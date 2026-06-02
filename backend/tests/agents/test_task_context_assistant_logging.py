from __future__ import annotations

import json

from backend.agents.task_context_assistant.logging import AgentRunAuditLogger


def test_agent_run_audit_logger_scrubs_sensitive_values(tmp_path) -> None:
    logger = AgentRunAuditLogger(logs_dir=tmp_path)

    logger.append_event(
        event_name="thinking_stage",
        conversation_id="conv-1",
        selected_skills=["rewrite"],
        payload=type(
            "ThinkingEvent",
            (),
            {
                "run_id": "run-1",
                "stage": "understand",
                "label": "理解需求",
                "status": "completed",
                "summary": (
                    '已识别为 rewrite 请求：Authorization: Bearer secret-token '
                    'password="abc" /mnt/d/CompanyProject/TenderWord/backend/.env'
                ),
                "selected_skill": "rewrite",
                "guard_result": None,
                "tool_name": None,
            },
        )(),
    )
    logger.append_event(
        event_name="error",
        conversation_id="conv-1",
        selected_skills=["rewrite"],
        payload=type(
            "ErrorEvent",
            (),
            {
                "run_id": "run-1",
                "code": "AGENT_RUN_FAILED",
                "message": (
                    'Traceback (most recent call last):\nFile "/mnt/d/private.py", '
                    'line 1, in <module>'
                ),
            },
        )(),
    )

    log_path = logger.log_path_for_run("run-1")
    assert log_path.is_file()

    log_text = log_path.read_text(encoding="utf-8")
    assert "secret-token" not in log_text
    assert "password" not in log_text.lower()
    assert "authorization" not in log_text.lower()
    assert ".env" not in log_text
    assert "/mnt/d/CompanyProject/TenderWord" not in log_text
    assert "Traceback" not in log_text

    entries = [json.loads(line) for line in log_text.splitlines() if line.strip()]
    assert entries[0]["summary"] == "已识别为 rewrite 请求。"
    assert entries[1]["summary"] == "[REDACTED_STACK]"


def test_agent_run_audit_logger_reads_recent_conversation_summaries(tmp_path) -> None:
    logger = AgentRunAuditLogger(logs_dir=tmp_path)

    logger.append_event(
        event_name="run_started",
        conversation_id="conv-1",
        selected_skills=["rewrite"],
        payload=type("RunStarted1", (), {"run_id": "run-1", "runtime": "fake"})(),
    )
    logger.append_event(
        event_name="task_accepted",
        conversation_id="conv-1",
        selected_skills=["rewrite"],
        payload=type(
            "Accepted1",
            (),
            {
                "run_id": "run-1",
                "task_id": "rewrite-task-1",
                "task_kind": "rewrite",
                "status": "queued",
                "queue_position": 1,
                "waiting_count": 0,
            },
        )(),
    )
    logger.append_event(
        event_name="run_started",
        conversation_id="conv-2",
        selected_skills=["edit"],
        payload=type("RunStarted2", (), {"run_id": "run-2", "runtime": "fake"})(),
    )

    summaries = logger.read_conversation_summaries("conv-1", limit=2)

    assert summaries == [
        {
            "run_id": "run-1",
            "selected_skills": ["rewrite"],
            "latest_event": "task_accepted",
            "updated_at": summaries[0]["updated_at"],
            "guard_results": [],
            "tool_names": [],
            "stage_summaries": [],
            "task_id": "rewrite-task-1",
            "task_kind": "rewrite",
        }
    ]
