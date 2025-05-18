import json
import logging
import re
from typing import AsyncIterable

from kani import AIFunction, ChatMessage, ChatRole, FunctionCall, ToolCall
from kani.engines import WrapperEngine
from kani.engines.base import BaseCompletion

log = logging.getLogger(__name__)


class SimpleReActEngine(WrapperEngine):
    """
    Simple prompter/parser for ReAct prompting. A few-shot prompt is probably necessary, and instructions should be
    given in the system prompt.

    Functions are not automatically passed to the model and must be prompted manually or in the engine implementation.

    Tool calls are done in the format::

        Action: {"tool_name": {...tool_args}}

    Streaming is not supported for my sanity.
    """

    def __init__(
        self,
        *args,
        react_add_observation_to_function_msgs=True,
        react_translate_function_msgs_to_user=False,
        react_use_natural_language_tool_prompt=False,
        **kwargs,
    ):
        """
        :param react_add_observation_to_function_msgs: Whether FUNCTION messages' content should be prefixed with
            ``Observation:``.
        :param react_translate_function_msgs_to_user: Whether FUNCTION messages should be translated to USER messages
            before sending them to the underlying model.
        :param react_use_natural_language_tool_prompt: Whether the natural language tool prompt should be appended to
            the system prompt. If True, functions will not be passed to the underlying engine - all tool calling will
            be handled at the ReAct level.
        """
        super().__init__(*args, **kwargs)
        self.add_observation_to_function_msgs = react_add_observation_to_function_msgs
        self.translate_function_msgs_to_user = react_translate_function_msgs_to_user
        self.use_natural_language_tool_prompt = react_use_natural_language_tool_prompt

    # ==== kani iface ====
    def function_token_reserve(self, functions: list[AIFunction]) -> int:
        if not self.use_natural_language_tool_prompt:
            return self.engine.function_token_reserve(functions)
        # if we're handling functions, see how long the system message is
        return self.engine.message_len(ChatMessage.system(simple_translate_functions(functions)))

    def message_len(self, message: ChatMessage) -> int:
        translated_message = self.translate_message(message)
        return self.engine.message_len(translated_message)

    async def predict(
        self, messages: list[ChatMessage], functions: list[AIFunction] | None = None, **hyperparams
    ) -> BaseCompletion:
        # if we're handling tool calling, make sure we have a system message that has the prompt
        if self.use_natural_language_tool_prompt:
            # tools go in the system prompt
            system_message_idx, system_message = next(
                ((idx, m) for idx, m in enumerate(messages) if m.role == ChatRole.SYSTEM), (None, None)
            )
            if not system_message:
                messages = [ChatMessage.system(simple_translate_functions(functions))] + messages
            else:
                messages[system_message_idx] = system_message.copy_with(
                    text=f"{system_message.text}\n\n{simple_translate_functions(functions)}"
                )
            # and don't pass through any functions
            functions = None

        # add in the Action: / Observation: (optionally) parts
        translated_messages = [self.translate_message(m) for m in messages]
        completion = await self.engine.predict(translated_messages, functions, **hyperparams)

        log.debug(f"Content before ReAct parsing: {completion.message.text}")
        content, tool_calls = self.parse_completion(completion.message.text)
        completion.message.content = content
        completion.message.tool_calls = tool_calls
        return completion

    async def stream(
        self, messages: list[ChatMessage], functions: list[AIFunction] | None = None, **hyperparams
    ) -> AsyncIterable[str | BaseCompletion]:
        completion = await self.predict(messages, functions, **hyperparams)
        yield completion.message.text
        yield completion

    # ==== translation & parsing ====
    def translate_message(self, message: ChatMessage) -> ChatMessage:
        match message:
            # assistant messages: add Thought and Action
            case ChatMessage(role=ChatRole.ASSISTANT, tool_calls=tc) if not tc:
                return message.copy_with(text=f"{message.text}\nAction: None".strip())
            case ChatMessage(role=ChatRole.ASSISTANT, tool_calls=list() as tc):
                actions = []
                for tc in tc:
                    action_json = json.dumps({"name": tc.function.name, "parameters": tc.function.kwargs})
                    actions.append(f"Action: {action_json}")
                actions_str = "\n".join(actions)
                return message.copy_with(tool_calls=None, text=f"{message.text}\n{actions_str}".strip())
            # function messages: add Observation
            case ChatMessage(role=ChatRole.FUNCTION):
                if self.translate_function_msgs_to_user:
                    message = message.copy_with(role=ChatRole.USER)
                if self.add_observation_to_function_msgs:
                    return message.copy_with(parts=["Observation: ", *message.parts])
                return message
        # base case: no change
        return message

    @staticmethod
    def parse_completion(content: str) -> tuple[str, list[ToolCall]]:
        # parse thought (everything before action)
        thought, *_ = content.split("Action:")
        thought_str = thought.strip()

        # parse actions
        actions = re.finditer(r"\n?Action:\s*(.+?)$", content, re.MULTILINE | re.IGNORECASE)
        tool_calls = []

        for match in actions:
            log.debug(f"Found action: {match[0]}")
            if match[1].lower() == "none":
                continue
            # if the args aren't json, panic
            try:
                data = json.loads(match[1])
            except json.JSONDecodeError:
                log.warning(f"Could not parse action JSON: {match[0]}")
                thought_str += match[0]
                continue
            # the data should be a dict
            if not isinstance(data, dict):
                log.warning(f"Action is not a dict: {match[0]}")
                thought_str += match[0]
                continue
            function_name = data["name"]
            args = data["parameters"]
            # the args should be a dict
            if not isinstance(args, dict):
                log.warning(f"Action arguments are not a dict: {match[0]}")
                thought_str += match[0]
                continue
            # record the tool call and remove it from the str
            tool_calls.append(ToolCall.from_function_call(FunctionCall(name=function_name, arguments=json.dumps(args))))

        # return new content, tool calls
        return thought_str, tool_calls


def simple_translate_functions(functions: list[AIFunction] | None) -> str:
    """A simple, natural-language prompt for tools."""
    if not functions:
        return ""
    tool_specs = []
    for tool in functions:
        tool_specs.append({
            "name": tool.name,
            "description": tool.desc,
            "parameters": tool.create_json_schema(include_desc=False),
        })
    tool_jsons = "\n".join(json.dumps(s) for s in tool_specs)
    return (
        "# Tools\n\nYou are provided with the following tools, which you should use in your"
        f" actions.\n<tools>\n{tool_jsons}\n</tools>\nTo use a tool, output a JSON object as your action with the"
        ' following format: `{"name": function name, "parameters": dictionary of argument name and its value}`.'
    )


def create_guidance_regex_for_functions(_, functions: list[AIFunction] | None) -> str:
    from outlines.fsm.json_schema import convert_json_schema_to_str
    from outlines_core.fsm.outlines_core_rs import build_regex_from_schema

    # we create a JSON schema regex for each function
    function_regexes = []
    if functions:
        for f in functions:
            schema_str = convert_json_schema_to_str(json_schema=f.json_schema)
            function_regex = build_regex_from_schema(schema_str)
            # {"name": ..., "parameters": ...}
            function_regexes.append(rf'(\{{ ?"name": ?"{re.escape(f.name)}", ?"parameters": ?{function_regex}\}})')
            # {"name": {parameters...}}
            # function_regexes.append(rf'(\{{ ?"{re.escape(f.name)}" ?: ?{function_regex}\}})')

    # then handwrite a regex for the rest
    # only one of the functions per Action
    function_regexes.append("None")
    return "|".join(function_regexes)


def create_guidance_regex_for_react(_, functions: list[AIFunction] | None) -> str:
    action_regex = create_guidance_regex_for_functions(_, functions)
    # Thought then Action
    regex_string = rf"Thought:.+\nAction: ?({action_regex})"
    log.debug(f"Regex string for functions: {regex_string}")
    return regex_string


def create_guidance_regex_for_react_with_transcribe(_, functions: list[AIFunction] | None) -> str:
    # start from Thought and action
    thought_action_regex = create_guidance_regex_for_react(_, functions)
    regex_string = rf"Transcript:.+\n{thought_action_regex}"
    log.debug(f"Regex string for react with transcript: {regex_string}")
    return regex_string


def create_guidance_regex_for_react_noreason(_, functions: list[AIFunction] | None) -> str:
    # only Action
    action_regex = create_guidance_regex_for_functions(_, functions)
    regex_string = rf"Action: ?({action_regex})"
    log.debug(f"Regex string for functions: {regex_string}")
    return regex_string
