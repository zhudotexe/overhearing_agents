import enum
import uuid

from kani import AIFunction, ChatMessage, ChatRole
from pydantic import BaseModel, Field

from .utils import DynamicSubclassDeser


class RunState(enum.Enum):
    """
    * ``RunState.STOPPED``: This kani is not currently running anything or waiting on a child.
    * ``RunState.RUNNING``: This kani is currently generating text.
    * ``RunState.WAITING``: This kani is waiting for the results of a sub-kani.
    * ``RunState.ERRORED``: This kani has run into a fatal error. Its internal state is indeterminate.
    """

    STOPPED = "stopped"  # not currently running anything or waiting on a child
    RUNNING = "running"  # gpt-4 is generating something
    WAITING = "waiting"  # waiting on a child
    ERRORED = "errored"  # panic


class AIFunctionState(BaseModel):
    name: str
    desc: str
    auto_retry: bool
    auto_truncate: int | None
    after: ChatRole
    json_schema: dict

    @classmethod
    def from_aifunction(cls, f: AIFunction):
        return cls(
            name=f.name,
            desc=f.desc,
            auto_retry=f.auto_retry,
            auto_truncate=f.auto_truncate,
            after=f.after,
            json_schema=f.json_schema,
        )


class KaniState(BaseModel):
    id: str
    depth: int
    parent: str | None
    children: list[str]
    always_included_messages: list[ChatMessage]
    chat_history: list[ChatMessage]
    state: RunState
    name: str
    engine_type: str
    engine_repr: str = ""
    functions: list[AIFunctionState]


class Suggestion(DynamicSubclassDeser, BaseModel):
    __discriminator_attr__ = "suggest_type"
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    suggest_type: str
