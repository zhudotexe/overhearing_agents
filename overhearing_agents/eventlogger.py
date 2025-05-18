import base64
import collections
import contextlib
import hashlib
import json
import logging
import pathlib
import shutil
import time
from collections import Counter
from functools import cached_property
from typing import Callable, TYPE_CHECKING

import openai.types.beta.realtime as oait
from kani.ext.realtime.interop import AudioPart
from pydub import AudioSegment

from . import events
from .config import DEFAULT_LOG_DIR
from .utils import read_jsonl

if TYPE_CHECKING:
    from .session import OverhearingAgentsSession


log = logging.getLogger(__name__)


class EventLogger:
    def __init__(
        self,
        app: "OverhearingAgentsSession",
        session_id: str,
        log_dir: pathlib.Path = None,
        clear_existing_log: bool = False,
    ):
        self.app = app
        self.session_id = session_id
        self.created = time.time()
        self.last_modified = time.time()
        self.log_dir = log_dir or (DEFAULT_LOG_DIR / session_id)
        self.clear_existing_log = clear_existing_log

        self.aof_path = self.log_dir / "events.jsonl"
        self.state_path = self.log_dir / "state.json"

        self.event_count = Counter()
        self._suppress_flag = 0

        self._audio_logger = AudioLogger()

    @cached_property
    def event_file(self):
        # we use a cached property here to only lazily create the log dir if we need it
        self.log_dir.mkdir(exist_ok=True, parents=True)

        if self.clear_existing_log:
            return open(self.aof_path, "w", buffering=1, encoding="utf-8")

        if self.aof_path.exists():
            existing_events = read_jsonl(self.aof_path)
            self.event_count = Counter(event["type"] for event in existing_events)
        return open(self.aof_path, "a", buffering=1, encoding="utf-8")

    async def log_event(self, event: events.BaseEvent):
        if self._suppress_flag:
            return
        if not event.__log_event__:
            return
        self.last_modified = time.time()

        # if we have audio in the message, write a reference to an audio file instead
        data = event.model_dump(mode="json")
        if isinstance(event, (events.KaniMessage, events.RootMessage)) and isinstance(event.msg.content, list):
            for idx, part in enumerate(event.msg.content):
                if isinstance(part, AudioPart) and part.audio_b64:
                    data["msg"]["content"][idx]["audio_b64"] = None
                    data["msg"]["content"][idx]["audio_file_path"] = self.save_audio(
                        part.audio_bytes,
                        fmt="mp3",
                        role=event.msg.role.value,
                        subdir="events-audio",
                        idx=self.event_count.total(),
                    )
        if isinstance(event, events.SendAudioMessage):
            data["data_b64"] = None
            data["audio_file_path"] = self.save_audio(
                event.data, fmt="mp3", role="user", subdir="events-audio", idx=self.event_count.total()
            )

        # since this is a synch operation we don't need a lock here (though it is thread-unsafe)
        self.event_file.write(json.dumps(data))
        self.event_file.write("\n")
        self.event_count[event.type] += 1

    async def write_state(self):
        """Write the full state of the app to the state file, with a basic checksum against the AOF to check validity"""
        if self._suppress_flag:
            return
        self.log_dir.mkdir(exist_ok=True, parents=True)

        # get the state of each kani
        states = []
        for ai in self.app.kanis.values():
            state = ai.get_save_state()
            data = state.model_dump(mode="json")
            # if we have audio in the state, write a reference to an audio file instead
            for idx, msg in enumerate(state.chat_history):
                if isinstance(msg.content, list):
                    for cidx, part in enumerate(msg.content):
                        if isinstance(part, AudioPart) and part.audio_b64:
                            data["chat_history"][idx]["content"][cidx]["audio_b64"] = None
                            data["chat_history"][idx]["content"][cidx]["audio_file_path"] = self.save_audio(
                                part.audio_bytes, fmt="mp3", role=msg.role.value, subdir="audio", idx=idx
                            )
            # and save it
            states.append(data)

        data = {
            "id": self.session_id,
            "created": self.created,
            "last_modified": self.last_modified,
            "n_events": self.event_count.total(),
            "state": states,
            "suggestion_history": [s.model_dump(mode="json") for s in self.app.suggestion_history],
        }
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    async def close(self):
        # if we haven't done anything, don't write anything
        if not self.event_count.total():
            return
        await self.write_state()
        self.event_file.close()

    @contextlib.contextmanager
    def suppress_logs(self):
        """Don't dispatch any events while in this body."""
        self._suppress_flag += 1
        try:
            yield
        finally:
            self._suppress_flag -= 1

    # ===== extensions =====
    @cached_property
    def realtime_event_file(self):
        # we use a cached property here to only lazily create the log dir if we need it
        self.log_dir.mkdir(exist_ok=True, parents=True)
        realtime_aof_path = self.log_dir / "realtime_events.jsonl"

        if self.clear_existing_log:
            return open(realtime_aof_path, "w", buffering=1, encoding="utf-8")
        return open(realtime_aof_path, "a", buffering=1, encoding="utf-8")

    async def log_realtime_event(self, event: oait.RealtimeServerEvent):
        # don't log delta events
        if event.type.endswith(".delta"):
            return

        # if we have audio in the message, write a summary instead
        data = event.model_dump(mode="json", exclude_unset=True)
        if isinstance(event, oait.ResponseAudioDeltaEvent):
            duration = len(base64.b64decode(event.delta)) / 48000
            data["delta"] = f"[audio: {duration:.3f}s]"

        # since this is a synch operation we don't need a lock here (though it is thread-unsafe)
        self.realtime_event_file.write(json.dumps(data))
        self.realtime_event_file.write("\n")

    def save_audio(
        self,
        audio_bytes: bytes,
        fmt: str = "mp3",
        subdir: str = "audio",
        idx: int = 0,
        role: str = "",
    ) -> str:
        fp = self._audio_logger.save_audio(
            audio_bytes,
            dir_path=self.log_dir / subdir,
            name_factory=lambda audio_hash: f"{idx}-{role.lower()}-{audio_hash[:8]}.{fmt}",
            fmt=fmt,
        )
        return fp.name


class AudioLogger:
    def __init__(self):
        # (hash, fmt) -> path
        self._audio_filenames: dict[tuple[str, str], list[pathlib.Path]] = collections.defaultdict(list)

    def save_audio(
        self,
        audio_bytes: bytes,
        dir_path: pathlib.Path,
        name_factory: Callable[[str], str],
        fmt: str = "mp3",
        *,
        copy_if_other_dir: bool = True,
    ) -> pathlib.Path:
        dir_path.mkdir(exist_ok=True, parents=True)
        assert dir_path.is_dir()
        audio_hash = hashlib.sha256(audio_bytes).hexdigest()
        fn = name_factory(audio_hash)
        out_fp = dir_path / fn

        # if in cache, ensure a copy exists in the same subdir that we're writing to
        if (audio_hash, fmt) in self._audio_filenames:
            existing_fps = self._audio_filenames[(audio_hash, fmt)]
            existing_fp_in_same_dir = next((fp for fp in existing_fps if str(fp).startswith(str(dir_path))), None)
            if copy_if_other_dir and not existing_fp_in_same_dir:
                shutil.copy(existing_fps[0], out_fp)
                self._audio_filenames[(audio_hash, fmt)].append(out_fp)
                return out_fp
            return existing_fp_in_same_dir

        # otherwise write it
        segment = AudioSegment(audio_bytes, sample_width=2, frame_rate=24000, channels=1)
        segment.export(out_fp, format=fmt)
        self._audio_filenames[(audio_hash, fmt)].append(out_fp)
        return out_fp
