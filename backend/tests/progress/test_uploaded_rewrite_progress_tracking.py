from __future__ import annotations

from datetime import datetime

import pytest

from backend.core.sse_manager import sse_manager
from backend.graphs.base_graph import TRACKED_PROGRESS_NODES, wrap_node_with_progress
from backend.task.task_queue_manager import Task, TaskKind, TaskQueueManager

UPLOADED_REWRITE_WORKFLOW_NODES = [
    "resolve_rewrite_target",
    "extract_rewrite_context",
    "delete_section",
    "rewrite_text",
    "update_word",
]

UPLOADED_REWRITE_PROGRESS_NODES = [
    "resolve_rewrite_target",
    "extract_rewrite_context",
    "rewrite_text",
]


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


@pytest.fixture(autouse=True)
def stub_progress_sse(monkeypatch):
    monkeypatch.setattr(sse_manager, "send_progress_threadsafe", lambda **kwargs: None)


def test_tracked_progress_nodes_include_uploaded_rewrite_workflow_nodes():
    assert set(UPLOADED_REWRITE_PROGRESS_NODES).issubset(TRACKED_PROGRESS_NODES)


@pytest.mark.parametrize("node_name", UPLOADED_REWRITE_PROGRESS_NODES)
def test_wrap_node_with_progress_updates_uploaded_rewrite_nodes(monkeypatch, node_name: str):
    calls: list[tuple[str, str, bool]] = []

    class RecordingQueue:
        def is_task_cancelled(self, task_id: str) -> bool:
            return False

        def update_progress(self, task_id: str, tracked_node_name: str, completed: bool = True):
            calls.append((task_id, tracked_node_name, completed))

    monkeypatch.setattr(
        "backend.task.task_queue_manager.get_task_queue",
        lambda: RecordingQueue(),
    )

    wrapped = wrap_node_with_progress(lambda state, config=None: {"ok": True}, node_name)
    result = wrapped({}, {"configurable": {"task_id": "task-rewrite-1"}})

    assert result == {"ok": True}
    assert calls == [
        ("task-rewrite-1", node_name, False),
        ("task-rewrite-1", node_name, True),
    ]


def test_uploaded_rewrite_progress_can_reach_declared_total():
    queue = TaskQueueManager()
    task_id = "task-rewrite-1"

    with queue._data_lock:
        queue._tasks[task_id] = Task(
            task_id=task_id,
            user_session_id="session-1",
            created_at=datetime.now(),
            task_kind=TaskKind.REWRITE,
        )

    assert queue.set_total_nodes(task_id, 5) is True

    for node_name in UPLOADED_REWRITE_WORKFLOW_NODES:
        queue.update_progress(task_id, node_name, completed=False)
        queue.update_progress(task_id, node_name, completed=True)

    task = queue.get_task(task_id)
    assert task is not None
    assert task.progress.completed_nodes == UPLOADED_REWRITE_WORKFLOW_NODES
    assert task.progress.running_nodes == []
    assert task.progress.progress_text == "5/5"
    assert task.progress.progress_percent == 100.0
