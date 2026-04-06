from __future__ import annotations

from datetime import datetime

import pytest

from backend.models.task import TaskStatus
from backend.services.task_service import TaskService
from backend.task.task_queue_manager import (
    Task,
    TaskKind as InternalTaskKind,
    TaskQueueManager,
)


def reset_task_queue_state(queue: TaskQueueManager) -> None:
    with queue._data_lock:
        queue._tasks.clear()
        queue._queue.clear()
        queue._progress_callbacks.clear()
        queue._cancel_events.clear()
        queue._worker_futures.clear()
        queue._running_async_loops.clear()
        queue._running_async_tasks.clear()
        queue._current_task_id = None


@pytest.fixture(autouse=True)
def isolate_task_queue():
    queue = TaskQueueManager()
    reset_task_queue_state(queue)
    yield
    reset_task_queue_state(queue)


def _build_edit_task(*, task_id: str = "task-edit-1") -> Task:
    return Task(
        task_id=task_id,
        user_session_id="conv-edit-1",
        created_at=datetime.now(),
        task_kind=InternalTaskKind.EDIT,
    )


def test_get_task_preserves_edit_task_kind():
    queue = TaskQueueManager()
    with queue._data_lock:
        queue._tasks["task-edit-1"] = _build_edit_task()

    response = TaskService(queue).get_task("task-edit-1")

    assert response is not None
    assert response.data is not None
    assert response.data.task_kind.value == "edit"


def test_list_tasks_preserves_edit_task_kind():
    queue = TaskQueueManager()
    with queue._data_lock:
        queue._tasks["task-edit-1"] = _build_edit_task()

    response = TaskService(queue).list_tasks(status_filter=[TaskStatus.QUEUED])

    assert response.total == 1
    assert response.tasks[0].task_kind.value == "edit"


def test_heartbeat_task_preserves_edit_task_kind():
    queue = TaskQueueManager()
    with queue._data_lock:
        queue._tasks["task-edit-1"] = _build_edit_task()

    response = TaskService(queue).heartbeat_task("task-edit-1")

    assert response is not None
    assert response.alive is True
    assert response.task_kind.value == "edit"
