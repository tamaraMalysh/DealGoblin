from __future__ import annotations

import fcntl
import json
import os
import socket
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


class RuntimeInstanceLockedError(RuntimeError):
    """Raised when another DealGoblin runtime already holds the lock."""


@dataclass
class RuntimeLock:
    path: Path
    _fd: object

    def release(self) -> None:
        if self._fd is None:
            return
        try:
            fcntl.flock(self._fd.fileno(), fcntl.LOCK_UN)
        finally:
            self._fd.close()
            self._fd = None


def _read_holder_metadata(path: Path) -> str:
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown holder"

    if not raw:
        return "unknown holder"

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw

    pid = payload.get("pid", "unknown")
    hostname = payload.get("hostname", "unknown")
    started_at = payload.get("started_at", "unknown")
    return f"pid={pid}, hostname={hostname}, started_at={started_at}"


def acquire_runtime_lock(lock_path: str) -> RuntimeLock:
    path = Path(lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        holder = _read_holder_metadata(path)
        fd.close()
        raise RuntimeInstanceLockedError(
            f"Runtime lock is already held at '{path}' ({holder})"
        ) from exc

    metadata = {
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "started_at": datetime.now(UTC).isoformat(),
    }
    fd.seek(0)
    fd.truncate()
    fd.write(json.dumps(metadata))
    fd.flush()
    os.fsync(fd.fileno())
    return RuntimeLock(path=path, _fd=fd)
