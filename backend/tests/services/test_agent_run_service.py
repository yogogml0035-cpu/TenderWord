from __future__ import annotations

import json

import pytest

from backend.models import AgentRunStreamRequest, GenerateResponse, TaskKind, TaskStatus
from backend.services.agent_run_service import AgentRunService


class _ConnectedRequest:
    async def is_disconnected(self) -> bool:
        return False


async def _collect_events(service: AgentRunService, payload: AgentRunStreamRequest) -> list[dict]:
    lines: list[str] = []
    async for line in service.stream(_ConnectedRequest(), payload):
        lines.append(line)
    return [json.loads(line) for line in lines]


@pytest.mark.asyncio
async def test_stream_emits_task_created_sequence_for_rewrite() -> None:
    async def _create_rewrite_task(**kwargs) -> GenerateResponse:
        assert kwargs == {
            "conversation_id": "conv-1",
            "user_prompt": "请改写第三包",
            "model": "deepseek",
            "rewrite_log_path": None,
        }
        return GenerateResponse(
            success=True,
            task_id="rewrite-task-1",
            message="queued",
            task_kind=TaskKind.REWRITE,
            status=TaskStatus.QUEUED,
            queue_position=2,
            waiting_count=1,
        )

    service = AgentRunService(
        run_id_factory=lambda: "run-1",
        rewrite_task_executor=_create_rewrite_task,
    )
    payload = AgentRunStreamRequest.model_validate(
        {
            "conversation_id": "conv-1",
            "message": "请改写第三包",
            "model": "deepseek",
            "selected_skills": ["rewrite"],
            "context_snapshot": {
                "rewrite_available": True,
                "uploaded_files": [],
            },
        }
    )

    events = await _collect_events(service, payload)

    assert [item["event"] for item in events] == [
        "run_started",
        "thinking_stage",
        "thinking_stage",
        "tool_call",
        "task_accepted",
        "done",
    ]
    assert events[0]["data"]["run_id"] == "run-1"
    assert events[3]["data"]["tool_name"] == "create_rewrite_task_tool"
    assert events[4]["data"] == {
        "run_id": "run-1",
        "task_id": "rewrite-task-1",
        "task_kind": "rewrite",
        "status": "queued",
        "queue_position": 2,
        "waiting_count": 1,
    }
    assert events[5]["data"]["task_id"] == "rewrite-task-1"


@pytest.mark.asyncio
async def test_stream_returns_needs_input_when_rewrite_context_missing() -> None:
    service = AgentRunService(run_id_factory=lambda: "run-2")
    payload = AgentRunStreamRequest.model_validate(
        {
            "conversation_id": "conv-2",
            "message": "改写评分办法",
            "model": "deepseek",
            "selected_skills": ["rewrite"],
            "context_snapshot": {
                "rewrite_available": False,
                "uploaded_files": [],
            },
        }
    )

    events = await _collect_events(service, payload)

    assert [item["event"] for item in events] == [
        "run_started",
        "thinking_stage",
        "thinking_stage",
        "needs_input",
    ]
    assert events[-1]["data"]["message"] == "当前会话没有可用文档，请先完成一次生成。"
    assert events[-1]["data"]["missing_requirements"] == ["rewrite_history"]


@pytest.mark.asyncio
async def test_stream_returns_error_terminal_when_rewrite_tool_raises() -> None:
    async def _raise(**_kwargs) -> GenerateResponse:
        raise RuntimeError("boom")

    service = AgentRunService(
        run_id_factory=lambda: "run-3",
        rewrite_task_executor=_raise,
    )
    payload = AgentRunStreamRequest.model_validate(
        {
            "conversation_id": "conv-3",
            "message": "请改写第三包",
            "model": "deepseek",
            "selected_skills": ["rewrite"],
            "context_snapshot": {
                "rewrite_available": True,
                "uploaded_files": [],
            },
        }
    )

    events = await _collect_events(service, payload)

    assert [item["event"] for item in events] == ["run_started", "error"]
    assert events[-1]["data"]["code"] == "AGENT_RUN_FAILED"
    assert events[-1]["data"]["run_id"] == "run-3"
