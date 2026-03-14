from __future__ import annotations

import sys
import types
from datetime import datetime, timezone

import pytest

from backend.models.task import TaskInfo, TaskProgress, TaskResponse, TaskStatus
from backend.services.task_service import TaskService
from backend.task.task_queue_manager import TaskQueueManager


def install_fastapi_stub() -> None:
    if "fastapi" in sys.modules:
        return

    fastapi_module = types.ModuleType("fastapi")
    responses_module = types.ModuleType("fastapi.responses")

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail=None):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class APIRouter:
        def __init__(self, *args, **kwargs):
            pass

        def get(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        def post(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        def delete(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

    def passthrough(default=None, *args, **kwargs):
        return default

    fastapi_module.APIRouter = APIRouter
    fastapi_module.HTTPException = HTTPException
    fastapi_module.Path = passthrough
    fastapi_module.Query = passthrough
    fastapi_module.Header = passthrough
    fastapi_module.Request = object
    fastapi_module.status = types.SimpleNamespace(
        HTTP_404_NOT_FOUND=404,
        HTTP_409_CONFLICT=409,
    )
    responses_module.StreamingResponse = object

    sys.modules["fastapi"] = fastapi_module
    sys.modules["fastapi.responses"] = responses_module


install_fastapi_stub()

from fastapi import HTTPException

import backend.api.tasks as tasks_api


def run_async_endpoint(coro):
    try:
        coro.send(None)
    except StopIteration as exc:
        return exc.value
    raise AssertionError("Endpoint coroutine yielded unexpectedly during test execution")


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


def seed_running_progress(task_queue: TaskQueueManager, task_id: str, total_nodes: int = 7) -> None:
    task_queue.set_total_nodes(task_id, total_nodes)
    task_queue.update_progress(task_id, "prepare_template", completed=True)
    task_queue.update_progress(task_id, "extract_tender_params", completed=False)


def test_task_api_service_serializes_progress_fields(task_queue):
    task_queue.add_task("task-running", "session-1")
    task_queue.start_task("task-running")
    seed_running_progress(task_queue, "task-running", total_nodes=7)

    result = TaskService(task_queue).get_task("task-running")

    assert result is not None
    assert result.data is not None
    assert result.data.progress.progress_text == "1/7"
    assert result.data.progress.progress_percent == pytest.approx(14.3)
    assert result.data.progress.current_node == "extract_tender_params"
    assert result.data.progress.current_node_display == "提取原始采购需求"
    assert result.data.current_running_progress is None


def test_task_api_service_includes_current_running_progress_for_queued_task(task_queue):
    task_queue.add_task("task-running", "session-1")
    task_queue.add_task("task-queued", "session-2")
    task_queue.start_task("task-running")
    seed_running_progress(task_queue, "task-running", total_nodes=7)

    result = TaskService(task_queue).get_task("task-queued")

    assert result is not None
    assert result.data is not None
    assert result.data.current_running_progress is not None
    assert result.data.current_running_progress.task_id == "task-running"
    assert result.data.current_running_progress.status == TaskStatus.RUNNING
    assert result.data.current_running_progress.progress_text == "1/7"
    assert result.data.current_running_progress.progress_percent == pytest.approx(14.3)
    assert result.data.current_running_progress.current_node_display == "提取原始采购需求"


def test_task_api_service_omits_current_running_progress_without_active_runner(task_queue):
    task_queue.add_task("task-queued", "session-1")

    result = TaskService(task_queue).get_task("task-queued")

    assert result is not None
    assert result.data is not None
    assert result.data.current_running_progress is None
    assert result.data.progress.progress_percent == pytest.approx(0.0)
    assert result.data.progress.progress_text == f"0/{result.data.progress.total_nodes}"


class DummyTaskStatusService:
    def __init__(self, response):
        self.response = response
        self.task_ids: list[str] = []

    def get_task(self, task_id: str):
        self.task_ids.append(task_id)
        return self.response


def test_task_api_route_returns_current_running_progress(monkeypatch):
    response = TaskResponse(
        success=True,
        task_id="task-queued",
        message="获取任务成功",
        data=TaskInfo(
            task_id="task-queued",
            user_session_id="session-1",
            status=TaskStatus.QUEUED,
            created_at=datetime.now(timezone.utc),
            queue_position=1,
            waiting_count=1,
            progress=TaskProgress(
                task_id="task-queued",
                status=TaskStatus.QUEUED,
                completed_count=0,
                total_nodes=7,
                progress_text="0/7",
                progress_percent=0.0,
                completed_nodes=[],
            ),
            current_running_progress=TaskProgress(
                task_id="task-running",
                status=TaskStatus.RUNNING,
                completed_count=1,
                total_nodes=10,
                progress_text="1/10",
                progress_percent=10.0,
                current_node="extract_tender_params",
                current_node_display="提取原始采购需求",
                completed_nodes=["prepare_template"],
            ),
        ),
    )
    service = DummyTaskStatusService(response)
    monkeypatch.setattr(tasks_api, "get_task_service", lambda: service)

    result = run_async_endpoint(tasks_api.get_task(task_id="task-queued"))

    assert result.data is not None
    assert result.data.current_running_progress is not None
    assert result.data.current_running_progress.progress_text == "1/10"
    assert result.data.current_running_progress.progress_percent == pytest.approx(10.0)
    assert service.task_ids == ["task-queued"]


def test_task_api_route_returns_404_for_missing_task(monkeypatch):
    service = DummyTaskStatusService(None)
    monkeypatch.setattr(tasks_api, "get_task_service", lambda: service)

    with pytest.raises(HTTPException) as exc_info:
        run_async_endpoint(tasks_api.get_task(task_id="missing-task"))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["error"]["code"] == "TASK_NOT_FOUND"
