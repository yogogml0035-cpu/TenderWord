from __future__ import annotations

from concurrent.futures import Future
from datetime import datetime, timedelta

import pytest

import backend.task.task_queue_manager as task_queue_module
from backend.task.task_queue_manager import TaskQueueManager, TaskStatus


class DummyAsyncTask:
    def __init__(self) -> None:
        self.cancel_requested = False
        self._done = False

    def done(self) -> bool:
        return self._done

    def cancel(self) -> None:
        self.cancel_requested = True
        self._done = True


class DummyLoop:
    def __init__(self) -> None:
        self.calls = 0

    def call_soon_threadsafe(self, callback) -> None:
        self.calls += 1
        callback()


@pytest.fixture
def task_queue():
    original_instance = TaskQueueManager._instance
    TaskQueueManager._instance = None
    queue = TaskQueueManager()

    try:
        yield queue
    finally:
        queue._cleanup_thread_stop.set()
        queue._cleanup_thread.join(timeout=1)
        TaskQueueManager._instance = original_instance


def test_heartbeat_timeout_cancels_queued_and_running_tasks(task_queue, monkeypatch):
    warnings: list[str] = []
    monkeypatch.setattr(task_queue_module.progress_log, "warning", warnings.append)

    task_queue.add_task("task-queued", "session-1")
    task_queue.add_task("task-running", "session-1")
    task_queue.start_task("task-running")

    queued_future = Future()
    running_future = Future()
    task_queue.register_worker_future("task-queued", queued_future)
    task_queue.register_worker_future("task-running", running_future)
    task_queue.register_progress_callback("task-queued", lambda progress: progress)
    task_queue.register_progress_callback("task-running", lambda progress: progress)

    running_loop = DummyLoop()
    running_async_task = DummyAsyncTask()
    task_queue.register_running_async_context("task-running", running_loop, running_async_task)

    with task_queue._data_lock:
        task_queue.get_task("task-queued").last_heartbeat = datetime.now() - timedelta(seconds=60)
        task_queue.get_task("task-running").last_heartbeat = datetime.now() - timedelta(seconds=60)

    task_queue._heartbeat_timeout = 30
    task_queue._check_and_cancel_timeout_tasks()

    assert task_queue.get_task("task-queued").status == TaskStatus.CANCELLED
    assert task_queue.get_task("task-running").status == TaskStatus.CANCELLED
    assert task_queue.get_task("task-queued").error == "heartbeat_timeout"
    assert task_queue.get_task("task-running").error == "heartbeat_timeout"
    assert task_queue._current_task_id is None
    assert "task-queued" not in task_queue._queue
    assert queued_future.cancelled() is True
    assert running_loop.calls == 1
    assert running_async_task.cancel_requested is True
    assert "task-queued" not in task_queue._progress_callbacks
    assert "task-running" not in task_queue._progress_callbacks
    assert "task-queued" not in task_queue._cancel_events
    assert "task-running" not in task_queue._cancel_events
    assert any("heartbeat_timeout" in warning for warning in warnings)


def test_heartbeat_timeout_releases_slot_for_next_task(task_queue):
    task_queue.add_task("task-running", "session-1")
    task_queue.add_task("task-next", "session-1")
    task_queue.start_task("task-running")

    with task_queue._data_lock:
        task_queue.get_task("task-running").last_heartbeat = datetime.now() - timedelta(seconds=60)
        task_queue.get_task("task-next").last_heartbeat = datetime.now()

    task_queue._heartbeat_timeout = 30
    task_queue._check_and_cancel_timeout_tasks()

    assert task_queue._current_task_id is None
    assert task_queue.wait_for_turn("task-next", timeout=0.01) is True


def test_cleanup_old_tasks_removes_cancelled_entries(task_queue):
    cancelled_task = task_queue.add_task("task-cancelled", "session-1")
    completed_task = task_queue.add_task("task-completed", "session-1")
    queued_task = task_queue.add_task("task-queued", "session-1")

    old_completed_at = datetime.now() - timedelta(seconds=120)
    with task_queue._data_lock:
        cancelled_task.status = TaskStatus.CANCELLED
        cancelled_task.completed_at = old_completed_at
        completed_task.status = TaskStatus.COMPLETED
        completed_task.completed_at = old_completed_at
        queued_task.completed_at = None

    task_queue.cleanup_old_tasks(max_age_seconds=60)

    assert task_queue.get_task("task-cancelled") is None
    assert task_queue.get_task("task-completed") is None
    assert task_queue.get_task("task-queued") is not None
