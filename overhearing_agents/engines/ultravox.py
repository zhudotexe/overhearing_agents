import io
import json
import logging
import re

import accelerate
import numpy as np
import soundfile
from kani import AIFunction, ChatMessage, ChatRole, FunctionCall, ToolCall
from kani.engines import BaseEngine, Completion
from kani.ext.realtime import interop
from pydub import AudioSegment
from transformers import AutoModel, AutoProcessor, AutoTokenizer

log = logging.getLogger(__name__)


# this is pretty much a HuggingEngine but we need to do some shenanigans to get it on GPUs so we inherit from BaseEngine
class UltravoxLlama33Engine(BaseEngine):
    def __init__(
        self,
        model_id: str = "fixie-ai/ultravox-v0_5-llama-3_3-70b",
        max_context_size: int = 128000,
        *,
        # hf args
        token=None,
        tokenizer_kwargs: dict = None,
        model_cls=AutoModel,
        model_load_kwargs: dict = None,
        # kani args
        token_reserve=7,
        # ultravox kwargs
        tool_calls_exclusive_in_message=True,
        wacky_device_map_fix=True,
        **hyperparams,
    ):
        if tokenizer_kwargs is None:
            tokenizer_kwargs = {}
        if model_load_kwargs is None:
            model_load_kwargs = {}

        tokenizer_kwargs.setdefault("token", hyperparams.get("use_auth_token", token))
        tokenizer_kwargs.setdefault("trust_remote_code", True)
        model_load_kwargs.setdefault("token", hyperparams.pop("use_auth_token", token))
        model_load_kwargs.setdefault("torch_dtype", "auto")
        model_load_kwargs.setdefault("trust_remote_code", True)

        self.model_id = model_id
        self.max_context_size = max_context_size

        self.tokenizer = AutoTokenizer.from_pretrained(model_id, **tokenizer_kwargs)
        self.model = model_cls.from_pretrained(model_id, **model_load_kwargs)
        self.processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)

        self.tool_calls_exclusive_in_message = tool_calls_exclusive_in_message

        self.hyperparams = hyperparams
        self.token_reserve = token_reserve

        if wacky_device_map_fix:
            # ensure model is on correct device - this is the weird part
            # we basically do device_map="auto" manually
            self.model.tie_weights()
            # this does it automatically but is fragile
            # device_map = _get_device_map(
            #     self.model,
            #     device_map="auto",
            #     max_memory=None,
            #     hf_quantizer=None,
            #     torch_dtype=self.model.dtype,
            #     keep_in_fp32_modules=None,
            # )
            # ["LlamaDecoderLayer"]
            no_split_modules = self.model._get_no_split_modules("auto")
            max_memory = accelerate.utils.get_balanced_memory(self.model)
            device_map = accelerate.infer_auto_device_map(
                self.model, max_memory=max_memory, no_split_module_classes=no_split_modules
            )
            accelerate.dispatch_model(self.model, device_map)

    # ==== kani impls ====
    def message_len(self, message: ChatMessage) -> int:
        """Return the length, in tokens, of the given chat message."""
        prompt, audios = translate_message_mm(message, tool_calls_exclusive=self.tool_calls_exclusive_in_message)
        if not audios:
            audios = None
        processed = self.processor(text=prompt, audios=audios, return_tensors="pt", sampling_rate=16000)
        # prompt str to tokens
        return processed["input_ids"].shape[-1] + 7

    def function_token_reserve(self, functions: list[AIFunction]) -> int:
        if not functions:
            return 0
        processed = self.processor(
            text=translate_functions(functions, tool_calls_exclusive=self.tool_calls_exclusive_in_message),
            return_tensors="pt",
            sampling_rate=16000,
        )
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
                messages = [
                    ChatMessage.system(
                        translate_functions(functions, tool_calls_exclusive=self.tool_calls_exclusive_in_message)
                    ),
                    *messages,
                ]
            else:
                messages[system_message_idx] = system_message.copy_with(
                    text=translate_functions(functions, tool_calls_exclusive=self.tool_calls_exclusive_in_message)
                    + system_message.text
                )
        prompt_parts = []
        audios = []

        # keep track of audio idxs
        for msg in messages:
            log.debug(f"Translating message: {msg.text}")
            part, part_audios = translate_message_mm(msg, tool_calls_exclusive=self.tool_calls_exclusive_in_message)
            prompt_parts.append(part)
            audios.extend(part_audios)
            log.debug(f"Part: {part}, Audios: {len(part_audios)}")

        # append an assistant generation prompt at the end
        prompt_parts.append("<|start_header_id|>assistant<|end_header_id|>\n\n")
        prompt = "".join(prompt_parts)
        log.debug(prompt)
        log.debug(f"{len(audios)} audios")
        if not audios:
            audios = None

        # embed the audio and get generation args
        input_args = (
            self.processor(text=prompt, audios=audios, return_tensors="pt", sampling_rate=16000)
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
        tool_calls, content = parse_tool_calls(content, tool_calls_exclusive=self.tool_calls_exclusive_in_message)
        output_len = len(output[0]) - (input_len + 1)
        return Completion(
            ChatMessage.assistant(content, tool_calls=tool_calls), prompt_tokens=input_len, completion_tokens=output_len
        )

    async def stream(self, messages: list[ChatMessage], functions: list[AIFunction] | None = None, **hyperparams):
        completion = await self.predict(messages, functions, **hyperparams)
        yield completion.message.text
        yield completion


# ==== general qwen stuff ====
def translate_functions(functions: list[AIFunction] | None, tool_calls_exclusive=True) -> str:
    """Translate a list of functions into the Llama33-format tool list."""
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
    tool_jsons = "\n\n".join(json.dumps(spec, indent=4) for spec in tool_specs)
    if tool_calls_exclusive:
        return (
            "Environment: ipython\nCutting Knowledge Date: December 2023\nToday Date: 26 Jul 2024\nYou have access to"
            " the following functions. To call a function, please respond with JSON for a function call. Respond in the"
            ' format {"name": function name, "parameters": dictionary of argument name and its value}. Do not use'
            f" variables.\n\n{tool_jsons}\n\n"
        )
    return (
        "Environment: ipython\nCutting Knowledge Date: December 2023\nToday Date: 26 Jul 2024\nYou have access to the"
        " following functions. To call a function, please respond with JSON for a function call after your normal"
        ' output. Respond in the format <tool_call>\n{"name": function name, "parameters": dictionary of argument name'
        f" and its value}}\n</tool_call>. Do not use variables.\n\n{tool_jsons}\n\n"
    )


def parse_tool_calls(content: str, tool_calls_exclusive=True) -> tuple[list[ToolCall] | None, str]:
    tool_calls = []

    def _record_and_remove(match):
        # if the args aren't json, panic
        try:
            data = json.loads(match[1])
        except json.JSONDecodeError:
            log.warning(f"Could not decode tool call: {match[0]}")
            return match[0]
        if not isinstance(data, dict):
            return match[0]
        # record the tool call and remove it from the str
        tool_calls.append(
            ToolCall.from_function_call(
                FunctionCall(name=data.get("name"), arguments=json.dumps(data.get("parameters")))
            )
        )
        return ""

    if not tool_calls_exclusive:
        content = re.sub(r"<tool_call>\s*(.+)\s*</tool_call>", _record_and_remove, content)
        content = content.strip()
    else:
        # content should just be a JSON string
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                tool_calls.append(
                    ToolCall.from_function_call(
                        FunctionCall(name=data.get("name"), arguments=json.dumps(data.get("parameters")))
                    )
                )
                content = None
        except json.JSONDecodeError:
            pass
    return tool_calls, content


# ==== audio multimodal ====
def translate_message_mm(message: ChatMessage, tool_calls_exclusive=True) -> tuple[str, list[np.ndarray]]:
    """Given a chat message, return the string prompt and a list of audios"""
    if message.role == ChatRole.FUNCTION:
        role_str = "ipython"
    else:
        role_str = message.role.value

    audios = []
    if isinstance(message.content, str):
        body = f"<|start_header_id|>{role_str}<|end_header_id|>\n\n{message.content}"
    elif isinstance(message.content, list):
        out = []
        for part in message.content:
            if isinstance(part, interop.AudioPart):
                out.append("<|audio|>")
                audios.append(pcm16_to_numpy(part.audio_bytes))
            else:
                out.append(str(part))
        out_str = "".join(out)
        body = f"<|start_header_id|>{role_str}<|end_header_id|>\n\n{out_str}"
    else:
        body = f"<|start_header_id|>{role_str}<|end_header_id|>\n\n"

    # add function calls
    if message.tool_calls:
        tcs = []
        for tc in message.tool_calls:
            tcs.append({"name": tc.function.name, "parameters": tc.function.kwargs})
        # WARNING: llama does not like tool calls mixed in with text output, by default tool calling JSON can be the
        # only thing in a body
        if tool_calls_exclusive:
            body = f"{json.dumps(tcs)}"
        else:
            body += f"<tool_call>\n{json.dumps(tcs)}\n</tool_call>"

    return f"{body}<|eot_id|>", audios


def pcm16_to_numpy(audio_bytes: bytes) -> np.ndarray:
    """Convert raw PCM bytes (24kHz mono, 16b signed) to arrays of floats at 16kHz."""
    # load and resample to 16kHz mono
    segment = AudioSegment(audio_bytes, sample_width=2, frame_rate=24000, channels=1)
    segment.set_frame_rate(16000)
    # then load it as a numpy array
    audio_filelike = io.BytesIO(segment.raw_data)
    data, sr = soundfile.read(audio_filelike, channels=1, samplerate=16000, format="RAW", subtype="PCM_16")
    return data
