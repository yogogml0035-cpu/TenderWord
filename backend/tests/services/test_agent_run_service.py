from __future__ import annotations

import json

import pytest

from backend.agents.task_context_assistant import AgentRunAuditLogger
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

TENDER_DATA_SNAPSHOT = {
    "project_name": "测试项目",
    "project_number": "XJ-001",
    "project_content": "采购需求",
    "buyer_name": "采购人",
    "tender_lx": 0,
    "fund_source_lx": 1,
}


@pytest.mark.asyncio
async def test_stream_emits_task_created_sequence_for_rewrite(tmp_path) -> None:
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

    audit_logger = AgentRunAuditLogger(logs_dir=tmp_path)
    service = AgentRunService(
        run_id_factory=lambda: "run-1",
        rewrite_task_executor=_create_rewrite_task,
        audit_logger=audit_logger,
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

    log_entries = [
        json.loads(line)
        for line in audit_logger.log_path_for_run("run-1").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [entry["event"] for entry in log_entries] == [
        "run_started",
        "thinking_stage",
        "thinking_stage",
        "tool_call",
        "task_accepted",
        "done",
    ]
    assert log_entries[0]["selected_skills"] == ["rewrite"]
    assert log_entries[1]["summary"] == "已识别为 rewrite 请求。"
    assert log_entries[2]["guard_result"] == "passed"
    assert log_entries[3]["tool_name"] == "create_rewrite_task_tool"
    assert log_entries[4]["task_id"] == "rewrite-task-1"
    assert "请改写第三包" not in audit_logger.log_path_for_run("run-1").read_text(
        encoding="utf-8"
    )


@pytest.mark.asyncio
async def test_stream_returns_needs_input_when_rewrite_context_missing(tmp_path) -> None:
    audit_logger = AgentRunAuditLogger(logs_dir=tmp_path)
    service = AgentRunService(run_id_factory=lambda: "run-2", audit_logger=audit_logger)
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

    log_entries = [
        json.loads(line)
        for line in audit_logger.log_path_for_run("run-2").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert log_entries[-2]["guard_result"] == "needs_input"
    assert log_entries[-1]["summary"] == "当前会话没有可用文档，请先完成一次生成。"
    assert "task_id" not in log_entries[-1]


@pytest.mark.asyncio
async def test_stream_returns_error_terminal_when_rewrite_tool_raises(tmp_path) -> None:
    async def _raise(**_kwargs) -> GenerateResponse:
        raise RuntimeError("Traceback (most recent call last): password=boom")

    audit_logger = AgentRunAuditLogger(logs_dir=tmp_path)
    service = AgentRunService(
        run_id_factory=lambda: "run-3",
        rewrite_task_executor=_raise,
        audit_logger=audit_logger,
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

    log_text = audit_logger.log_path_for_run("run-3").read_text(encoding="utf-8")
    assert "Traceback" not in log_text
    assert "password" not in log_text.lower()
    log_entries = [json.loads(line) for line in log_text.splitlines() if line.strip()]
    assert log_entries[-1]["summary"] == "agent run 执行失败，请稍后重试"

@pytest.mark.asyncio
async def test_stream_emits_task_created_sequence_for_uploaded_file_rewrite(tmp_path) -> None:
    async def _create_rewrite_task(**kwargs) -> GenerateResponse:
        assert kwargs["conversation_id"] == "conv-rewrite-upload-1"
        assert getattr(kwargs["form_type"], "value", kwargs["form_type"]) == "xjcg_tender"
        assert getattr(kwargs["model"], "value", kwargs["model"]) == "deepseek"
        assert kwargs["user_prompt"] == "请修改第三章采购需求"
        assert kwargs["file_path"] == "D:/UploadFiles/source.docx"
        assert kwargs["insertion_config"].before_text == "第三章 采购需求"
        assert kwargs["insertion_config"].after_text == "第四章 响应文件有关格式"
        assert kwargs["tender_lx"] == 0
        assert kwargs["fund_source_lx"] == 1
        assert kwargs["tender_data_snapshot"].project_name == "测试项目"
        return GenerateResponse(
            success=True,
            task_id="rewrite-upload-task-1",
            message="queued",
            task_kind=TaskKind.REWRITE,
            status=TaskStatus.QUEUED,
            queue_position=1,
            waiting_count=0,
        )

    audit_logger = AgentRunAuditLogger(logs_dir=tmp_path)
    service = AgentRunService(
        run_id_factory=lambda: "run-rewrite-upload-1",
        rewrite_task_executor=_create_rewrite_task,
        audit_logger=audit_logger,
    )
    payload = AgentRunStreamRequest.model_validate(
        {
            "conversation_id": "conv-rewrite-upload-1",
            "message": "请修改第三章采购需求",
            "model": "deepseek",
            "selected_skills": ["rewrite"],
            "context_snapshot": {
                "rewrite_available": False,
                "uploaded_files": [
                    {
                        "file_path": "D:/UploadFiles/source.docx",
                        "file_name": "source.docx",
                    }
                ],
                "rewrite_context": {
                    "form_type": "xjcg_tender",
                    "insertion_config": {
                        "before_text": "第三章 采购需求",
                        "after_text": "第四章 响应文件有关格式",
                    },
                    "tender_lx": 0,
                    "fund_source_lx": 1,
                    "tender_data_snapshot": TENDER_DATA_SNAPSHOT,
                },
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
    assert events[3]["data"]["tool_name"] == "create_rewrite_task_tool"
    assert events[4]["data"] == {
        "run_id": "run-rewrite-upload-1",
        "task_id": "rewrite-upload-task-1",
        "task_kind": "rewrite",
        "status": "queued",
        "queue_position": 1,
        "waiting_count": 0,
    }
    assert events[5]["data"]["task_id"] == "rewrite-upload-task-1"

    log_entries = [
        json.loads(line)
        for line in audit_logger.log_path_for_run("run-rewrite-upload-1").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [entry["event"] for entry in log_entries] == [
        "run_started",
        "thinking_stage",
        "thinking_stage",
        "tool_call",
        "task_accepted",
        "done",
    ]
    assert log_entries[2]["guard_result"] == "passed"
    assert log_entries[3]["tool_name"] == "create_rewrite_task_tool"
    assert log_entries[4]["task_id"] == "rewrite-upload-task-1"

@pytest.mark.asyncio
async def test_stream_returns_needs_input_when_rewrite_skill_has_no_file_or_history(tmp_path) -> None:
    audit_logger = AgentRunAuditLogger(logs_dir=tmp_path)
    service = AgentRunService(run_id_factory=lambda: "run-rewrite-2", audit_logger=audit_logger)
    payload = AgentRunStreamRequest.model_validate(
        {
            "conversation_id": "conv-rewrite-2",
            "message": "请修改第三章采购需求",
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
async def test_stream_returns_needs_input_when_uploaded_rewrite_anchor_missing(tmp_path) -> None:
    audit_logger = AgentRunAuditLogger(logs_dir=tmp_path)
    service = AgentRunService(run_id_factory=lambda: "run-rewrite-upload-3", audit_logger=audit_logger)
    payload = AgentRunStreamRequest.model_validate(
        {
            "conversation_id": "conv-rewrite-upload-3",
            "message": "请修改第三章采购需求",
            "model": "deepseek",
            "selected_skills": ["rewrite"],
            "context_snapshot": {
                "rewrite_available": False,
                "uploaded_files": [
                    {
                        "file_path": "D:/UploadFiles/source.docx",
                        "file_name": "source.docx",
                    }
                ],
                "rewrite_context": {
                    "form_type": "xjcg_tender",
                    "insertion_config": {
                        "before_text": "第三章 采购需求",
                        "after_text": "",
                    },
                    "tender_lx": 0,
                    "fund_source_lx": 1,
                    "tender_data_snapshot": TENDER_DATA_SNAPSHOT,
                },
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
    assert events[-1]["data"]["message"] == "请先补全当前页面的插入锚点。"
    assert events[-1]["data"]["missing_requirements"] == ["insertion_config"]

@pytest.mark.asyncio
async def test_stream_returns_needs_input_when_uploaded_rewrite_form_context_missing(tmp_path) -> None:
    audit_logger = AgentRunAuditLogger(logs_dir=tmp_path)
    service = AgentRunService(run_id_factory=lambda: "run-rewrite-upload-4", audit_logger=audit_logger)
    payload = AgentRunStreamRequest.model_validate(
        {
            "conversation_id": "conv-rewrite-upload-4",
            "message": "请修改第三章采购需求",
            "model": "deepseek",
            "selected_skills": ["rewrite"],
            "context_snapshot": {
                "rewrite_available": False,
                "uploaded_files": [
                    {
                        "file_path": "D:/UploadFiles/source.docx",
                        "file_name": "source.docx",
                    }
                ],
                "rewrite_context": {
                    "insertion_config": {
                        "before_text": "第三章 采购需求",
                        "after_text": "第四章 响应文件有关格式",
                    },
                    "tender_lx": 0,
                    "fund_source_lx": 1,
                    "tender_data_snapshot": TENDER_DATA_SNAPSHOT,
                },
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
    assert events[-1]["data"]["message"] == "请先补全当前页面的招标类型。"
    assert events[-1]["data"]["missing_requirements"] == ["form_type"]

@pytest.mark.asyncio
async def test_stream_returns_needs_input_when_uploaded_rewrite_tender_data_missing(tmp_path) -> None:
    audit_logger = AgentRunAuditLogger(logs_dir=tmp_path)
    service = AgentRunService(run_id_factory=lambda: "run-rewrite-upload-5", audit_logger=audit_logger)
    payload = AgentRunStreamRequest.model_validate(
        {
            "conversation_id": "conv-rewrite-upload-5",
            "message": "请修改第三章采购需求",
            "model": "deepseek",
            "selected_skills": ["rewrite"],
            "context_snapshot": {
                "rewrite_available": False,
                "uploaded_files": [
                    {
                        "file_path": "D:/UploadFiles/source.docx",
                        "file_name": "source.docx",
                    }
                ],
                "rewrite_context": {
                    "form_type": "xjcg_tender",
                    "insertion_config": {
                        "before_text": "第三章 采购需求",
                        "after_text": "第四章 响应文件有关格式",
                    },
                    "tender_lx": 0,
                    "fund_source_lx": 1,
                },
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
    assert events[-1]["data"]["message"] == "请先补全当前页面的招标数据。"
    assert events[-1]["data"]["missing_requirements"] == ["tender_data_snapshot"]
