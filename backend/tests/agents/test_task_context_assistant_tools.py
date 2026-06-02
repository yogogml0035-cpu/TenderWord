from __future__ import annotations

from datetime import datetime

import pytest

from backend.agents.task_context_assistant import (
    AgentRunAuditLogger,
    TaskContextAssistantToolContext,
    create_read_current_conversation_summary_tool,
    create_read_current_task_public_summary_tool,
    create_rewrite_task_tool,
)
from backend.models import (
    GenerateResponse,
    TaskInfo,
    TaskKind,
    TaskProgress,
    TaskResponse,
    TaskStatus,
)


@pytest.mark.asyncio
async def test_create_rewrite_task_tool_reuses_document_service() -> None:
    captured: dict[str, object] = {}

    class FakeDocumentService:
        async def create_rewrite_task(self, **kwargs) -> GenerateResponse:
            captured.update(kwargs)
            return GenerateResponse(
                success=True,
                task_id="rewrite-task-42",
                message="queued",
                task_kind=TaskKind.REWRITE,
                status=TaskStatus.QUEUED,
                queue_position=0,
                waiting_count=0,
            )

    tool = create_rewrite_task_tool(
        TaskContextAssistantToolContext(document_service=FakeDocumentService())
    )

    result = await tool.ainvoke(
        {
            "conversation_id": "conv-42",
            "user_prompt": "改写第三包技术参数",
            "model": "deepseek",
            "rewrite_log_path": "backend/logs/rewrite-task-42.jsonl",
        }
    )

    assert tool.name == "create_rewrite_task_tool"
    assert captured == {
        "conversation_id": "conv-42",
        "user_prompt": "改写第三包技术参数",
        "model_provider": "deepseek",
        "rewrite_log_path": "backend/logs/rewrite-task-42.jsonl",
    }
    assert result["task_id"] == "rewrite-task-42"
    assert result["task_kind"] == "rewrite"


@pytest.mark.asyncio
async def test_read_current_conversation_summary_tool_returns_scrubbed_context(
    tmp_path,
) -> None:
    audit_logger = AgentRunAuditLogger(logs_dir=tmp_path)
    audit_logger.append_event(
        event_name="run_started",
        conversation_id="conv-42",
        selected_skills=["rewrite"],
        payload=type(
            "RunStarted",
            (),
            {
                "run_id": "run-42",
                "runtime": "fake",
            },
        )(),
    )
    audit_logger.append_event(
        event_name="done",
        conversation_id="conv-42",
        selected_skills=["rewrite"],
        payload=type(
            "DoneEvent",
            (),
            {
                "run_id": "run-42",
                "message": "已创建 rewrite 任务。",
                "task_id": "rewrite-task-42",
                "selected_skill": "rewrite",
            },
        )(),
    )

    class FakeConversationService:
        def has_rewrite_history(self, conversation_id: str) -> bool:
            assert conversation_id == "conv-42"
            return True

        def get_latest_rewrite_state(self, conversation_id: str) -> dict[str, object]:
            assert conversation_id == "conv-42"
            return {
                "prepared_doc_path": "/private/customer.docx",
                "polished_text": "完整客户原文",
                "comment_writeback_summary": "AI批注写入完成",
            }

    tool = create_read_current_conversation_summary_tool(
        TaskContextAssistantToolContext(
            conversation_service=FakeConversationService(),
            agent_run_audit_logger=audit_logger,
        )
    )

    result = await tool.ainvoke({"conversation_id": "conv-42", "limit": 1})

    assert tool.name == "read_current_conversation_summary_tool"
    assert result["conversation_id"] == "conv-42"
    assert result["rewrite_available"] is True
    assert result["latest_rewrite_context"] == {
        "has_prepared_doc": True,
        "has_polished_text": True,
        "has_comment_metadata": True,
        "has_style_writeback_summary": False,
    }
    assert result["recent_agent_runs"] == [
        {
            "run_id": "run-42",
            "selected_skills": ["rewrite"],
            "latest_event": "done",
            "updated_at": result["recent_agent_runs"][0]["updated_at"],
            "guard_results": [],
            "tool_names": [],
            "stage_summaries": [
                {
                    "event": "done",
                    "summary": "已创建 rewrite 任务。",
                }
            ],
            "task_id": "rewrite-task-42",
            "task_kind": None,
        }
    ]


@pytest.mark.asyncio
async def test_read_current_task_public_summary_tool_omits_private_result_fields() -> None:
    class FakeTaskService:
        def get_task(self, task_id: str) -> TaskResponse:
            assert task_id == "task-42"
            return TaskResponse(
                success=True,
                task_id=task_id,
                message="ok",
                data=TaskInfo(
                    task_id=task_id,
                    user_session_id="conv-42",
                    task_kind=TaskKind.REWRITE,
                    status=TaskStatus.RUNNING,
                    created_at=datetime(2026, 6, 2, 12, 0, 0),
                    queue_position=0,
                    waiting_count=0,
                    result={
                        "output_file": "/mnt/d/private/output.docx",
                        "download_url": "/api/download/file.docx",
                    },
                    error='Traceback (most recent call last):\nFile "/tmp/private.py"',
                    progress=TaskProgress(
                        task_id=task_id,
                        status=TaskStatus.RUNNING,
                        completed_count=2,
                        total_nodes=7,
                        progress_text="2/7",
                        progress_percent=28.6,
                        current_node="rewrite_text",
                        current_node_display="AI重写内容",
                    ),
                ),
            )

    tool = create_read_current_task_public_summary_tool(
        TaskContextAssistantToolContext(task_service=FakeTaskService())
    )

    result = await tool.ainvoke({"conversation_id": "conv-42", "task_id": "task-42"})

    assert tool.name == "read_current_task_public_summary_tool"
    assert result == {
        "task_id": "task-42",
        "available": True,
        "task_kind": "rewrite",
        "status": "running",
        "queue_position": 0,
        "waiting_count": 0,
        "progress": {
            "progress_text": "2/7",
            "progress_percent": 28.6,
            "current_node_display": "AI重写内容",
        },
        "has_result": True,
        "download_ready": True,
        "error": "[REDACTED_STACK]",
    }
