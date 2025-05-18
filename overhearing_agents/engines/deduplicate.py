import base64
import itertools
import logging
from typing import Literal

from kani import ChatMessage, ChatRole
from kani.engines import WrapperEngine
from kani.exceptions import MessageTooLong
from kani.ext.realtime import interop

from overhearing_agents import events
from overhearing_agents.kanis.base import BaseKani

log = logging.getLogger(__name__)


class DeduplicateMessages(WrapperEngine):
    """
    A simple wrapper engine that deduplicates ASSISTANT messages.

    If the same message appears twice (or more) in a row, only the latest or earliest (default latest) one is kept.
    All newly-consecutive USER messages will be merged into a single USER message, merging audio as necessary.
    """

    def __init__(self, *args, max_merges=3, keep: Literal["last", "first"] = "last", **kwargs):
        """
        :param max_merges: The maximum number of user messages to merge into a single message.
        :param keep: If multiple consecutive duplicates are encountered, whether to keep the last one (default)
            or the first one.
        """
        super().__init__(*args, **kwargs)
        self.max_merges = max_merges
        self.keep = keep

    def _deduplicate_keep_last(self, messages: list[ChatMessage]) -> list[ChatMessage]:
        new_messages = []
        last_assistant_content = None
        merges = 0

        # deduplicate in reverse
        for msg in reversed(messages):
            if not msg.role == ChatRole.ASSISTANT:
                # merge consecutive user msgs
                if (
                    merges < self.max_merges
                    and msg.role == ChatRole.USER
                    and new_messages
                    and new_messages[-1].role == ChatRole.USER
                ):
                    # msg is the older one, so prepend it to new_messages[-1]
                    new_messages[-1] = merge_user_messages(msg, new_messages[-1])
                    merges += 1
                else:
                    new_messages.append(msg)
                    merges = 0
                continue

            # yeet duplicate asst messages
            if last_assistant_content and msg.content == last_assistant_content:
                log.debug(f"Deduplicated content: {msg.content!r}")
                continue
            last_assistant_content = msg.content
            new_messages.append(msg)
            merges = 0

        new_messages.reverse()
        return new_messages

    def _deduplicate_keep_first(self, messages: list[ChatMessage]) -> list[ChatMessage]:
        new_messages = []
        last_assistant_content = None
        merges = 0

        # deduplicate in reverse
        for msg in messages:
            if not msg.role == ChatRole.ASSISTANT:
                # merge consecutive user msgs
                if (
                    merges < self.max_merges
                    and msg.role == ChatRole.USER
                    and new_messages
                    and new_messages[-1].role == ChatRole.USER
                ):
                    # msg is the newer one, so append it to new_messages[-1]
                    new_messages[-1] = merge_user_messages(new_messages[-1], msg)
                    merges += 1
                else:
                    new_messages.append(msg)
                    merges = 0
                continue

            # yeet duplicate asst messages
            if last_assistant_content and msg.content == last_assistant_content:
                log.debug(f"Deduplicated content: {msg.content!r}")
                continue
            last_assistant_content = msg.content
            new_messages.append(msg)
            merges = 0

        return new_messages

    async def predict(self, messages, functions=None, **hyperparams):
        if self.keep == "last":
            deduped_messages = self._deduplicate_keep_last(messages)
        else:
            deduped_messages = self._deduplicate_keep_first(messages)
        return await self.engine.predict(deduped_messages, functions, **hyperparams)

    async def stream(self, messages, functions=None, **hyperparams):
        if self.keep == "last":
            deduped_messages = self._deduplicate_keep_last(messages)
        else:
            deduped_messages = self._deduplicate_keep_first(messages)
        async for elem in self.engine.stream(deduped_messages, functions, **hyperparams):
            yield elem


def merge_user_messages(older: ChatMessage, newer: ChatMessage):
    parts = []
    # merge consecutive audioparts together
    for part in itertools.chain(older.parts, newer.parts):
        if parts and isinstance(part, interop.AudioPart) and isinstance(parts[-1], interop.AudioPart):
            transcript = f'{part.transcript or ""}\n{parts[-1].transcript or ""}'.strip()
            audio_b64 = base64.b64encode(part.audio_bytes + parts[-1].audio_bytes)
            parts[-1] = parts[-1].copy_with(audio_b64=audio_b64, transcript=transcript)
        else:
            parts.append(part)
    return newer.copy_with(parts=parts)


# conv = [
#     ChatMessage.user("hello world"),
#     ChatMessage.assistant("hi"),
#     ChatMessage.user("hello world2"),
#     ChatMessage.assistant("hi"),
#     ChatMessage.user("hello world2"),
#     ChatMessage.assistant("hi2"),
#     ChatMessage.user("hello world"),
#     ChatMessage.assistant("hi3"),
# ]
# DeduplicateMessages._deduplicate(conv)

# conv = [
#     ChatMessage.user([interop.AudioPart(oai_type="audio", audio_b64="AAA=", transcript=None)]),
#     ChatMessage.assistant("hi"),
#     ChatMessage.user([interop.AudioPart(oai_type="audio", audio_b64="AAA=", transcript=None)]),
#     ChatMessage.assistant("hi"),
#     ChatMessage.user("hello world2"),
#     ChatMessage.assistant("hi2"),
# ]
# DeduplicateMessages._deduplicate(conv)


class ResetContextOnDuplicatesMixin(BaseKani):
    """
    A moderately cursed Kani mixin that will reset the chat context if N consecutive duplicates
    (i.e., N+1 of the same message in a row) are detected.
    """

    def __init__(self, *args, max_consecutive_duplicates=2, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_consecutive_duplicates = max_consecutive_duplicates

        # duplicate tracking
        self._last_asst_content = None
        self._seen_duplicates = 0
        self._chat_history_start_idx = 0

    async def add_completion_to_history(self, completion):
        message = await super().add_completion_to_history(completion)
        # when we get a new completion, check if it's a duplicate of the last one
        if message.content == self._last_asst_content:
            self._seen_duplicates += 1
            # if it is and we have seen too many duplicates, kill the chat context and dispatch an event
            if self._seen_duplicates >= self.max_consecutive_duplicates:
                self._chat_history_start_idx = len(self.chat_history)
                self.dispatch(
                    events.ClientEventLog(
                        key="chat_history_reset", data={"reason": "duplicates", "duplicates": self._seen_duplicates}
                    )
                )
                log.warning(
                    f"{self.max_consecutive_duplicates+1} duplicate messages seen in a row, resetting chat history!"
                )
                self._seen_duplicates = 0
                self._last_asst_content = None
        else:
            self._seen_duplicates = 0
            self._last_asst_content = message.content
        return message

    async def get_prompt(self) -> list[ChatMessage]:
        """
        Called each time before asking the LM engine for a completion to generate the chat prompt.
        Returns a list of messages such that the total token count in the messages is less than
        ``(self.max_context_size - self.desired_response_tokens)``.

        Always includes the system prompt plus any always_included_messages at the start of the prompt.

        You may override this to get more fine-grained control over what is exposed in the model's memory at any given
        call.
        """
        always_len = self.always_len
        remaining = max_size = self.max_context_size - always_len
        total_tokens = 0
        to_keep = 0  # messages to keep from the end of chat history
        for message in reversed(self.chat_history[self._chat_history_start_idx :]):
            # get and check the message's length
            message_len = self.message_token_len(message)
            if message_len > max_size:
                func_help = (
                    ""
                    if message.role != ChatRole.FUNCTION
                    else "You may set `auto_truncate` in the @ai_function to automatically truncate long responses.\n"
                )
                raise MessageTooLong(
                    "The chat message's size is longer than the allowed context window (after including system"
                    " messages, always included messages, and desired response tokens).\n"
                    f"{func_help}Content: {message.text[:100]}..."
                )
            # see if we can include it
            remaining -= message_len
            if remaining >= 0:
                total_tokens += message_len
                to_keep += 1
            else:
                break
        log.debug(
            f"get_prompt() returned {always_len + total_tokens} tokens ({always_len} always) in"
            f" {len(self.always_included_messages) + to_keep} messages"
            f" ({len(self.always_included_messages)} always)"
        )
        if not to_keep:
            return self.always_included_messages
        return self.always_included_messages + self.chat_history[-to_keep:]
