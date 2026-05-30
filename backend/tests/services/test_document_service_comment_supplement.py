from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from backend.models import CommentSupplementRequest, LLMModel, TaskKind
from backend.services import document_service
from backend.services.document_service import DocumentService, SSECallback

class _ConversationService:
    def __init__(self, latest_state: dict[str, Any] | None = None) -> None:
        self.latest_state = latest_state
        self.appended: dict[str, Any] | None = None

    def get_latest_rewrite_state(self, conversation_id: str):
        assert conversation_id == "conv-1"
        return self.latest_state

    def append_comment_supplement_success(self, **kwargs) -> None:
        self.appended = kwargs

class _TaskQueue:
    def __init__(self) -> None:
        self.completed: dict[str, Any] | None = None

    def set_total_nodes(self, task_id: str, total_nodes: int) -> None:
        assert task_id == "task-1"
        assert total_nodes == 4

    def complete_task(self, task_id: str, result=None, error=None) -> None:
        self.completed = {"task_id": task_id, "result": result, "error": error}

def _service_with_conversation(latest_state: dict[str, Any] | None) -> DocumentService:
    service = DocumentService.__new__(DocumentService)
    service._conversation_service = _ConversationService(latest_state)
    service._task_queue = _TaskQueue()
    service._callbacks = {}
    return service

@pytest.mark.asyncio
async def test_create_comment_supplement_task_validates_and_submits(monkeypatch, tmp_path: Path) -> None:
    source_file = tmp_path / "generated.docx"
    source_file.write_bytes(b"word")
    service = _service_with_conversation(
        {
            "tender_type": "xjcg",
            "prepared_doc_path": str(source_file),
            "polished_text": "投标人须提供原厂授权函。",
            "insertion_before_text": "第三章  采购需求",
            "insertion_after_text": "第四章  响应文件有关格式",
            "comment_plan_detail": [{"content": "内部依据"}],
        }
    )
    submitted: dict[str, Any] = {}

    monkeypatch.setattr(service, "_allocate_task_callback_pair", lambda: ("task-1", object()))
    monkeypatch.setattr(
        document_service,
        "COMMENT_SUPPLEMENT_GRAPH_CLASS",
        object,
    )

    def fake_submit(**kwargs):
        submitted.update(kwargs)
        from backend.models import GenerateResponse

        return GenerateResponse(
            success=True,
            task_id=kwargs["task_id"],
            task_kind=TaskKind.COMMENT_SUPPLEMENT,
            message="任务已创建",
        )

    monkeypatch.setattr(service, "_submit_graph_task", fake_submit)

    response = await service.create_comment_supplement_task(
        CommentSupplementRequest(
            conversation_id="conv-1",
            source_file=str(source_file),
            model=LLMModel.QWEN,
        )
    )

    assert response.success is True
    assert response.task_kind == TaskKind.COMMENT_SUPPLEMENT
    assert submitted["task_kind"] == "comment_supplement"
    assert submitted["model_provider"] == "qwen"
    assert submitted["conversation_id"] == "conv-1"
    assert submitted["llm_node_name"] == "generate_comments"
    assert submitted["initial_state"]["prepared_doc_path"] == str(source_file.resolve())
    assert submitted["initial_state"]["comment_supplement_source_file"] == str(source_file.resolve())
    assert submitted["initial_state"]["polished_text"] == "投标人须提供原厂授权函。"
    assert submitted["initial_state"]["comment_plan_detail"] == [{"content": "内部依据"}]

@pytest.mark.asyncio
async def test_create_comment_supplement_task_rejects_missing_rewrite_state(monkeypatch, tmp_path: Path) -> None:
    source_file = tmp_path / "generated.docx"
    source_file.write_bytes(b"word")
    service = _service_with_conversation(None)
    monkeypatch.setattr(service, "_allocate_task_callback_pair", lambda: ("task-1", object()))

    response = await service.create_comment_supplement_task(
        CommentSupplementRequest(conversation_id="conv-1", source_file=str(source_file))
    )

    assert response.success is False
    assert response.error == "COMMENT_SUPPLEMENT_NO_DOCUMENT"

@pytest.mark.asyncio
async def test_create_comment_supplement_task_rejects_stale_source_file(monkeypatch, tmp_path: Path) -> None:
    latest_file = tmp_path / "latest.docx"
    source_file = tmp_path / "stale.docx"
    latest_file.write_bytes(b"latest")
    source_file.write_bytes(b"stale")
    service = _service_with_conversation(
        {
            "prepared_doc_path": str(latest_file),
            "polished_text": "正文",
        }
    )
    monkeypatch.setattr(service, "_allocate_task_callback_pair", lambda: ("task-1", object()))

    response = await service.create_comment_supplement_task(
        CommentSupplementRequest(conversation_id="conv-1", source_file=str(source_file))
    )

    assert response.success is False
    assert response.error == "COMMENT_SUPPLEMENT_SOURCE_MISMATCH"

def test_run_graph_updates_latest_rewrite_state_for_comment_supplement(
    monkeypatch,
    tmp_path: Path,
) -> None:
    output_file = tmp_path / "supplement.docx"
    output_file.write_bytes(b"word")
    service = _service_with_conversation({})
    callback = SSECallback("task-1")

    class FakeGraph:
        def estimate_total_nodes(self, initial_state):
            return 4

        def compile(self):
            return object()

    async def fake_invoke(*args, **kwargs):
        return (
            {
                "tender_type": "xjcg",
                "prepared_doc_path": str(output_file),
                "polished_text": "补充后的正文上下文",
                "comment_writeback_result": {
                    "summary": "AI批注写入: 生成=1, 成功=1, 失败=0, 跳过=0",
                    "generated": 1,
                    "added": 1,
                    "failed": 0,
                    "skipped": 0,
                    "warning": False,
                },
            },
            0.5,
        )

    monkeypatch.setattr(service, "_invoke_graph_async", fake_invoke)
    from backend.core.sse_manager import sse_manager

    monkeypatch.setattr(sse_manager, "send_done_threadsafe", lambda **_kwargs: None)

    service._run_graph(
        "task-1",
        FakeGraph,
        {
            "task_id": "task-1",
            "conversation_id": "conv-1",
            "user_session_id": "conv-1",
            "tender_type": "xjcg",
            "prepared_doc_path": str(tmp_path / "source.docx"),
            "polished_text": "原正文上下文",
        },
        callback,
        "deepseek",
        task_kind="comment_supplement",
        conversation_id="conv-1",
        llm_node_name="generate_comments",
    )

    assert service._conversation_service.appended is not None
    rewrite_state = service._conversation_service.appended["rewrite_state"]
    assert rewrite_state["prepared_doc_path"] == str(output_file)
    assert rewrite_state["polished_text"] == "补充后的正文上下文"
    assert service._task_queue.completed is not None
    assert service._task_queue.completed["result"]["comment_writeback"]["added"] == 1
    done_events = [event for event in callback.get_events() if event.event.value == "done"]
    assert done_events[0].data["task_kind"] == "comment_supplement"
    assert done_events[0].data["comment_writeback"]["added"] == 1
