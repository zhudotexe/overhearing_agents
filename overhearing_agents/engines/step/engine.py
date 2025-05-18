import functools
import json
import logging
import os
import re
import tempfile
from pathlib import Path

import torch
from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess
from kani import AIFunction, ChatMessage, ChatRole, FunctionCall, ToolCall
from kani.engines import BaseEngine
from kani.engines.base import BaseCompletion, Completion
from kani.ext.realtime import interop
from pydub import AudioSegment
from transformers import AutoModelForCausalLM, AutoTokenizer

from .tokenizer import StepAudioTokenizer
from .utils import load_optimus_ths_lib

log = logging.getLogger(__name__)
has_cuda = torch.backends.cuda.is_built()


# ASR model from https://github.com/stepfun-ai/Step-Audio/blob/main/app.py
class CustomAsr:
    def __init__(self, model_name="iic/SenseVoiceSmall", device="cuda"):
        self.model = AutoModel(
            model=model_name,
            vad_model="fsmn-vad",
            vad_kwargs={"max_single_segment_time": 30000},
            device=device,
        )

    def run(self, audio_path):
        res = self.model.generate(
            input=audio_path,
            cache={},
            language="auto",  # "zh", "en", "yue", "ja", "ko", "nospeech"
            use_itn=True,
            batch_size_s=60,
            merge_vad=True,
            merge_length_s=15,
        )
        text = rich_transcription_postprocess(res[0]["text"])
        return text


class StepAudioChatEngine(BaseEngine):
    """Step-Audio-Chat"""

    max_context_size = 32768
    token_reserve = 5

    def __init__(
        self,
        tokenizer_path: Path | str,
        llm_path: Path | str,
        *,
        device: str | None = None,
        tokenizer_kwargs: dict = None,
        model_load_kwargs: dict = None,
        **hyperparams,
    ):
        """
        :param device: The hardware device to use. If not specified, uses CUDA if available; otherwise uses CPU.
        :param tokenizer_kwargs: Additional arguments to pass to ``AutoTokenizer.from_pretrained()``.
        :param model_load_kwargs: Additional arguments to pass to ``AutoModelForCausalLM.from_pretrained()``.
        :param hyperparams: Additional arguments to supply the model during generation.
        """
        if tokenizer_kwargs is None:
            tokenizer_kwargs = {}
        if model_load_kwargs is None:
            model_load_kwargs = {}
        if device is None:
            device = "cuda" if has_cuda else "cpu"

        model_load_kwargs.setdefault("torch_dtype", "auto")
        if has_cuda:
            model_load_kwargs.setdefault("device_map", "auto")

        self.hyperparams = hyperparams

        # load the model
        load_optimus_ths_lib(os.path.join(llm_path, "lib"))
        self.tokenizer = AutoTokenizer.from_pretrained(llm_path, trust_remote_code=True, **tokenizer_kwargs)
        self.encoder = StepAudioTokenizer(tokenizer_path)
        self.llm = AutoModelForCausalLM.from_pretrained(llm_path, trust_remote_code=True, **model_load_kwargs)
        self.asr = CustomAsr(device=device)

        # ensure model is on correct device
        self.device = device
        if self.llm.device.type != self.device:
            self.llm.to(device)

    def message_len(self, message: ChatMessage) -> int:
        """Return the length, in tokens, of the given chat message."""
        prompt = self.translate_messages([message])
        # prompt str to tokens
        tokenized = self.tokenizer.encode(prompt, add_special_tokens=False)
        return len(tokenized)

    def function_token_reserve(self, functions: list[AIFunction]) -> int:
        tokenized = self.tokenizer.encode(self.translate_functions(functions), add_special_tokens=False)
        return len(tokenized)

    async def predict(
        self,
        messages: list[ChatMessage],
        functions: list[AIFunction] | None = None,
        *,
        decode_kwargs: dict = None,
        **hyperparams,
    ) -> BaseCompletion:
        if decode_kwargs is None:
            decode_kwargs = dict(skip_special_tokens=True)

        # put the available tools at the end since it's underspecified where to put them
        prompt = (
            self.translate_messages(messages[:-1], transcribe_audio=True)
            + self.translate_functions(functions)
            + self.translate_message(messages[-1], transcribe_audio=False)
        )
        if not prompt.endswith("<|BOT|>assistant\n"):
            prompt += "<|BOT|>assistant\n"
        log.debug(prompt)

        token_ids = self.tokenizer.encode(prompt, return_tensors="pt")
        input_len = len(token_ids[0])
        # move the input tensor to the right device
        if token_ids.device.type != self.device:
            token_ids = token_ids.to(self.device)
        # set up hyperparams for HF decode
        hyperparams = {**self.hyperparams, **hyperparams}
        if "max_new_tokens" not in hyperparams:
            hyperparams.setdefault("max_length", self.max_context_size)
        # run it through the model
        output = self.llm.generate(token_ids, **hyperparams)
        # decode to tokens
        # the completion shouldn't include the prompt or stop token
        content = self.tokenizer.decode(output[0][input_len:], **decode_kwargs).strip()
        output_len = len(output[0]) - (input_len + 1)
        log.debug(content)
        # parse for function calls
        tool_calls, content = self.parse_tool_calls(content)
        return Completion(
            ChatMessage.assistant(content, tool_calls=tool_calls), prompt_tokens=input_len, completion_tokens=output_len
        )

    # ==== step port ====
    @functools.cache
    def encode_audio(self, audio_bytes: bytes):
        """Encode audio in 24kHz PCM to tokens"""
        # equivalence verify
        # $ ffmpeg -i data/starless/StarlessTest.m4a -ac 1 -ar 24000 data/starless/muxed/StarlessTest.wav
        # import torchaudio, torch
        # from pathlib import Path
        # audio_path_wav = Path("/Users/andrew/Desktop/Code/overhearing_agents/data/starless/muxed/StarlessTest.wav")
        # audio_path_pcm = Path("/Users/andrew/Desktop/Code/overhearing_agents/data/starless/muxed/StarlessTest.pcm")
        # audio_wav, sr = torchaudio.load(audio_path_wav)
        # audio_bytes = audio_path_pcm.read_bytes()
        # audio_ints = torch.frombuffer(audio_bytes, dtype=torch.int16)
        # audio_wav2 = audio_ints.div(32768).reshape(1, -1)
        # (audio_wav == audio_wav2).all()
        sr = 24000
        audio_ints = torch.frombuffer(audio_bytes, dtype=torch.int16)
        audio_wav = audio_ints.div(32768).reshape(1, -1)
        # stereo -> mono if needed (which we don't since we force mono)
        # audio_wav = audio_wav.mean(dim=0, keepdim=True)
        audio_tokens = self.encoder(audio_wav, sr)
        return audio_tokens

    def translate_functions(self, functions: list[AIFunction] | None) -> str:
        if not functions:
            return ""
        # see https://github.com/stepfun-ai/Step-Audio/issues/31#issuecomment-2677484268
        # "The definition of the tool should be placed in a role called tool_json_schemas and passed to the model."
        tool_json_schemas = json.dumps([f.json_schema for f in functions])
        return f"<|BOT|>tool_json_schemas\n{tool_json_schemas}<|EOT|>"

    def translate_message(self, message: ChatMessage, transcribe_audio=False) -> str:
        if message.role == ChatRole.USER:
            role_str = "human"
        else:
            role_str = message.role.value

        # todo what do function returns look like
        # presumably just role function

        if isinstance(message.content, str):
            body = f"<|BOT|>{role_str}\n{message.content}"
        elif isinstance(message.content, list):
            if transcribe_audio:
                body = f"<|BOT|>{role_str}\n{self.transcribe_message(message)}"
            else:
                out = []
                for part in message.content:
                    if isinstance(part, interop.AudioPart):
                        audio_tokens = self.encode_audio(part.audio_bytes)
                        out.append(audio_tokens)
                    else:
                        out.append(str(part))
                out_str = "\n".join(out)
                body = f"<|BOT|>{role_str}\n{out_str}"
        else:
            body = f"<|BOT|>{role_str}\n"

        # add function calls, though this seems somewhat inconsistent
        # <|CALL_START|> function
        # wikipedia
        # {"title": "Yamanote Line"}<|CALL_END|>
        if message.tool_calls:
            for tc in message.tool_calls:
                body += f"<|CALL_START|> function\n{tc.function.name}\n{tc.function.arguments}<|CALL_END|>"

        return f"{body}<|EOT|>"

    def transcribe_message(self, message: ChatMessage) -> str:
        """Use the ASR model in the Step-Audio repo to transcribe a message's audio, if any"""
        for part in message.parts:
            if not isinstance(part, interop.AudioPart):
                continue
            if part.transcript is not None:
                continue
            log.debug(f"Transcribing {part.audio_duration}s audio")
            # save the audio to a temporary wav file and transcribe it
            with tempfile.NamedTemporaryFile(suffix=".wav") as f:
                segment = AudioSegment(part.audio_bytes, sample_width=2, frame_rate=24000, channels=1)
                segment.export(f.name, format="wav")
                part.transcript = self.asr.run(f.name)
                log.debug(f"Transcript: {part.transcript}")
        return message.text

    def translate_messages(self, messages: list[ChatMessage], transcribe_audio=None) -> str:
        out = []
        for idx, msg in enumerate(messages):
            if transcribe_audio is None:
                do_transcribe = idx != len(messages) - 1
            else:
                do_transcribe = transcribe_audio
            # use transcriptions of messages that are not the most recent
            # which is what their impl does
            out.append(self.translate_message(msg, transcribe_audio=do_transcribe))
        return "".join(out)

    def parse_tool_calls(self, content: str) -> tuple[list[ToolCall] | None, str]:
        tool_calls = []

        def _record_and_remove(match):
            function_name = match[1]
            args_json = match[2]
            # if the args aren't json, panic
            try:
                json.loads(args_json)
            except json.JSONDecodeError:
                return match[0]
            # record the tool call and remove it from the str
            tool_calls.append(ToolCall.from_function_call(FunctionCall(name=function_name, arguments=args_json)))
            return ""

        content = re.sub(r"<\|CALL_START\|> ?function\n(.+)\n(.+)<\|CALL_END\|>", _record_and_remove, content)
        return tool_calls, content
