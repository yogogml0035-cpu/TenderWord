from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace

import pytest

from backend.core.sse_manager import sse_manager
from backend.graphs.base_graph import invoke_with_timing_async
from backend.models.sse import SSEEventType
from backend.services.document_service import DocumentService, SSECallback
from backend.task.task_queue_manager import Task, TaskQueueManager, TaskStatus


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
def isolate_task_queue() -> None:
    queue = TaskQueueManager()
    reset_task_queue_state(queue)
    yield
    reset_task_queue_state(queue)


def test_run_graph_sends_nonfatal_sse_error_when_async_task_is_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue = TaskQueueManager()
    task_id = "task-cancel-1"
    queue._tasks[task_id] = Task(
        task_id=task_id,
        user_session_id="session-1",
        created_at=datetime.now(),
        status=TaskStatus.CANCELLED,
        error="user_cancelled",
        completed_at=datetime.now(),
    )

    service = DocumentService.__new__(DocumentService)
    service._task_queue = queue
    service._cleanup_temporary_output = lambda _path: None

    async def raise_cancelled(*_args, **_kwargs):
        raise asyncio.CancelledError()

    monkeypatch.setattr(service, "_invoke_graph_async", raise_cancelled)
    monkeypatch.setattr(
        sse_manager,
        "send_error_threadsafe",
        lambda **kwargs: sent_errors.append(kwargs),
    )
    monkeypatch.setattr(sse_manager, "send_progress_threadsafe", lambda **_kwargs: None)

    sent_errors: list[dict[str, object]] = []
    callback = SSECallback(task_id)
    graph_factory = lambda: SimpleNamespace(
        estimate_total_nodes=lambda _state: 1,
        compile=lambda: object(),
    )

    service._run_graph(
        task_id=task_id,
        graph_class=graph_factory,
        initial_state={},
        callback=callback,
        model_provider="deepseek",
    )

    task = queue.get_task(task_id)
    assert task is not None
    assert task.status == TaskStatus.CANCELLED
    assert task.error == "user_cancelled"

    callback_errors = [event for event in callback.get_events() if event.event == SSEEventType.ERROR]
    assert len(callback_errors) == 1
    assert callback_errors[0].data["is_fatal"] is False
    assert callback_errors[0].data["error"] == "任务已取消"

    assert sent_errors == [
        {
            "task_id": task_id,
            "task_kind": "generate",
            "error": "任务已取消",
            "is_fatal": False,
        }
    ]


def test_invoke_with_timing_async_keeps_cancelled_task_out_of_success_state() -> None:
    queue = TaskQueueManager()
    task_id = "task-cancel-graph-1"
    queue._tasks[task_id] = Task(
        task_id=task_id,
        user_session_id="session-1",
        created_at=datetime.now(),
    )
    queue._queue.append(task_id)

    class DummyLock:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    class CancellingGraph:
        async def ainvoke(self, *_args, **_kwargs):
            raise asyncio.CancelledError()

    async def run() -> None:
        with pytest.raises(asyncio.CancelledError):
            await invoke_with_timing_async(
                CancellingGraph(),
                {},
                verbose=False,
                config={"configurable": {"task_id": task_id}},
                lock=DummyLock(),
            )

    asyncio.run(run())

    task = queue.get_task(task_id)
    assert task is not None
    assert task.status == TaskStatus.CANCELLED
    assert task.result is None
    assert task.error == "任务已取消"
