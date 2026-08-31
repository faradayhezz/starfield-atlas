from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable


TERMINAL_STATUSES = {"complete", "cancelled", "error", "timeout"}


class TaskAlreadyExistsError(ValueError):
    """Raised when a live progress record already uses a request id."""


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(slots=True)
class _AnalysisTask:
    request_id: str
    status: str
    stage: str
    percent: int
    message: str
    received_bytes: int
    total_bytes: int
    updated_at: str
    updated_monotonic: float
    cancel_event: threading.Event = field(default_factory=threading.Event)
    cancel_hook: Callable[[], None] | None = None

    def public(self) -> dict[str, object]:
        return {
            "status": self.status,
            "stage": self.stage,
            "percent": self.percent,
            "message": self.message,
            "receivedBytes": self.received_bytes,
            "totalBytes": self.total_bytes,
            "updatedAt": self.updated_at,
        }


class AnalysisTaskRegistry:
    """Thread-safe, short-lived progress and cancellation state."""

    def __init__(
        self,
        *,
        ttl_seconds: float = 30 * 60,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._ttl_seconds = float(ttl_seconds)
        self._monotonic = monotonic
        self._lock = threading.Lock()
        self._tasks: dict[str, _AnalysisTask] = {}

    def _cleanup_locked(self, now: float) -> None:
        expired = [
            request_id
            for request_id, task in self._tasks.items()
            if now - task.updated_monotonic >= self._ttl_seconds
        ]
        for request_id in expired:
            self._tasks.pop(request_id, None)

    def cleanup(self) -> int:
        with self._lock:
            before = len(self._tasks)
            self._cleanup_locked(self._monotonic())
            return before - len(self._tasks)

    def register(self, request_id: str, *, total_bytes: int) -> dict[str, object]:
        now = self._monotonic()
        with self._lock:
            self._cleanup_locked(now)
            if request_id in self._tasks:
                raise TaskAlreadyExistsError(request_id)
            task = _AnalysisTask(
                request_id=request_id,
                status="uploading",
                stage="upload",
                percent=0,
                message="准备接收照片",
                received_bytes=0,
                total_bytes=max(0, int(total_bytes)),
                updated_at=_utc_timestamp(),
                updated_monotonic=now,
            )
            self._tasks[request_id] = task
            return task.public()

    def get(self, request_id: str) -> dict[str, object] | None:
        now = self._monotonic()
        with self._lock:
            self._cleanup_locked(now)
            task = self._tasks.get(request_id)
            return task.public() if task else None

    def update(
        self,
        request_id: str,
        *,
        status: str | None = None,
        stage: str | None = None,
        percent: int | float | None = None,
        message: str | None = None,
        received_bytes: int | None = None,
        total_bytes: int | None = None,
    ) -> dict[str, object] | None:
        now = self._monotonic()
        with self._lock:
            self._cleanup_locked(now)
            task = self._tasks.get(request_id)
            if task is None:
                return None
            # Once cancellation is requested, late pipeline callbacks must not
            # make the task look active again.
            if task.cancel_event.is_set() and status != "cancelled":
                return task.public()
            if status is not None:
                task.status = str(status)
            if stage is not None:
                task.stage = str(stage)
            if percent is not None:
                normalized_percent = min(100, max(0, round(float(percent))))
                task.percent = max(task.percent, normalized_percent)
            if message is not None:
                task.message = str(message)
            if received_bytes is not None:
                task.received_bytes = max(task.received_bytes, max(0, int(received_bytes)))
            if total_bytes is not None:
                task.total_bytes = max(0, int(total_bytes))
            task.updated_at = _utc_timestamp()
            task.updated_monotonic = now
            return task.public()

    def cancel(self, request_id: str) -> tuple[dict[str, object] | None, bool]:
        hook: Callable[[], None] | None = None
        now = self._monotonic()
        with self._lock:
            self._cleanup_locked(now)
            task = self._tasks.get(request_id)
            if task is None:
                return None, False
            if task.status in TERMINAL_STATUSES:
                return task.public(), False
            task.cancel_event.set()
            task.status = "cancelling"
            task.message = "正在取消识别"
            task.updated_at = _utc_timestamp()
            task.updated_monotonic = now
            hook = task.cancel_hook
            snapshot = task.public()
        if hook is not None:
            try:
                hook()
            except OSError:
                pass
        return snapshot, True

    def mark_cancelled(self, request_id: str, message: str = "识别已取消") -> dict[str, object] | None:
        return self.update(
            request_id,
            status="cancelled",
            stage="cancelled",
            message=message,
        )

    def is_cancelled(self, request_id: str) -> bool:
        now = self._monotonic()
        with self._lock:
            self._cleanup_locked(now)
            task = self._tasks.get(request_id)
            return task is None or task.cancel_event.is_set()

    def set_cancel_hook(
        self, request_id: str, hook: Callable[[], None] | None
    ) -> bool:
        invoke_now = False
        now = self._monotonic()
        with self._lock:
            self._cleanup_locked(now)
            task = self._tasks.get(request_id)
            if task is None:
                return False
            if hook is not None and task.cancel_event.is_set():
                invoke_now = True
            else:
                task.cancel_hook = hook
        if invoke_now:
            try:
                hook()
            except OSError:
                pass
        return True
