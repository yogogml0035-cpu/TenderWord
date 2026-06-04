from __future__ import annotations

import json

import pytest

from backend.api import agent as agent_api
from backend.models import AgentRunStreamRequest


class _Request:
    async def is_disconnected(self) -> bool:
        return False


async def _read_streaming_response(response) -> list[dict]:
    lines: list[str] = []
    async for chunk in response.body_iterator:
        text = chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk)
        lines.extend(line for line in text.splitlines() if line.strip())
    return [json.loads(line) for line in lines]


@pytest.mark.asyncio
async def test_stream_agent_run_returns_ndjson_stream(monkeypatch) -> None:
    class FakeAgentRunService:
        async def stream(self, request, payload):
            assert request is not None
            assert payload.conversation_id == "conv-1"
            yield (
                '{"event":"run_started","data":{"run_id":"run-1","conversation_id":"conv-1",'
                '"model":"deepseek","runtime":"fake","selected_skills":["rewrite"]}}\n'
            )

    monkeypatch.setattr(
        agent_api,
        "get_agent_run_service",
        lambda: FakeAgentRunService(),
    )

    response = await agent_api.stream_agent_run(
        _Request(),
        AgentRunStreamRequest.model_validate(
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
        ),
    )

    events = await _read_streaming_response(response)

    assert response.media_type == "application/x-ndjson"
    assert response.headers["Cache-Control"] == "no-cache"
    assert response.headers["X-Accel-Buffering"] == "no"
    assert events[0]["event"] == "run_started"
    assert events[0]["data"]["selected_skills"] == ["rewrite"]
