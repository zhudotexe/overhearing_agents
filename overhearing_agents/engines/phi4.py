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
from transformers import AutoProcessor, GenerationConfig

log = logging.getLogger(__name__)


class Phi4MultimodalEngine(HuggingEngine):
    def __init__(
        self,
        model_id: str = "microsoft/Phi-4-multimodal-instruct",
        max_context_size: int = 128000,
        prompt_pipeline: PromptPipeline = None,
        *,
        tokenizer_kwargs: dict = None,
        model_load_kwargs: dict = None,
        token_reserve=1,
        **kwargs,
    ):
        if tokenizer_kwargs is None:
            tokenizer_kwargs = {"trust_remote_code": True}
        tokenizer_kwargs.setdefault("trust_remote_code", True)
        if model_load_kwargs is None:
            model_load_kwargs = {"trust_remote_code": True}
        model_load_kwargs.setdefault("trust_remote_code", True)
        super().__init__(
            model_id=model_id,
            max_context_size=max_context_size,
            prompt_pipeline=prompt_pipeline,
            tokenizer_kwargs=tokenizer_kwargs,
            model_load_kwargs=model_load_kwargs,
            token_reserve=token_reserve,
            **kwargs,
        )
        self.processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
        self.generation_config = GenerationConfig.from_pretrained(model_id, "generation_config.json")

    # ==== kani impls ====
    def message_len(self, message: ChatMessage) -> int:
        """Return the length, in tokens, of the given chat message."""
        prompt, audios = translate_message_mm(message)
        if not audios:
            audios = None
        processed = self.processor(text=prompt, audios=audios)
        # prompt str to tokens
        return processed["input_ids"].shape[-1] + 2

    def function_token_reserve(self, functions: list[AIFunction]) -> int:
        if not functions:
            return 0
        processed = self.processor(text=translate_functions(functions))
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
        audio_idx = 1
        for msg in messages:
            log.debug(f"Translating message: {msg.text}")
            part, part_audios = translate_message_mm(msg, audio_idx)
            audio_idx += len(part_audios)
            prompt_parts.append(part)
            audios.extend(part_audios)
            log.debug(f"Part: {part}, Audios: {len(part_audios)}")

        # append an assistant generation prompt at the end
        prompt_parts.append("<|assistant|>")
        prompt = "".join(prompt_parts)
        log.debug(prompt)
        log.debug(f"{len(audios)} audios")
        if not audios:
            audios = None

        # embed the audio and get generation args
        input_args = self.processor(text=prompt, audios=audios, return_tensors="pt").to(self.device)
        input_len = input_args["input_ids"].shape[-1]

        hyperparams = {**self.hyperparams, **hyperparams}
        hyperparams.setdefault("max_length", self.max_context_size)

        # run it through the model
        output = self.model.generate(**input_args, **hyperparams, generation_config=self.generation_config)

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


# ==== general phi stuff ====
def translate_functions(functions: list[AIFunction] | None) -> str:
    """Translate a list of functions into the Phi-format tool list."""
    if not functions:
        return ""
    tool_specs = []
    for tool in functions:
        params = {}
        for param_name, schema in tool.json_schema["properties"].items():
            param_spec = {}
            # description, type, default
            default_keys = ("description", "type", "default")
            for key in default_keys:
                if v := schema.get(key):
                    param_spec[key] = v
            # other non-title params (e.g. enum)
            param_spec |= {k: v for k, v in schema.items() if k not in (*default_keys, "title")}
            params[param_name] = param_spec
        tool_specs.append({"name": tool.name, "description": tool.desc, "parameters": params})
    tool_specs_json = json.dumps(tool_specs)
    return f"<|tool|>{tool_specs_json}<|/tool|>"


def parse_tool_calls(content: str) -> tuple[list[ToolCall] | None, str]:
    tool_calls = []

    def _record_and_remove(match):
        # if the args aren't json, panic
        try:
            tcs = json.loads(match[1])
        except json.JSONDecodeError:
            log.warning(f"Could not decode tool call: {match[0]}")
            return match[0]
        if not isinstance(tcs, list):
            log.warning(f"Parsed tool call is not list: {match[0]}")
            return match[0]
        # record the tool call and remove it from the str
        for tc in tcs:
            tool_calls.append(
                ToolCall.from_function_call(
                    FunctionCall(name=tc.get("name"), arguments=json.dumps(tc.get("arguments")))
                )
            )
        return ""

    content = re.sub(r"<\|tool_call\|>(.+)<\|/tool_call\|>", _record_and_remove, content)
    return tool_calls, content


# ==== audio multimodal ====
def translate_message_mm(message: ChatMessage, audio_idx=1) -> tuple[str, list[tuple[np.ndarray, int]]]:
    """Given a chat message, return the string prompt and a list of audios"""
    if message.role == ChatRole.FUNCTION:
        role_str = "tool_response"
    else:
        role_str = message.role.value

    audios = []
    if isinstance(message.content, str):
        body = f"<|{role_str}|>{message.content}"
    elif isinstance(message.content, list):
        out = []
        for part in message.content:
            if isinstance(part, interop.AudioPart):
                out.append(f"<|audio_{audio_idx}|>")
                audio_idx += 1
                audios.append(pcm16_to_soundfile(part.audio_bytes))
            else:
                out.append(str(part))
        out_str = "".join(out)
        body = f"<|{role_str}|>{out_str}"
    else:
        body = f"<|{role_str}|>"

    # add function calls
    if message.tool_calls:
        tcs = []
        for tc in message.tool_calls:
            tcs.append({"name": tc.function.name, "arguments": tc.function.kwargs})
        body += f"<|tool_call|>{json.dumps(tcs)}<|/tool_call|>"

    return f"{body}<|end|>", audios


def pcm16_to_soundfile(audio_bytes: bytes) -> tuple[np.ndarray, int]:
    """Convert raw PCM bytes (24kHz mono, 16b signed) to the soundfile bytes phi expects"""
    audio_filelike = io.BytesIO(audio_bytes)
    return soundfile.read(audio_filelike, channels=1, samplerate=24000, format="RAW", subtype="PCM_16")
