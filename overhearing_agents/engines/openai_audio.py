import base64
import io
import math
import wave
from typing import AsyncIterable

from kani import AIFunction, ChatMessage, ChatRole, MessagePart, PromptPipeline
from kani.engines.base import Completion
from kani.engines.openai import OpenAIEngine
from kani.engines.openai.translation import (
    ChatCompletion,
    kani_tc_to_openai_tc,
    openai_tc_to_kani_tc,
    translate_functions,
)
from kani.ext.realtime import interop
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionFunctionMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionToolMessageParam,
    ChatCompletionUserMessageParam,
)


class OpenAIAudioEngine(OpenAIEngine):
    """An OpenAIEngine with multimodal audio support."""

    def __init__(self, *args, token_len_is_audio_duration=False, **kwargs):
        """
        :param token_len_is_audio_duration: If True, the message length for a given message will be
            max(1, duration in seconds of all audio in message) instead of the token length. This is useful for limiting
            the amount of audio processed by the model by duration.
        """
        super().__init__(*args, **kwargs)
        self.token_len_is_audio_duration = token_len_is_audio_duration

    def message_len(self, message: ChatMessage) -> int:
        audio_duration = sum(part.audio_duration for part in message.parts if isinstance(part, interop.AudioPart))

        if self.token_len_is_audio_duration:
            return max(math.ceil(audio_duration), 1)

        if (cached_len := self.get_cached_message_len(message)) is not None:
            return cached_len

        mlen = 7
        # text parts
        if message.text:
            mlen += len(self.tokenizer.encode(message.text))
        # audio parts - 10 tok/sec in openai
        mlen += math.ceil(audio_duration * 10)
        # misc meta
        if message.name:
            mlen += len(self.tokenizer.encode(message.name))
        if message.tool_calls:
            for tc in message.tool_calls:
                mlen += len(self.tokenizer.encode(tc.function.name))
                mlen += len(self.tokenizer.encode(tc.function.arguments))

        # HACK: using gpt-4o and parallel function calling, the API randomly adds tokens based on the length of the
        # TOOL message (see tokencounting.ipynb)???
        # this seems to be ~ 6 + (token len / 20) tokens per message (though it randomly varies), but this formula
        # is <10 tokens of an overestimate in most cases
        if self.model.startswith("gpt-4o") and message.role == ChatRole.FUNCTION:
            mlen += 6 + (mlen // 20)

        return mlen

    async def predict(
        self, messages: list[ChatMessage], functions: list[AIFunction] | None = None, **hyperparams
    ) -> ChatCompletion:
        if functions:
            tool_specs = translate_functions(functions)
        else:
            tool_specs = None
        # translate to openai spec - group any tool messages together and ensure all free ToolCall IDs are bound
        translated_messages = translate_messages(messages)
        # make API call
        completion = await self.client.chat.completions.create(
            model=self.model, messages=translated_messages, tools=tool_specs, **(self.hyperparams | hyperparams)
        )
        # translate into Kani spec and return
        kani_cmpl = ChatCompletion(openai_completion=completion)
        self.set_cached_message_len(kani_cmpl.message, kani_cmpl.completion_tokens)
        return kani_cmpl

    async def stream(
        self, messages: list[ChatMessage], functions: list[AIFunction] | None = None, **hyperparams
    ) -> AsyncIterable[str | Completion]:
        if functions:
            tool_specs = translate_functions(functions)
        else:
            tool_specs = None
        # translate to openai spec - group any tool messages together and ensure all free ToolCall IDs are bound
        translated_messages = translate_messages(messages)
        # make API call
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=translated_messages,
            tools=tool_specs,
            stream=True,
            stream_options={"include_usage": True},
            **(self.hyperparams | hyperparams),
        )

        # save requested tool calls and content as streamed
        content_chunks = []
        tool_call_partials = {}  # index -> tool call
        usage = None

        # iterate over the stream and yield/save
        async for chunk in stream:
            # save usage if present
            if chunk.usage is not None:
                usage = chunk.usage

            if not chunk.choices:
                continue

            # process content delta
            delta = chunk.choices[0].delta

            # yield content
            if delta.content is not None:
                content_chunks.append(delta.content)
                yield delta.content

            # tool calls are partials, save a mapping to the latest state and we'll translate them later once complete
            if delta.tool_calls:
                # each tool call can have EITHER the function.name/id OR function.arguments
                for tc in delta.tool_calls:
                    if tc.id is not None:
                        tool_call_partials[tc.index] = tc
                    else:
                        partial = tool_call_partials[tc.index]
                        partial.function.arguments += tc.function.arguments

        # construct the final completion with streamed tool calls
        content = None if not content_chunks else "".join(content_chunks)
        tool_calls = [openai_tc_to_kani_tc(tc) for tc in sorted(tool_call_partials.values(), key=lambda c: c.index)]
        msg = ChatMessage(role=ChatRole.ASSISTANT, content=content, tool_calls=tool_calls)

        # token counting
        if usage:
            self.set_cached_message_len(msg, usage.completion_tokens)
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
        else:
            prompt_tokens = completion_tokens = None
        yield Completion(message=msg, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)


# ==== kani -> openai ====
# decomp
def kani_cm_to_openai_cm(msg: ChatMessage) -> ChatCompletionMessageParam:
    """Translate a kani ChatMessage into an OpenAI Message."""
    # translate tool responses to a function to the right openai format
    match msg.role:
        case ChatRole.FUNCTION if msg.tool_call_id is not None:
            return ChatCompletionToolMessageParam(role="tool", content=msg.text, tool_call_id=msg.tool_call_id)
        case ChatRole.FUNCTION:
            return ChatCompletionFunctionMessageParam(**_msg_kwargs(msg))
        case ChatRole.SYSTEM:
            return ChatCompletionSystemMessageParam(**_msg_kwargs(msg))
        case ChatRole.USER:
            return ChatCompletionUserMessageParam(**_msg_kwargs(msg))
        case _:  # assistant
            if msg.tool_calls:
                tool_calls = [kani_tc_to_openai_tc(tc) for tc in msg.tool_calls]
                return ChatCompletionAssistantMessageParam(**_msg_kwargs(msg), tool_calls=tool_calls)
            return ChatCompletionAssistantMessageParam(**_msg_kwargs(msg))


def _msg_kwargs(msg: ChatMessage) -> dict:
    match msg:
        case ChatMessage(role=ChatRole.USER, content=list(parts)):
            content = _parts_to_oai(parts)
        case _:
            content = msg.text

    data = dict(role=msg.role.value, content=content)
    if msg.name is not None:
        data["name"] = msg.name
    return data


def _parts_to_oai(parts: list[MessagePart | str]):
    out = []
    for part in parts:
        if isinstance(part, interop.AudioPart):
            wav_data = audio_part_wav_b64(part)
            out.append({"type": "input_audio", "input_audio": {"data": wav_data, "format": "wav"}})
        else:
            out.append({"type": "text", "text": str(part)})
    return out


def audio_part_wav_b64(part: interop.AudioPart):
    out_bytes = io.BytesIO()
    data_bytes = part.audio_bytes
    wave_data = wave.open(out_bytes, "wb")
    wave_data.setnchannels(1)
    wave_data.setsampwidth(2)
    wave_data.setframerate(24000)
    wave_data.setnframes(len(data_bytes) // 2)
    wave_data.writeframesraw(data_bytes)
    wave_data.close()

    out_bytes.seek(0)
    return base64.b64encode(out_bytes.read()).decode()


# main
OPENAI_PIPELINE = (
    PromptPipeline()
    .ensure_bound_function_calls()
    .ensure_start(predicate=lambda msg: msg.role != ChatRole.FUNCTION)
    .apply(kani_cm_to_openai_cm)
)


def translate_messages(messages: list[ChatMessage]) -> list[ChatCompletionMessageParam]:
    return OPENAI_PIPELINE(messages)
