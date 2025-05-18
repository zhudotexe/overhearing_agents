import asyncio
import base64
import logging
import time
from contextlib import contextmanager
from typing import Any, AsyncIterable, Callable, Optional, TYPE_CHECKING

import openai.types.beta.realtime as oait
from kani import ChatMessage, ChatRole, Kani
from kani.engines.base import BaseCompletion
from kani.engines.openai import OpenAIEngine
from kani.engines.openai.translation import ChatCompletion
from kani.ext.realtime import OpenAIRealtimeKani
from kani.ext.realtime._internal import create_task, ensure_async
from kani.ext.realtime.interop import AudioPart, chat_history_from_session_state
from kani.ext.realtime.session import ConnectionState, RealtimeSession
from kani.streaming import StreamManager

from overhearing_agents import events
from overhearing_agents.state import AIFunctionState, KaniState, RunState
from overhearing_agents.utils import create_kani_id, get_chat_history_audio_len

if TYPE_CHECKING:
    from overhearing_agents.session import OverhearingAgentsSession

log = logging.getLogger(__name__)


class BaseKani(Kani):
    """
    Base class for all kani in the application, regardless of recursive delegation.

    Extends :class:`kani.Kani`. See the Kani documentation for more details on the internal chat state and LLM
    interface.
    """

    def __init__(
        self,
        *args,
        parent: "BaseKani" = None,
        id: str = None,
        name: str = None,
        **kwargs,
    ):
        """
        :param parent: The parent of this kani, or ``None`` if this is the root of a system.
        :param id: The internal ID of this kani. If not passed, generates a UUID.
        :param name: The human-readable name of this kani. If not passed, uses the ID.
        """
        super().__init__(*args, **kwargs)
        self.state = RunState.STOPPED
        self._old_state_stack = []
        # tree management
        if parent is not None:
            self.depth = parent.depth + 1
        else:
            self.depth = 0
        self.parent = parent
        self.children = {}
        # app management
        self.id = create_kani_id() if id is None else id
        self.name = self.id if name is None else name
        self.pa_session: Optional["OverhearingAgentsSession"] = None

    # ==== session lifecycle ====
    async def join_session(self, session: "OverhearingAgentsSession"):
        """Register this kani instance to a session."""
        self.pa_session = session
        session.on_kani_creation(self)

    def dispatch(self, event: events.BaseEvent):
        if self.pa_session is None:
            return
        self.pa_session.dispatch(event)

    async def init(self):
        """Used to do various setup tasks. Overload this in impl subclasses."""
        pass

    # ==== overrides ====
    async def get_model_completion(self, include_functions: bool = True, **kwargs) -> BaseCompletion:
        # if include_functions is False but we have functions and are using an OpenAIEngine, we should set
        # tool_choice="none" instead -- this prevents the API from exploding if we set parallel_tool_calls
        if self.functions and (not include_functions) and isinstance(self.engine, OpenAIEngine):
            include_functions = True
            kwargs["tool_choice"] = "none"

        return await super().get_model_completion(include_functions=include_functions, **kwargs)

    async def get_model_stream(self, include_functions: bool = True, **kwargs) -> AsyncIterable[str | BaseCompletion]:
        # same as above for streaming
        if self.functions and (not include_functions) and isinstance(self.engine, OpenAIEngine):
            include_functions = True
            kwargs["tool_choice"] = "none"

        async for elem in super().get_model_stream(include_functions=include_functions, **kwargs):
            yield elem

    async def chat_round(self, *args, **kwargs):
        with self.run_state(RunState.RUNNING):
            return await super().chat_round(*args, **kwargs)

    def chat_round_stream(self, *args, **kwargs) -> StreamManager:
        stream = super().chat_round_stream(*args, **kwargs)

        # consume from the inner StreamManager and re-yield with bookkeeping
        async def _impl():
            with self.run_state(RunState.RUNNING):
                async for token in stream:
                    yield token
                    self.dispatch(
                        events.StreamDelta(id=self.id, is_root=self.parent is None, delta=token, role=stream.role)
                    )
                yield await stream.completion()

        return StreamManager(_impl(), role=stream.role)

    async def full_round(self, *args, **kwargs):
        with self.run_state(RunState.RUNNING):
            async for msg in super().full_round(*args, **kwargs):
                yield msg

    async def full_round_stream(self, *args, **kwargs) -> AsyncIterable[StreamManager]:
        with self.run_state(RunState.RUNNING):
            async for stream in super().full_round_stream(*args, **kwargs):
                # consume from the inner StreamManager and re-yield with bookkeeping
                async def _impl(s):
                    async for token in s:
                        yield token
                        self.dispatch(
                            events.StreamDelta(id=self.id, is_root=self.parent is None, delta=token, role=s.role)
                        )
                    yield await s.completion()

                yield StreamManager(_impl(stream), role=stream.role)

    async def add_to_history(self, message: ChatMessage):
        await super().add_to_history(message)
        self.dispatch(events.KaniMessage(id=self.id, msg=message))
        if self.parent is None:
            self.dispatch(events.RootMessage(msg=message))

    async def add_completion_to_history(self, completion):
        message = await super().add_completion_to_history(completion)
        self.dispatch(
            events.TokensUsed(
                id=self.id, prompt_tokens=completion.prompt_tokens, completion_tokens=completion.completion_tokens
            )
        )
        if isinstance(completion, ChatCompletion) and completion.openai_completion.usage:
            self.dispatch(
                events.DetailedTokensUsed(id=self.id, usage=completion.openai_completion.usage.model_dump(mode="json"))
            )
        # HACK: sometimes openai's function calls are borked; we fix them here
        if message.tool_calls:
            for tc in message.tool_calls:
                if (function_call := tc.function) and function_call.name.startswith("functions."):
                    function_call.name = function_call.name.removeprefix("functions.")
        return message

    # ==== utils ====
    @property
    def last_user_message(self) -> ChatMessage | None:
        """The most recent USER message in this kani's chat history, if one exists."""
        return next((m for m in reversed(self.chat_history) if m.role == ChatRole.USER), None)

    @property
    def last_assistant_message(self) -> ChatMessage | None:
        """The most recent ASSISTANT message in this kani's chat history, if one exists."""
        return next((m for m in reversed(self.chat_history) if m.role == ChatRole.ASSISTANT), None)

    def get_save_state(self, **kwargs) -> KaniState:
        """Get a Pydantic state suitable for saving/loading."""
        return KaniState(
            id=self.id,
            depth=self.depth,
            parent=self.parent.id if self.parent else None,
            children=list(self.children),
            always_included_messages=self.always_included_messages,
            chat_history=self.chat_history,
            state=self.state,
            name=self.name,
            engine_type=type(self.engine).__name__,
            engine_repr=repr(self.engine),
            functions=[AIFunctionState.from_aifunction(f) for f in self.functions.values()],
            **kwargs,
        )

    # --- state utils ---
    def set_run_state(self, state: RunState):
        """Set the run state and dispatch the event."""
        # noop if we're already in that state
        if self.state == state:
            return
        self.state = state
        self.dispatch(events.KaniStateChange(id=self.id, state=self.state))

    @contextmanager
    def run_state(self, state: RunState):
        """Run the body of this statement with a different run state then set it back after."""
        self._old_state_stack.append(self.state)
        self.set_run_state(state)
        try:
            yield
        finally:
            self.set_run_state(self._old_state_stack.pop())

    async def cleanup(self):
        """This kani may run again but is done for now; clean up any ephemeral resources but save its state."""
        pass

    async def close(self):
        """The application is shutting down and all resources should be gracefully cleaned up."""
        pass


class BaseRealtimeKani(BaseKani, OpenAIRealtimeKani):
    def __init__(
        self,
        *args,
        realtime_reconnect_after_secs: float | None = 60 * 15,
        realtime_reconnect_reupload_secs: float = 180,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.session.add_lifecycle_listener(self._on_connection_state_change)
        self.session.add_listener(self._on_event)
        self._realtime_reconnect_after_secs = realtime_reconnect_after_secs
        self._realtime_reconnect_reupload_secs = realtime_reconnect_reupload_secs
        self._realtime_connected_at = 0
        self._backup_chat_history = []

    @OpenAIRealtimeKani.chat_history.getter
    def chat_history(self):
        return self._backup_chat_history + super().chat_history

    async def _on_event(self, event: oait.RealtimeServerEvent):
        if isinstance(event, oait.ResponseDoneEvent):
            self.dispatch(events.DetailedTokensUsed(id=self.id, usage=event.response.usage.model_dump(mode="json")))

    # ==== lifecycle ====
    async def reconnect(self, retry_attempts: int = 5):
        """
        Close the existing WS, optionally copy all conversational history to another WS session, and connect to it

        :param retry_attempts: the number of times to retry with exponential backoff (if the connection fails)
        """
        retry_attempts = max(retry_attempts, 1)
        # if we somehow have failed to connect, don't copy the chat session etc
        if not self.session.has_connected_once:
            raise RuntimeError("gotta connect at least once before reconnecting")
        reconnect_start = time.time()
        # copy chat history and config from the old session to memory
        self._backup_chat_history.extend(chat_history_from_session_state(self.session))
        session_config = self.session.session_config.model_dump(
            include=(
                "input_audio_format",
                "input_audio_transcription",
                "instructions",
                "max_response_output_tokens",
                "modalities",
                "model",
                "output_audio_format",
                "temperature",
                "tool_choice",
                "tools",
                "turn_detection",
                "voice",
            )
        )
        model = self.session.session_config.model

        # decide how much of the history to keep, and move it from backup
        if not self._realtime_reconnect_reupload_secs:
            self._chat_history = []
            accumulated_duration = 0.0
        else:
            slice_idx = 0
            accumulated_duration = 0.0
            for idx, msg in enumerate(reversed(self._backup_chat_history)):
                for part in msg.parts:
                    if isinstance(part, AudioPart):
                        accumulated_duration += part.audio_duration
                # this always breaks after a user, so the reuploaded history will always start on USER
                if accumulated_duration >= self._realtime_reconnect_reupload_secs and msg.role == ChatRole.USER:
                    slice_idx = len(self._backup_chat_history) - (idx + 1)
                    break
            self._chat_history = self._backup_chat_history[slice_idx:]
            del self._backup_chat_history[slice_idx:]

        # replace the underlying session
        old_session = self.session
        self.session = RealtimeSession(model=model, client=self.client)
        self.session.listeners = old_session.listeners
        self.session.lifecycle_listeners = old_session.lifecycle_listeners
        # connect with N retries with exponential backoff
        for retry_idx in range(retry_attempts):
            try:
                await self.connect(**session_config)
            except Exception as e:
                if retry_idx == retry_attempts:
                    log.error(f"Failed to reconnect after {retry_attempts} attempts!", exc_info=e)
                    raise
                sleep_for = 2**retry_idx
                log.warning(
                    f"Failed to reconnect (attempt {retry_idx + 1} of {retry_attempts}), sleeping for"
                    f" {sleep_for} sec...",
                    exc_info=e,
                )
                await asyncio.sleep(sleep_for)
            else:
                break

        await old_session.close()
        log.info(f"Reconnected and reuploaded {accumulated_duration}s of audio in {time.time() - reconnect_start}s.")

    async def _on_connection_state_change(self, old_state: ConnectionState, new_state: ConnectionState):
        if old_state == ConnectionState.CONNECTED and new_state == ConnectionState.DISCONNECTED:
            log.warning("Realtime session WS disconnected, attempting to reconnect...")
            task = create_task(self.reconnect(retry_attempts=12))
            await asyncio.shield(task)
        elif new_state == ConnectionState.CONNECTED:
            self._realtime_connected_at = time.time()

    async def _check_reconnect(self):
        """
        If it has been enough time since we connected to the realtime WS, reconnect
        Also reconnect if the context is longer than the reconnect time (usually in cases of batch querying)
        """
        now = time.time()
        if now - self._realtime_connected_at > self._realtime_reconnect_after_secs:
            log.info(f"Last reconnect was {now - self._realtime_connected_at:.2f} sec ago, reconnecting...")
            await self.reconnect(retry_attempts=12)  # I really do not want this disconnecting lol
        elif (
            audio_history_duration := get_chat_history_audio_len(chat_history_from_session_state(self.session))
        ) > self._realtime_reconnect_after_secs:
            log.info(f"Chat history audio duration is {audio_history_duration:.2f} sec, reconnecting...")
            await self.reconnect(retry_attempts=12)  # I really do not want this disconnecting lol

    async def close(self):
        self.session.remove_lifecycle_listener(self._on_connection_state_change)
        return await super().close()

    # ==== overrides ====
    # check for a reconnect time before doing queries
    async def chat_round(self, *args, **kwargs):
        await self._check_reconnect()
        return await super().chat_round(*args, **kwargs)

    def chat_round_stream(self, *args, **kwargs) -> StreamManager:
        stream = super().chat_round_stream(*args, **kwargs)

        async def _impl():
            await self._check_reconnect()
            async for token in stream:
                yield token
            yield await stream.completion()

        return StreamManager(_impl(), role=stream.role)

    async def full_round(self, *args, **kwargs):
        await self._check_reconnect()
        async for msg in super().full_round(*args, **kwargs):
            yield msg

    async def full_round_stream(self, *args, **kwargs) -> AsyncIterable[StreamManager]:
        await self._check_reconnect()
        async for stream in super().full_round_stream(*args, **kwargs):
            yield stream

    async def full_duplex(
        self,
        audio_stream: AsyncIterable[bytes],
        audio_callback: Callable[[bytes], Any] = None,
        **kwargs,
    ) -> AsyncIterable[StreamManager]:
        # wrap the audio callback to emit audio delta events if we get them
        if audio_callback is None:

            async def wrapped_audio_callback(data):
                self.dispatch(events.OutputAudioDelta(id=self.id, delta=base64.b64encode(data).decode()))

        else:
            audio_callback = ensure_async(audio_callback)

            async def wrapped_audio_callback(data):
                self.dispatch(events.OutputAudioDelta(id=self.id, delta=base64.b64encode(data).decode()))
                await audio_callback(data)

        # main call to full_duplex
        async for stream in super().full_duplex(audio_stream, wrapped_audio_callback, **kwargs):
            # consume from the inner StreamManager and re-yield with bookkeeping
            async def _impl(s):
                async for token in s:
                    yield token
                    self.dispatch(events.StreamDelta(id=self.id, is_root=self.parent is None, delta=token, role=s.role))
                yield await s.completion()

            yield StreamManager(_impl(stream), role=stream.role)
