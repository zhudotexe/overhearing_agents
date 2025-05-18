# {
#     "filename:experiment-key": {
#         "state": "running|done|error",
#         "path": "run-id/experiment-key.json"
#     }
# }
import contextlib
import json
import traceback
from pathlib import Path

from filelock import FileLock


class ExperimentRunIndex:
    """
    Simple index thingy to prevent double runs, using a flock
    Assumption: Only 1 process will be touching a given key at a time
    """

    def __init__(self, fp: Path):
        self.fp = fp
        self.flock = FileLock(fp.with_suffix(".lock"))
        self.data = None
        self.updated_keys = set()

    def __enter__(self):
        with self.flock:
            if not self.fp.exists():
                self.fp.write_text("{}")
            with self.fp.open("r") as f:
                self.data = json.load(f)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._sync()

    def _sync(self):
        with self.flock:
            with self.fp.open("r+") as f:
                # read the most recent data & merge it with updated_keys (i.e., most recent data in memory)
                new_data = json.load(f)
                data_to_merge = {k: self.data[k] for k in self.updated_keys}
                self.data = new_data | data_to_merge
                # write it back, if we had any updates
                if not self.updated_keys:
                    return
                f.seek(0)
                json.dump(self.data, f, indent=2)
                f.truncate()
                # and clear updated_keys
                self.updated_keys.clear()

    # primitives
    def set_key(self, key, value):
        self.data[key] = value
        self.updated_keys.add(key)

    def update_key(self, key, value):
        if key not in self.data:
            self.data[key] = {}
        self.data[key] |= value
        self.updated_keys.add(key)

    # state read
    def is_done_or_running(self, key: str):
        self._sync()
        state = self.data.get(key, {}).get("state")
        return state == "running" or state == "done"

    def is_partially_complete(self, key: str):
        if self.is_done_or_running(key):
            return False
        data = self.data.get(key, {})
        return data.get("last_processed", 0)

    # state write
    @contextlib.contextmanager
    def running(self, key: str, fp: Path):
        rel_fp = str(fp.relative_to(Path(__file__).parent / "logs"))
        self.set_key(key, {"state": "running", "path": rel_fp})
        try:
            yield
        except BaseException:  # we want to catch *everything* here and log it
            self.update_key(key, {"state": "error", "path": rel_fp, "error": traceback.format_exc()})
            raise
        else:
            self.update_key(key, {"state": "done", "path": rel_fp})
        finally:
            self._sync()

    def update_last_seen(self, key: str, ts: float):
        """Save that the run with the given key has seem up to the given ts."""
        self.update_key(key, {"last_processed": ts})
        self._sync()
