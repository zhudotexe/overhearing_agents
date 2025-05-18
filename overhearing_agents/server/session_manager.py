import asyncio
from typing import TYPE_CHECKING

from fastapi import WebSocket

from overhearing_agents import OverhearingAgentsSession, events
from .models import SaveMeta, SessionMeta, SessionState

if TYPE_CHECKING:
    from .server import VizServer


class SessionManager:
    """Responsible for a single session and all connections to it."""

    def __init__(self, server: "VizServer", session: OverhearingAgentsSession):
        self.server = server
        self.session = session
        self.session.add_listener(self.on_event)
        self.task = None
        self.event_queue = asyncio.Queue[events.UserEventT]()
        self.active_connections: list[WebSocket] = []

    # ==== lifecycle ====
    async def start(self):
        if self.task is not None:
            raise RuntimeError("This session has already been started.")
        self.task = asyncio.create_task(self.session.chat_from_queue(self.event_queue))

    async def close(self):
        if self.task is not None:
            self.task.cancel()
        await self.session.close()

    # ==== state ====
    def get_state(self) -> SessionState:
        kanis = [ai.get_save_state() for ai in self.session.kanis.values()]
        return SessionState(
            id=self.session.session_id,
            created=self.session.logger.created,
            last_modified=self.session.logger.last_modified,
            n_events=self.session.logger.event_count.total(),
            state=kanis,
            suggestion_history=self.session.suggestion_history,
        )

    def get_session_meta(self) -> SessionMeta:
        return SessionMeta(
            id=self.session.session_id,
            created=self.session.logger.created,
            last_modified=self.session.logger.last_modified,
            n_events=self.session.logger.event_count.total(),
        )

    def get_save_meta(self) -> SaveMeta:
        return SaveMeta(
            id=self.session.session_id,
            created=self.session.logger.created,
            last_modified=self.session.logger.last_modified,
            n_events=self.session.logger.event_count.total(),
            grouping_prefix=self.session.logger.log_dir.parent.parts,
            save_dir=self.session.logger.log_dir,
            state_fp=self.session.logger.state_path,
            event_fp=self.session.logger.aof_path,
        )

    # ==== ws ====
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, data: str):
        await asyncio.gather(
            *(connection.send_text(data) for connection in self.active_connections), return_exceptions=True
        )

    async def on_event(self, event: events.BaseEvent):
        if isinstance(event, events.UserEvent):
            return
        await self.broadcast(event.model_dump_json())
        # update the server save info on each RoundComplete
        if isinstance(event, events.RoundComplete):
            self.server.saves[self.session.session_id] = self.get_save_meta()
