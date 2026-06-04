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
        "file_path": None,
        "form_type": None,
        "insertion_config": None,
        "tender_lx": None,
        "fund_source_lx": None,
        "tender_data_snapshot": None,
    }
    assert result["task_id"] == "rewrite-task-42"
    assert result["task_kind"] == "rewrite"

@pytest.mark.asyncio
async def test_create_rewrite_task_tool_accepts_uploaded_file_context() -> None:
    captured: dict[str, object] = {}

    class FakeDocumentService:
        async def create_rewrite_task(self, **kwargs) -> GenerateResponse:
            captured.update(kwargs)
            return GenerateResponse(
                success=True,
                task_id="rewrite-upload-task-42",
                message="queued",
                task_kind=TaskKind.REWRITE,
                status=TaskStatus.QUEUED,
                queue_position=1,
                waiting_count=0,
            )

    tool = create_rewrite_task_tool(
        TaskContextAssistantToolContext(document_service=FakeDocumentService())
    )

    result = await tool.ainvoke(
        {
            "conversation_id": "conv-42",
            "form_type": "xjcg_tender",
            "model": "deepseek",
            "user_prompt": "把第三章采购需求补充完整",
            "file_path": "D:/UploadFiles/source.docx",
            "insertion_config": {
                "before_text": "第三章 采购需求",
                "after_text": "第四章 响应文件有关格式",
            },
            "tender_lx": 0,
            "fund_source_lx": 1,
            "tender_data_snapshot": {
                "project_name": "测试项目",
                "project_number": "XJ-001",
                "project_content": "采购内容",
                "buyer_name": "采购人",
                "bzj_rule": "规则",
                "project_zbr_xbr": "张三",
                "zbr_xbr_tel": "13800000000",
                "zbr_pinyin": "zhangsan",
                "shell_start_date": "2026-06-01",
                "shell_end_date": "2026-06-08",
                "submit_date": "2026-06-09",
                "platform": "平台",
                "service_fee": "1000",
                "tender_lx": 0,
                "fund_source_lx": 1,
            },
        }
    )

    assert tool.name == "create_rewrite_task_tool"
    assert captured["conversation_id"] == "conv-42"
    assert getattr(captured["form_type"], "value", captured["form_type"]) == "xjcg_tender"
    assert captured["model_provider"] == "deepseek"
    assert captured["user_prompt"] == "把第三章采购需求补充完整"
    assert captured["file_path"] == "D:/UploadFiles/source.docx"
    insertion_config = captured["insertion_config"]
    if hasattr(insertion_config, "model_dump"):
        insertion_config = insertion_config.model_dump(mode="json")
    assert insertion_config == {
        "before_text": "第三章 采购需求",
        "after_text": "第四章 响应文件有关格式",
    }
    assert captured["tender_lx"] == 0
    assert captured["fund_source_lx"] == 1
    snapshot = captured["tender_data_snapshot"]
    assert snapshot.project_name == "测试项目"
    assert snapshot.project_number == "XJ-001"
    assert snapshot.tender_lx == 0
    assert snapshot.fund_source_lx == 1
    assert result["task_id"] == "rewrite-upload-task-42"
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
