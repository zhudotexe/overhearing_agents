import io
import json
import logging
import re

import numpy as np
import soundfile
from kani import AIFunction, ChatMessage, ChatRole, FunctionCall, PromptPipeline, ToolCall
from kani.engines import Completion
from kani.engines.huggingface import HuggingEngine
from kani.ext.realtime import interop
from pydub import AudioSegment
from transformers import AutoProcessor, Qwen2_5OmniForConditionalGeneration

log = logging.getLogger(__name__)


class QwenOmniEngine(HuggingEngine):
    def __init__(
        self,
        model_id: str = "Qwen/Qwen2.5-Omni-7B",
        max_context_size: int = 32768,
        prompt_pipeline: PromptPipeline = None,
        *,
        tokenizer_kwargs: dict = None,
        model_load_kwargs: dict = None,
        model_cls=Qwen2_5OmniForConditionalGeneration,
        token_reserve=7,
        **kwargs,
    ):
        super().__init__(
            model_id=model_id,
            max_context_size=max_context_size,
            prompt_pipeline=prompt_pipeline,
            tokenizer_kwargs=tokenizer_kwargs,
            model_load_kwargs=model_load_kwargs,
            model_cls=model_cls,
            token_reserve=token_reserve,
            **kwargs,
        )
        self.processor = AutoProcessor.from_pretrained(model_id)

    # ==== kani impls ====
    def message_len(self, message: ChatMessage) -> int:
        """Return the length, in tokens, of the given chat message."""
        prompt, audios = translate_message_mm(message)
        if not audios:
            audios = None
        processed = self.processor(text=prompt, audio=audios, padding=True, return_tensors="pt")
        # prompt str to tokens
        return processed["input_ids"].shape[-1] + 7

    def function_token_reserve(self, functions: list[AIFunction]) -> int:
        if not functions:
            return 0
        processed = self.processor(text=translate_functions(functions), return_tensors="pt")
        return processed["input_ids"].shape[-1]

    async def predict(
        self,
        messages: list[ChatMessage],
        functions: list[AIFunction] | None = None,
        *,
        decode_kwargs: dict = None,
        **hyperparams,
    ) -> Completion:
        """
        Given the current context of messages and available functions, get the next predicted chat message from the LM.

        :param messages: The messages in the current chat context. ``sum(message_len(m) for m in messages)`` is
            guaranteed to be less than max_context_size.
        :param functions: The functions the LM is allowed to call.
        :param decode_kwargs: Any arguments to pass to AutoTokenizer.decode(). Defaults to
            ``dict(skip_special_tokens=True)``.
        :param hyperparams: Any additional parameters to pass to GenerationMixin.generate(). (See
            https://huggingface.co/docs/transformers/main_classes/text_generation)
        """
        if decode_kwargs is None:
            decode_kwargs = dict(skip_special_tokens=True)

        # translate the messages
        if functions:
            # tools go in the system prompt
            system_message_idx, system_message = next(
                ((idx, m) for idx, m in enumerate(messages) if m.role == ChatRole.SYSTEM), (None, None)
            )
            if not system_message:
                messages = [ChatMessage.system(translate_functions(functions))] + messages
            else:
                messages[system_message_idx] = system_message.copy_with(
                    text=system_message.text + translate_functions(functions)
                )
        prompt_parts = []
        audios = []

        # keep track of audio idxs
        for msg in merge_function_messages(messages):
            log.debug(f"Translating message: {msg.text}")
            part, part_audios = translate_message_mm(msg)
            prompt_parts.append(part)
            audios.extend(part_audios)
            log.debug(f"Part: {part}, Audios: {len(part_audios)}")

        # append an assistant generation prompt at the end
        prompt_parts.append("<|im_start|>assistant\n")
        prompt = "".join(prompt_parts)
        log.debug(prompt)
        log.debug(f"{len(audios)} audios")
        if not audios:
            audios = None

        # embed the audio and get generation args
        input_args = (
            self.processor(text=prompt, audio=audios, return_tensors="pt", padding=True)
            .to(self.model.device)
            .to(self.model.dtype)
        )
        input_len = input_args["input_ids"].shape[-1]

        hyperparams = {**self.hyperparams, **hyperparams}
        hyperparams.setdefault("max_length", self.max_context_size)

        # run it through the model
        output = self.model.generate(**input_args, **hyperparams)

        # decode to tokens
        # the completion shouldn't include the prompt or stop token
        content = self.tokenizer.decode(output[0][input_len:], **decode_kwargs).strip()
        tool_calls, content = parse_tool_calls(content)
        output_len = len(output[0]) - (input_len + 1)
        return Completion(
            ChatMessage.assistant(content, tool_calls=tool_calls), prompt_tokens=input_len, completion_tokens=output_len
        )

    async def stream(self, messages: list[ChatMessage], functions: list[AIFunction] | None = None, **hyperparams):
        completion = await self.predict(messages, functions, **hyperparams)
        yield completion.message.text
        yield completion


# ==== general qwen stuff ====
def translate_functions(functions: list[AIFunction] | None) -> str:
    """Translate a list of functions into the Qwen-format tool list."""
    if not functions:
        return ""
    tool_specs = []
    for tool in functions:
        tool_specs.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.desc,
                "parameters": tool.create_json_schema(include_desc=False),
            },
        })
    tool_jsons = "\n".join(json.dumps(spec) for spec in tool_specs)
    return (
        "\n\n# Tools\n\nYou may call one or more functions to assist with the user query.\n\nYou are provided with"
        f" function signatures within <tools></tools> XML tags:\n<tools>\n{tool_jsons}\n</tools>\n\nFor each function"
        " call, return a json object with function name and arguments within <tool_call></tool_call> XML"
        ' tags:\n<tool_call>\n{"name": <function-name>, "arguments": <args-json-object>}\n</tool_call>'
    )


def parse_tool_calls(content: str) -> tuple[list[ToolCall] | None, str]:
    tool_calls = []

    def _record_and_remove(match):
        # if the args aren't json, panic
        try:
            tc = json.loads(match[1])
        except json.JSONDecodeError:
            log.warning(f"Could not decode tool call: {match[0]}")
            return match[0]
        if not isinstance(tc, dict):
            log.warning(f"Parsed tool call is not dict: {match[0]}")
            return match[0]
        # record the tool call and remove it from the str
        tool_calls.append(
            ToolCall.from_function_call(FunctionCall(name=tc.get("name"), arguments=json.dumps(tc.get("arguments"))))
        )
        return ""

    content = re.sub(r"<tool_call>\s*(.+)\s*</tool_call>", _record_and_remove, content)
    return tool_calls, content.strip()


# ==== audio multimodal ====
merge_function_messages = (
    PromptPipeline()
    # tool messages get wrapped in <tool_response>\n\n</tool_response>
    .wrap(role=ChatRole.FUNCTION, prefix="<tool_response>\n", suffix="\n</tool_response>")
    # and merged together
    .merge_consecutive(role=ChatRole.FUNCTION, sep="\n")
    # and then they become user messages
    .translate_role(role=ChatRole.FUNCTION, to=ChatRole.USER)
)


def translate_message_mm(message: ChatMessage) -> tuple[str, list[np.ndarray]]:
    """Given a chat message, return the string prompt and a list of audios"""
    if message.role == ChatRole.FUNCTION:
        role_str = "user"
    else:
        role_str = message.role.value

    audios = []
    if isinstance(message.content, str):
        body = f"<|im_start|>{role_str}\n{message.content}"
    elif isinstance(message.content, list):
        out = []
        for part in message.content:
            if isinstance(part, interop.AudioPart):
                out.append("<|audio_bos|><|AUDIO|><|audio_eos|>")
                audios.append(pcm16_to_numpy(part.audio_bytes))
            else:
                out.append(str(part))
        out_str = "".join(out)
        body = f"<|im_start|>{role_str}\n{out_str}"
    else:
        body = f"<|im_start|>{role_str}\n"

    # add function calls
    if message.tool_calls:
        tcs = []
        for tc in message.tool_calls:
            tcs.append({"name": tc.function.name, "arguments": tc.function.kwargs})
        body += f"\n<tool_call>\n{json.dumps(tcs)}\n</tool_call>"

    return f"{body}<|im_end|>\n", audios


def pcm16_to_numpy(audio_bytes: bytes) -> np.ndarray:
    """Convert raw PCM bytes (24kHz mono, 16b signed) to arrays of floats at 16kHz."""
    # load and resample to 16kHz mono
    segment = AudioSegment(audio_bytes, sample_width=2, frame_rate=24000, channels=1)
    segment.set_frame_rate(16000)
    # then load it as a numpy array
    audio_filelike = io.BytesIO(segment.raw_data)
    data, sr = soundfile.read(audio_filelike, channels=1, samplerate=16000, format="RAW", subtype="PCM_16")
    return data
