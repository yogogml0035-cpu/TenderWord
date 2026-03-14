from __future__ import annotations

import asyncio
import sys
import types

import pytest


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

    class StreamingResponse:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

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
        HTTP_502_BAD_GATEWAY=502,
    )
    responses_module.StreamingResponse = StreamingResponse

    sys.modules["fastapi"] = fastapi_module
    sys.modules["fastapi.responses"] = responses_module


install_fastapi_stub()

from fastapi import HTTPException

import backend.api.stream as stream_api


class DummyRequest:
    async def is_disconnected(self) -> bool:
        return False


class MissingTaskService:
    def get_task(self, task_id: str):
        return None


def test_stream_task_events_returns_404_for_missing_task(monkeypatch):
    monkeypatch.setattr(stream_api, "get_task_service", lambda: MissingTaskService())

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            stream_api.stream_task_events(
                request=DummyRequest(),
                task_id="missing-task",
            )
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["error"]["code"] == "TASK_NOT_FOUND"
