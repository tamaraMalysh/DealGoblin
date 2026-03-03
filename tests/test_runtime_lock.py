import json

import pytest

from dealgoblin.runtime_lock import (
    RuntimeInstanceLockedError,
    acquire_runtime_lock,
)


def test_runtime_lock_acquires_and_writes_metadata(tmp_path):
    lock_path = tmp_path / "runtime.lock"

    lock = acquire_runtime_lock(str(lock_path))
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
        assert payload["pid"] > 0
        assert payload["hostname"]
        assert payload["started_at"]
    finally:
        lock.release()


def test_runtime_lock_fails_fast_when_lock_is_already_held(tmp_path):
    lock_path = tmp_path / "runtime.lock"
    first_lock = acquire_runtime_lock(str(lock_path))
    try:
        with pytest.raises(RuntimeInstanceLockedError, match="Runtime lock is already held"):
            acquire_runtime_lock(str(lock_path))
    finally:
        first_lock.release()


def test_runtime_lock_can_be_reacquired_after_release(tmp_path):
    lock_path = tmp_path / "runtime.lock"

    first_lock = acquire_runtime_lock(str(lock_path))
    first_lock.release()

    second_lock = acquire_runtime_lock(str(lock_path))
    second_lock.release()
