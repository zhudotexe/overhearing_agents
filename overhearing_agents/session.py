import asyncio
import base64
import logging
import time
import uuid
from collections.abc import AsyncIterable
from pathlib import Path
from typing import Any, Awaitable, Callable
from weakref import WeakValueDictionary

from kani import ChatRole
from kani.ext.realtime.interop import AudioPart

from overhearing_agents.kanis.base import BaseKani, BaseRealtimeKani
from . import events
from .eventlogger import EventLogger
from .state import Suggestion
from .utils import ainput, print_event, round_events

log = logging.getLogger(__name__)


class OverhearingAgentsSession:
    """
    Main application framework - event dispatch/logging.
    """

    def __init__(
        self,
        root_kani: BaseKani,
        *,
        # config
        max_function_rounds: int | None = None,
        # logging
        log_dir: Path = None,
        clear_existing_log: bool = False,
        session_id: str = None,
    ):
        """
        :param log_dir: A path to a directory to save logs for this session. Defaults to
            ``logs/instances/{session_id}/``.
        :param clear_existing_log: If the log directory has existing events, clear them before writing new events.
            Otherwise, append to existing events.
        :param session_id: The ID of this session. Generally this should not be set manually; it is used for loading
            previous states.
        """
        # internals
        self._init_lock = asyncio.Lock()

        # config
        self.max_function_rounds = max_function_rounds

        # events
        self.listeners = []
        self.event_queue = asyncio.Queue()
        self.dispatch_task = None
        # state
        self.session_id = session_id or f"{int(time.time())}-{uuid.uuid4()}"
        # logging
        self.logger = EventLogger(self, self.session_id, log_dir=log_dir, clear_existing_log=clear_existing_log)
        self.add_listener(self.logger.log_event)
        # kanis
        self.root_kani = root_kani
        self.kanis = WeakValueDictionary()

        # overhearing_agents state
        # adding new synced stateful attrs here? make sure to also add it to
        # server/models, server/session_manager, and eventlogger
        self.suggestion_history: list[Suggestion] = []

    async def ensure_init(self):
        """Called at least once before any messaging happens. Used to do async init. Must be idempotent."""
        async with self._init_lock:  # lock in case of parallel calls - no double creation
            if self.dispatch_task is None:
                self.dispatch_task = asyncio.create_task(self._dispatch_task(), name=f"dispatch-{self.session_id}")
            if self.root_kani.pa_session is None:
                await self.root_kani.join_session(self)
            elif self.root_kani.pa_session is not self:
                raise ValueError("Kanis cannot be reused in multiple sessions!")
            await self.root_kani.init()
        return self.root_kani

    # === entrypoints ===
    # --- non-realtime ---
    async def chat_from_queue(self, q: asyncio.Queue[events.UserEventT], streaming_audio_chunk_duration=5.0):
        """Get chat messages from a provided queue. Used internally in the visualization server."""
        await self.ensure_init()

        # if we're using a realtime kani, make sure we log the events
        if isinstance(self.root_kani, BaseRealtimeKani):
            if not self.root_kani.is_connected:
                raise RuntimeError("connect first")
            # add a listener for realtime events
            if self.logger.log_realtime_event not in self.root_kani.session.listeners:
                self.root_kani.session.add_listener(self.logger.log_realtime_event)

        # set up a b64 buffer for streaming input
        audio_buffer = bytearray()
        streaming_chunk_duration_b64_len = streaming_audio_chunk_duration * 48000  # 48kB bytes = 1 sec

        # main loop
        try:
            while True:
                try:
                    user_event = await q.get()
                    log.debug(f"Event from queue: {user_event!r}")
                    self.dispatch(user_event)
                    match user_event:
                        case events.SendMessage(content=content):
                            query = content
                        case events.SendAudioMessage(
                            text_prefix=text_prefix, text_suffix=text_suffix, data_b64=audio_b64
                        ):
                            query = []
                            if text_prefix:
                                query.append(text_prefix)
                            query.append(AudioPart(oai_type="input_audio", transcript=None, audio_b64=audio_b64))
                            if text_suffix:
                                query.append(text_suffix)
                        case events.InputAudioDelta(data_b64=audio_b64):
                            audio_buffer.extend(base64.b64decode(audio_b64))
                            if len(audio_buffer) >= streaming_chunk_duration_b64_len and q.empty():
                                query = [
                                    AudioPart(
                                        oai_type="input_audio",
                                        transcript=None,
                                        audio_b64=base64.b64encode(audio_buffer).decode(),
                                    )
                                ]
                                audio_buffer.clear()
                            else:
                                continue
                        case e:
                            log.debug(f"Got unhandled user event: {e}")
                            continue
                    async for stream in self.root_kani.full_round_stream(
                        query, max_function_rounds=self.max_function_rounds
                    ):
                        msg = await stream.message()
                        if msg.role == ChatRole.ASSISTANT:
                            log.debug(f"AI: {msg}")
                    self.dispatch(events.RoundComplete(session_id=self.session_id))
                    await self.logger.write_state()  # save after each round
                except asyncio.CancelledError:
                    log.debug("chat_from_queue cancelled")
                    raise
                except Exception as e:
                    log.exception("Error in chat_from_queue:")
                    self.dispatch(events.Error.from_exc(e))
                    await self.logger.write_state()  # save after errors
        finally:
            await self.logger.write_state()  # autosave on exit

    def chat_session(self, **kwargs) -> "SessionChatManager":
        return SessionChatManager(self, **kwargs)

    async def chat_in_terminal(self):
        """Chat with the defined system in the terminal. Prints function calls and root messages to the terminal."""
        try:
            async with self.chat_session() as s:
                while True:
                    query = await ainput("USER: ")
                    query = query.strip()
                    print("AI: ", end="")
                    async for event in s.query(query, only_loggable=False):
                        print_event(event)
        except (KeyboardInterrupt, asyncio.CancelledError):
            await self.close()

    async def query_one(self, query: str, only_loggable=True) -> AsyncIterable[events.BaseEvent]:
        """Run one round with the given query. If a multi-round conversation is needed, use :meth:`.chat_session`.

        Yields all loggable events from the app (i.e. no stream deltas) during the query. To get only messages
        from the root, filter for `events.RootMessage`.
        """
        async with self.chat_session() as s:
            async for event in s.query(query, only_loggable=only_loggable):
                yield event

    # --- audio - non-realtime ---
    async def query_one_audio(self, audio: bytes, only_loggable=True) -> AsyncIterable[events.BaseEvent]:
        """
        Run one round with the given audio query. If a multi-round conversation is needed, use :meth:`.chat_session`.

        Yields all loggable events from the app (i.e. no stream deltas) during the query.
        """
        async with self.chat_session() as s:
            async for event in s.query_audio(audio, only_loggable=only_loggable):
                yield event

    async def stream_audio(
        self, audio_stream: AsyncIterable[bytes], only_loggable=True, send_audio_every=5.0
    ) -> AsyncIterable[events.BaseEvent]:
        """
        Play the given audio stream to the model, allowing it to generate a response after each element in the stream.
        Controls audio chunking on our side.

        Yields all loggable events from the app (i.e. no stream deltas) during the query.
        """
        await self.ensure_init()

        in_q = asyncio.Queue()
        out_q = asyncio.Queue()
        chat_task = asyncio.create_task(self.chat_from_queue(in_q, streaming_audio_chunk_duration=send_audio_every))
        self.add_listener(out_q.put)

        try:
            async for data in audio_stream:
                await in_q.put(events.InputAudioDelta(data_b64=base64.b64encode(data).decode()))
                while not out_q.empty():
                    event = await out_q.get()
                    if event.__log_event__ or not only_loggable:
                        yield event
                    if isinstance(event, events.Error):
                        raise event.exc
        finally:
            self.remove_listener(out_q.put)
            chat_task.cancel()

    async def chat_in_terminal_audio(self, mic_id: int, send_audio_every=5.0):
        """Chat with the defined system in the terminal. Prints function calls and root messages to the terminal."""
        import easyaudiostream

        try:
            async for event in self.stream_audio(
                easyaudiostream.get_mic_stream_async(mic_id), only_loggable=False, send_audio_every=send_audio_every
            ):
                print_event(event)
        finally:
            await self.close()

    # --- audio - realtime ---
    async def chat_from_queue_realtime(self, q: asyncio.Queue[events.UserEventT], audio_callback=None):
        """Get chat messages from a provided queue. Used internally in the visualization server."""
        await self.ensure_init()

        if not isinstance(self.root_kani, BaseRealtimeKani):
            raise TypeError("use a realtime kani")
        if not self.root_kani.is_connected:
            raise RuntimeError("connect first")

        # add a listener for realtime events
        if self.logger.log_realtime_event not in self.root_kani.session.listeners:
            self.root_kani.session.add_listener(self.logger.log_realtime_event)

        # create the actual iterator for audio input by filtering InputAudioDelta from the input queue
        async def audio_events():
            while True:
                user_event = await q.get()
                log.debug(f"Event from queue: {user_event!r}")
                self.dispatch(user_event)
                if isinstance(user_event, events.InputAudioDelta):
                    yield user_event.data

        # needed to make sure stream events are emitted
        _dummies = set()

        def dummy_consume_stream(s):
            async def _impl():
                async for _ in s:
                    pass

            t = asyncio.create_task(_impl())
            _dummies.add(t)
            t.add_done_callback(_dummies.discard)

        # main loop
        try:
            async for stream in self.root_kani.full_duplex(audio_events(), audio_callback):
                dummy_consume_stream(stream)  # needed to make sure stream events are emitted
        except asyncio.CancelledError:
            log.debug("chat_from_queue cancelled")
            raise
        except Exception as e:
            log.exception("Error in chat_from_queue:")
            self.dispatch(events.Error.from_exc(e))
        finally:
            await self.logger.write_state()  # autosave
            self.root_kani.session.remove_listener(self.logger.log_realtime_event)

    async def chat_in_terminal_realtime(self, mic_id: int):
        """Chat with the defined system in the terminal. Prints function calls and root messages to the terminal."""
        import easyaudiostream

        await self.ensure_init()
        if not isinstance(self.root_kani, BaseRealtimeKani):
            raise TypeError("use a realtime kani")
        if not self.root_kani.is_connected:
            raise RuntimeError("connect first")

        # create a queue to send events to the server and start server
        in_q = asyncio.Queue()
        chat_task = asyncio.create_task(self.chat_from_queue_realtime(in_q))
        root_id = self.root_kani.id

        # create a listener to print events
        async def handle_event(event):
            # if not isinstance(event, (events.InputAudioDelta, events.OutputAudioDelta)):
            #     print(event)
            match event:
                # case events.StreamDelta(id=id, role=ChatRole.ASSISTANT, delta=part) if id == root_id:
                #     print(part, end="", flush=True)
                case events.OutputAudioDelta(id=id, delta=part) if id == root_id:
                    easyaudiostream.play_raw_audio(base64.b64decode(part))
                case events.RootMessage(msg=msg) if msg.role == ChatRole.ASSISTANT:
                    # print()  # end of stream
                    # if text := assistant_message_thinking(msg, show_args=True):
                    #     print(f"AI: {text}")
                    print(f"AI: {msg.text}")
                case events.RootMessage(msg=msg) if msg.role == ChatRole.FUNCTION:
                    print(f"FUNC: {msg.text}")
                case events.RootMessage(msg=msg) if msg.role == ChatRole.USER:
                    print(f"USER: {msg.text}")

        self.add_listener(handle_event)

        try:
            # in loop, send frames
            audio_stream = easyaudiostream.get_mic_stream_async(mic_id)
            async for frame in audio_stream:
                await in_q.put(events.InputAudioDelta(data_b64=base64.b64encode(frame).decode()))
        except (KeyboardInterrupt, asyncio.CancelledError):
            chat_task.cancel()
            await self.close()
            return
        finally:
            self.remove_listener(handle_event)

    # === events ===
    def add_listener(self, callback: Callable[[events.BaseEvent], Awaitable[Any]]):
        """
        Add a listener which is called for every event dispatched by the system.
        The listener must be an asynchronous function that takes in an event in a single argument.
        """
        self.listeners.append(callback)

    def remove_listener(self, callback):
        """Remove a listener added by :meth:`add_listener`."""
        self.listeners.remove(callback)

    async def wait_for(
        self,
        event_type: str,
        predicate: Callable[[events.BaseEvent], bool] = None,
        timeout: float = 60,
        raise_on_exc: bool = False,
    ) -> events.BaseEvent:
        """
        Wait for the next event of a given type, and return it.

        :param raise_on_exc: If True, raise for any Error event.
        """
        future = asyncio.get_running_loop().create_future()

        async def waiter(e: events.BaseEvent):
            if e.type == event_type and (predicate is None or predicate(e)):
                future.set_result(e)
            # raise an applicable Error
            elif isinstance(e, events.Error) and raise_on_exc:
                future.set_exception(e.exc)

        try:
            self.add_listener(waiter)
            return await asyncio.wait_for(future, timeout)
        finally:
            self.remove_listener(waiter)

    async def _dispatch_task(self):
        while True:
            event = await self.event_queue.get()
            # noinspection PyBroadException
            try:
                # get listeners, call them
                results = await asyncio.gather(
                    *(callback(event) for callback in self.listeners), return_exceptions=True
                )
                # log exceptions
                for r in results:
                    if isinstance(r, BaseException):
                        log.exception("Exception in event dispatch:", exc_info=r)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Exception when dispatching event:")
            finally:
                self.event_queue.task_done()

    def dispatch(self, event: events.BaseEvent):
        """Dispatch an event to all listeners.
        Technically this just adds it to a queue and then an async background task dispatches it."""
        self.event_queue.put_nowait(event)

    async def drain(self):
        """Wait until all events have finished processing."""
        await self.event_queue.join()

    # --- kani lifecycle ---
    def on_kani_creation(self, ai: BaseKani):
        """Called by the overhearing_agents kani constructor.
        Registers a new kani in the app, handles parent-child bookkeeping, and dispatches a KaniSpawn event."""
        self.kanis[ai.id] = ai
        if ai.parent:
            ai.parent.children[ai.id] = ai
        self.dispatch(events.KaniSpawn(state=ai.get_save_state()))

    # === resources + app lifecycle ===
    async def close(self):
        """Clean up all the app resources."""
        log.debug("session closing...")
        self.dispatch(events.SessionClose(session_id=self.session_id))
        await self.drain()
        if self.dispatch_task is not None:
            self.dispatch_task.cancel()
        await asyncio.gather(
            self.logger.close(),
            *(k.close() for k in self.kanis.values()),
        )


class SessionChatManager:
    """
    Context manager to manage a continuous chat. Like server.SessionManager but for local queries.

    Should not be constructed manually - use :meth:`.PassiveAgentsSession.chat_session` instead.
    """

    def __init__(self, pa_session: OverhearingAgentsSession, *, autoraise=True):
        self.pa_session = pa_session
        self.autoraise = autoraise
        self.in_q = None
        self.chat_task = None

    async def __aenter__(self):
        await self.pa_session.ensure_init()
        self.in_q = asyncio.Queue()
        self.chat_task = asyncio.create_task(self.pa_session.chat_from_queue(self.in_q))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.pa_session.drain()
        self.chat_task.cancel()

    async def query(self, query: str, only_loggable=True) -> AsyncIterable[events.BaseEvent]:
        """
        Run one round with the given query.

        Yields all loggable events from the app (i.e. no stream deltas) during the query. To get only messages
        from the root, filter for `events.RootMessage`.
        """
        async with round_events(self.pa_session, only_loggable=only_loggable, autoraise=self.autoraise) as rnd:
            await self.in_q.put(events.SendMessage(content=query))
            async for event in rnd:
                yield event

    async def query_audio(self, audio: bytes, only_loggable=True) -> AsyncIterable[events.BaseEvent]:
        """
        Send the given audio query to the session.

        Yields all loggable events from the app (i.e. no stream deltas) during the query.
        """
        async with round_events(self.pa_session, only_loggable=only_loggable, autoraise=self.autoraise) as rnd:
            await self.in_q.put(events.SendAudioMessage(data_b64=base64.b64encode(audio).decode()))
            async for event in rnd:
                yield event
