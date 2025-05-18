from pathlib import Path

from pydantic import BaseModel, SerializeAsAny

from overhearing_agents.state import KaniState, Suggestion


# ===== server -> client =====
class SessionMeta(BaseModel):
    id: str
    created: float
    last_modified: float
    n_events: int


class SaveMeta(SessionMeta):
    grouping_prefix: list[str]
    save_dir: Path
    state_fp: Path
    event_fp: Path


class SessionState(SessionMeta):
    state: list[KaniState]
    suggestion_history: list[SerializeAsAny[Suggestion]] = []


# ===== client -> server =====
class LoadSavePayload(BaseModel):
    fork: bool = True
