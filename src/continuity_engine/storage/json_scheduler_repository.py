from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from threading import Lock, RLock
from typing import Any

from continuity_engine.domain.scheduling import (
    SchedulerPersistenceError,
    SchedulerQueue,
    SchedulerValidationError,
)


_LOCK_REGISTRY_GUARD = Lock()
_LOCK_REGISTRY: dict[str, RLock] = {}


def _shared_lock(path: Path) -> RLock:
    key = str(path.resolve(strict=False))
    with _LOCK_REGISTRY_GUARD:
        return _LOCK_REGISTRY.setdefault(key, RLock())


class JsonSchedulerRepository:
    """Single atomic P11 queue document with optimistic revision checks."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root) / "scheduler"
        self.path = self.root / "queue.v1.json"
        self._lock = _shared_lock(self.path)

    def load_queue(self) -> SchedulerQueue:
        with self._lock:
            if not self.path.exists():
                return SchedulerQueue()
            if not self.path.is_file():
                raise SchedulerPersistenceError("scheduler queue path is not a file")
            try:
                value = json.loads(self.path.read_text(encoding="utf-8"))
                return SchedulerQueue.from_dict(value)
            except (OSError, UnicodeError, json.JSONDecodeError, SchedulerValidationError) as exc:
                raise SchedulerPersistenceError("unable to read a valid scheduler queue") from exc

    def save_queue(self, queue: SchedulerQueue, *, expected_revision: int) -> None:
        if not isinstance(queue, SchedulerQueue):
            raise SchedulerPersistenceError("queue must be a SchedulerQueue")
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 0:
            raise SchedulerPersistenceError("expected_revision must be non-negative")
        if queue.revision != expected_revision + 1:
            raise SchedulerPersistenceError("scheduler queue revision must advance by one")
        with self._lock:
            current = self.load_queue()
            if current.revision != expected_revision:
                raise SchedulerPersistenceError("scheduler queue does not match expected_revision")
            self._write(queue.to_dict())

    def _write(self, value: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=".queue.",
                suffix=".tmp",
                dir=self.root,
                delete=False,
            ) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
                temporary_path = Path(handle.name)
            os.replace(temporary_path, self.path)
        except OSError as exc:
            raise SchedulerPersistenceError("unable to atomically save scheduler queue") from exc
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
