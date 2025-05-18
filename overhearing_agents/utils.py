import asyncio
import contextlib
import itertools
import json
import sys
import uuid
from typing import ClassVar, Dict, Iterable, Type, TypeVar

from kani import ChatMessage, ChatRole
from kani.ext.realtime import interop
from kani.utils.message_formatters import assistant_message_contents_thinking, assistant_message_thinking
from pydantic import BaseModel, model_validator
from pydantic_core.core_schema import ValidationInfo

from overhearing_agents import events

T = TypeVar("T")


def create_kani_id() -> str:
    """Create a unique identifier for a kani."""
    return str(uuid.uuid4())


def batched(iterable: Iterable[T], n: int) -> Iterable[tuple[T, ...]]:
    # batched('ABCDEFG', 3) --> ABC DEF G
    if n < 1:
        raise ValueError("n must be at least one")
    it = iter(iterable)
    while batch := tuple(itertools.islice(it, n)):
        yield batch


def read_jsonl(fp) -> Iterable[dict]:
    """
    Yield JSON objects from the JSONL file at the given path.

    .. note::
        This function returns an iterator, not a list -- to read a full JSONL file into memory, use
        ``list(read_jsonl(...))``.
    """
    with open(fp, encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


async def ainput(string: str) -> str:
    """input(), but async."""
    print(string, end="", flush=True)
    return (await asyncio.to_thread(sys.stdin.readline)).rstrip("\n")


@contextlib.asynccontextmanager
async def round_events(session, only_loggable=True, autoraise=True):
    """
    Get an iterator that yields all events in a session until the end of the current round.

    Usage::

        in_q = asyncio.Queue()
        chat_task = asyncio.create_task(self.chat_from_queue(in_q))

        async with round_events(self) as rnd:
            await in_q.put(events.SendMessage(content=query))
            async for event in rnd:
                # do something with the event

    :param session: The session
    :param only_loggable: Whether to emit only loggable events, or all events (e.g. streaming deltas)
    :param autoraise: Whether to raise exceptions from the chat loop in the calling scope.
    """
    # register a new listener which passes events into a local queue
    q = asyncio.Queue()
    session.add_listener(q.put)

    async def generator():
        # yield from the q until we get a RoundComplete
        while True:
            event = await q.get()
            if event.__log_event__ or not only_loggable:
                yield event
            if autoraise and isinstance(event, events.Error):
                raise event.exc
            if event.type == "round_complete":
                break

    try:
        yield generator()
    finally:
        session.remove_listener(q.put)


def print_event(event, print_stream=True, print_user=False):
    match event:
        # stream
        case events.StreamDelta(role=ChatRole.ASSISTANT, is_root=True, delta=part) if print_stream:
            print(part, end="", flush=True)
        case events.RootMessage(msg=msg) if msg.role == ChatRole.ASSISTANT and print_stream:
            print()  # end of stream
            if text := assistant_message_thinking(msg, show_args=True):
                print(f"AI: {text}")
        # user events
        case events.RootMessage(
            msg=ChatMessage(role=ChatRole.USER, content=[interop.AudioPart() as audio_part])
        ) if print_user:
            print(f"USER: [audio: {audio_part.audio_duration:.3f}s]")
        case events.RootMessage(msg=msg) if msg.role == ChatRole.USER and print_user:
            print(f"USER: {msg.text}")
        # messages
        case events.RootMessage(msg=msg) if msg.role == ChatRole.ASSISTANT and not print_stream:
            text = assistant_message_contents_thinking(msg, show_args=True)
            print(f"AI: {text}")
        case events.RootMessage(msg=msg) if msg.role == ChatRole.FUNCTION:
            print(f"FUNC: {msg.text}")


def get_chat_history_audio_len(msgs: list[ChatMessage]) -> float:
    """Get the duration of all audio in *msgs*, in seconds."""
    duration = 0.0
    for msg in msgs:
        for part in msg.parts:
            if isinstance(part, interop.AudioPart):
                duration += part.audio_duration
    return duration


class DynamicSubclassDeser(BaseModel):
    # ==== serdes ====
    __discriminator_attr__: ClassVar[str]
    # used for saving/loading - map key to messagepart type
    _subclass_registry: ClassVar[Dict[str, Type["DynamicSubclassDeser"]]] = {}

    # noinspection PyMethodOverriding
    def __init_subclass__(cls, **kwargs):
        """
        When a new subclass is defined, we need to save its type so that we can load saved JSON into the right type
        later.
        """
        super().__init_subclass__(**kwargs)
        type_key = getattr(cls, cls.__discriminator_attr__, None)
        if type_key is None:
            # probably the root class, don't do anything
            return
        if type_key in cls._subclass_registry:
            raise ValueError(
                f"{type(cls).__name__} has key {type_key!r} on discriminating attribute"
                f" {cls.__discriminator_attr__} but this key is already registered to class"
                f" {cls._subclass_registry[type_key].__name__}."
            )
        cls._subclass_registry[type_key] = cls

    # noinspection PyNestedDecorators
    @model_validator(mode="wrap")
    @classmethod
    def _validate(cls, v, nxt, info: ValidationInfo):
        """If we are deserializing a dict with the special key, switch to the right class' validator."""
        # only do this on the base
        if isinstance(info.context, dict) and "_dynamic_subclass_deser_seen" in info.context:
            return nxt(v)

        if isinstance(v, dict) and cls.__discriminator_attr__ in v:
            type_key = v[cls.__discriminator_attr__]
            try:
                klass = cls._subclass_registry[type_key]
            except KeyError:
                raise ValueError(
                    f"Attempted to deserialize a {type(cls).__name__} with type {type_key!r}, but the type is not"
                    " defined."
                ) from None
            return klass.model_validate(v, context={"_dynamic_subclass_deser_seen": True})
        return nxt(v)
