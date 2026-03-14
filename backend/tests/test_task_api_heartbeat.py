from __future__ import annotations

import sys
import types

import pytest

from backend.models.task import TaskHeartbeatResponse, TaskStatus


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


class DummyTaskService:
    def __init__(self, response):
        self.response = response
        self.task_ids: list[str] = []

    def heartbeat_task(self, task_id: str):
        self.task_ids.append(task_id)
        return self.response


def test_heartbeat_task_returns_alive_status(monkeypatch):
    service = DummyTaskService(
        TaskHeartbeatResponse(
            success=True,
            task_id="task-1",
            alive=True,
            status=TaskStatus.RUNNING,
        )
    )
    monkeypatch.setattr(tasks_api, "get_task_service", lambda: service)

    result = run_async_endpoint(tasks_api.heartbeat_task(task_id="task-1"))

    assert result.task_id == "task-1"
    assert result.alive is True
    assert result.status == TaskStatus.RUNNING
    assert service.task_ids == ["task-1"]


def test_heartbeat_task_returns_404_for_missing_task(monkeypatch):
    service = DummyTaskService(None)
    monkeypatch.setattr(tasks_api, "get_task_service", lambda: service)

    with pytest.raises(HTTPException) as exc_info:
        run_async_endpoint(tasks_api.heartbeat_task(task_id="missing-task"))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["error"]["code"] == "TASK_NOT_FOUND"
