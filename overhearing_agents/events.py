import abc
import base64
import time
from typing import Literal, TypeVar

from kani import ChatMessage, ChatRole
from pydantic import BaseModel, Field, SerializeAsAny

from .state import KaniState, RunState, Suggestion
from .utils import DynamicSubclassDeser


class BaseEvent(BaseModel, abc.ABC):
    """The base event that all other events should inherit from."""

    __log_event__ = True  # whether or not the event should be logged
    type: str
    timestamp: float = Field(default_factory=time.time)


# server events
class ServerEvent(BaseEvent):
    pass


class Error(ServerEvent):
    type: Literal["error"] = "error"
    _exc: BaseException
    msg: str

    def __init__(self, exc: BaseException, **kwargs):
        super().__init__(**kwargs)
        self._exc = exc

    @classmethod
    def from_exc(cls, exc: BaseException):
        return cls(exc=exc, msg=str(exc))

    @property
    def exc(self):
        return self._exc


class KaniSpawn(ServerEvent):
    """
    A new kani was spawned. Includes the state of the kani. See :class:`.BaseKani`.

    The ID can be the same as an existing ID, in which case this event should overwrite the previous state.
    """

    type: Literal["kani_spawn"] = "kani_spawn"
    state: KaniState


class KaniStateChange(ServerEvent):
    """
    A kani's run state changed.

    This is primarily used for rendering the color of a node in the web interface.
    """

    type: Literal["kani_state_change"] = "kani_state_change"
    id: str
    state: RunState


class TokensUsed(ServerEvent):
    """A kani just finished a request to the engine, which used this many tokens."""

    type: Literal["tokens_used"] = "tokens_used"
    id: str
    prompt_tokens: int
    completion_tokens: int


class DetailedTokensUsed(ServerEvent):
    """A more detailed version of tokens_used for OAI models."""

    type: Literal["tokens_used"] = "detailed_tokens_used"
    id: str
    usage: dict


class KaniMessage(ServerEvent):
    """A kani added a message to its chat history."""

    type: Literal["kani_message"] = "kani_message"
    id: str
    msg: ChatMessage


class RootMessage(ServerEvent):
    """
    The root kani has a new result.

    This will be fired *in addition* to a ``kani_message`` event.
    """

    type: Literal["root_message"] = "root_message"
    msg: ChatMessage


class StreamDelta(ServerEvent):
    """A kani is streaming and emitted a new token."""

    __log_event__ = False

    type: Literal["stream_delta"] = "stream_delta"
    id: str
    delta: str
    role: ChatRole
    is_root: bool = None  # useful for stateless printing


class OutputAudioDelta(ServerEvent):
    """A kani is streaming and is playing this audio."""

    __log_event__ = False

    type: Literal["output_audio_delta"] = "output_audio_delta"
    id: str
    delta: str


class RoundComplete(ServerEvent):
    """The root kani has finished a full round and control should be handed off to the user."""

    type: Literal["round_complete"] = "round_complete"
    session_id: str


class SessionClose(ServerEvent):
    """The session is closing and clients should be redirected to the home page."""

    __log_event__ = False

    type: Literal["session_close"] = "session_close"
    session_id: str


class SessionMetaUpdate(ServerEvent):
    """Some part of the session metadata has been updated."""

    type: Literal["session_meta_update"] = "session_meta_update"
    title: str


# ---- overhearing_agents events ----
class SuggestionEvent(ServerEvent):
    type: Literal["suggestion"] = "suggestion"
    suggestion: SerializeAsAny[Suggestion]


# ===== user events =====
class UserEvent(DynamicSubclassDeser, BaseEvent):
    __discriminator_attr__ = "type"


class SendMessage(UserEvent):
    type: Literal["send_message"] = "send_message"
    content: str


class SendAudioMessage(UserEvent):
    type: Literal["send_audio_message"] = "send_audio_message"
    data_b64: str
    text_prefix: str | None = None
    text_suffix: str | None = None

    @property
    def data(self) -> bytes:
        return base64.b64decode(self.data_b64)


class InputAudioDelta(UserEvent):
    __log_event__ = False

    type: Literal["input_audio_delta"] = "input_audio_delta"
    data_b64: str

    @property
    def data(self) -> bytes:
        return base64.b64decode(self.data_b64)


class ClientEventLog(UserEvent):
    """Arbitrary data logging for later analysis, does not affect server state"""

    type: Literal["log_client_event"] = "log_client_event"
    key: str
    data: dict


UserEventT = TypeVar("UserEventT", bound=UserEvent)
