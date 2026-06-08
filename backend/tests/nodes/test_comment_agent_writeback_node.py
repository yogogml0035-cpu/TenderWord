from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from backend.nodes.common_word_nodes import comment_agent as comment_agent_node
from backend.nodes.common_word_nodes.comment_agent import comment_agent_writeback
from backend.prompts.comment_prompt import render_comment_prompt
from backend.prompts.types import CommentPromptInput


@pytest.fixture(autouse=True)
def _disable_bad_case_context(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        comment_agent_node,
        "_build_bad_case_context_for_comment_agent",
        lambda _polished_text: ([], None),
    )
    monkeypatch.setattr(comment_agent_node, "COMMENT_AGENT_AUDIT_ROOT", tmp_path)


def _patch_word_success(monkeypatch) -> None:
    monkeypatch.setattr(
        comment_agent_node,
        "create_word_application",
        lambda **_kwargs: (object(), False),
    )
    monkeypatch.setattr(
        comment_agent_node,
        "open_document_with_retry",
        lambda **_kwargs: object(),
    )
    monkeypatch.setattr(
        comment_agent_node,
        "unprotect_document",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        comment_agent_node,
        "find_anchor_range",
        lambda *_args, **_kwargs: (object(), object()),
    )
    monkeypatch.setattr(
        comment_agent_node,
        "resolve_anchor_content_range",
        lambda **_kwargs: {"range_start": 0, "range_end": 20},
    )
    monkeypatch.setattr(
        comment_agent_node,
        "save_document_with_retry",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        comment_agent_node,
        "close_word_application",
        lambda **_kwargs: None,
    )


def test_comment_agent_writeback_degrades_missing_word_context_to_warning() -> None:
    events = []
    result = comment_agent_writeback(
        {
            "generation_mode": "agent",
            "polished_text": "正文锚点",
            "polished_comments": [
                {
                    "reference_text": "正文锚点",
                    "comment_text": "补充审查意见",
                }
            ],
            "generated_comment_count": 1,
        },
        config={
            "configurable": {
                "task_id": "task-1",
                "task_kind": "generate",
                "agent_step_callback": events.append,
            }
        },
    )

    assert result["comment_writeback_result"]["warning"] is True
    assert result["comment_writeback_result"]["generated"] == 1
    assert result["comment_writeback_result"]["failed"] == 1
    assert result["comment_writeback_added"] == 0
    assert result["comment_writeback_failed"] == 1
    assert result["comment_writeback_errors"][0]["reason"] == "missing_comment_agent_anchor_context"
    assert events[-1].node == "comment_agent"
    assert events[-1].step_type == "final"
    assert events[-1].is_complete is True


def test_comment_agent_writeback_skips_empty_candidates_without_warning() -> None:
    result = comment_agent_writeback(
        {
            "polished_text": "正文",
            "polished_comments": [],
            "generated_comment_count": 0,
        },
        config={"configurable": {"task_id": "task-1", "task_kind": "generate"}},
    )

    assert result["comment_writeback_result"]["warning"] is False
    assert result["comment_writeback_result"]["generated"] == 0
    assert result["comment_writeback_result"]["failed"] == 0


def test_comment_agent_writeback_allows_agent_generation_without_candidates(monkeypatch) -> None:
    captured = {}

    _patch_word_success(monkeypatch)

    def fake_run_comment_agent(**kwargs):
        captured.update(kwargs)
        expected_prompt = render_comment_prompt(
            CommentPromptInput(
                tender_type="xjcg",
                polished_text="投标人须提供原厂授权函。",
            )
        )
        assert kwargs["initial_comments"] == []
        assert kwargs["allow_comment_generation"] is True
        assert (
            kwargs["comment_generation_instruction"]
            == expected_prompt.system_prompt + "\n\n" + expected_prompt.user_prompt
        )
        return SimpleNamespace(
            validation=SimpleNamespace(passed=[object()], failed=[], skipped=[]),
            writeback_result={
                "total": 1,
                "attempted": 1,
                "added": 1,
                "failed": 0,
                "skipped": 0,
                "issues": [],
            },
            audit_log_path=None,
            final_proposed_comments=[
                {
                    "reference_text": "投标人须提供原厂授权函",
                    "comment_text": "建议提示：不得要求原厂授权函。",
                }
            ],
        )

    monkeypatch.setattr(comment_agent_node, "run_comment_agent", fake_run_comment_agent)

    result = comment_agent_writeback(
        {
            "generation_mode": "agent",
            "task_kind": "generate",
            "tender_type": "xjcg",
            "prepared_doc_path": "D:/UploadFiles/output.docx",
            "polished_text": "投标人须提供原厂授权函。",
            "polished_comments": [],
            "generated_comment_count": 0,
            "insertion_before_text": "第三章  采购需求",
            "insertion_after_text": "第四章  响应文件有关格式",
        },
        config={
            "configurable": {
                "task_id": "task-2",
                "task_kind": "generate",
                "generation_mode": "agent",
            }
        },
    )

    assert captured["allow_comment_generation"] is True
    assert result["comment_writeback_result"]["generated"] == 1
    assert result["comment_writeback_result"]["added"] == 1


def test_comment_supplement_without_candidates_lets_comment_agent_generate(monkeypatch) -> None:
    captured = {}

    _patch_word_success(monkeypatch)

    def fake_run_comment_agent(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            validation=SimpleNamespace(passed=[object()], failed=[], skipped=[]),
            writeback_result={
                "total": 1,
                "attempted": 1,
                "added": 1,
                "failed": 0,
                "skipped": 0,
                "issues": [],
            },
            audit_log_path=None,
            final_proposed_comments=[
                {
                    "reference_text": "投标人须提供原厂授权函",
                    "comment_text": "建议提示：不得要求原厂授权函。",
                }
            ],
        )

    monkeypatch.setattr(comment_agent_node, "run_comment_agent", fake_run_comment_agent)

    result = comment_agent_writeback(
        {
            "task_kind": "comment_supplement",
            "tender_type": "xjcg",
            "prepared_doc_path": "D:/UploadFiles/output.docx",
            "polished_text": "投标人须提供原厂授权函。",
            "polished_comments": [],
            "generated_comment_count": 0,
            "insertion_before_text": "第三章  采购需求",
            "insertion_after_text": "第四章  响应文件有关格式",
        },
        config={
            "configurable": {
                "task_id": "task-1",
                "task_kind": "comment_supplement",
            }
        },
    )

    assert captured["initial_comments"] == []
    assert captured["allow_comment_generation"] is True
    expected_prompt = render_comment_prompt(
        CommentPromptInput(
            tender_type="xjcg",
            polished_text="投标人须提供原厂授权函。",
        )
    )
    assert (
        captured["comment_generation_instruction"]
        == expected_prompt.system_prompt + "\n\n" + expected_prompt.user_prompt
    )
    assert result["comment_writeback_result"]["generated"] == 1
    assert result["comment_writeback_result"]["added"] == 1


def test_comment_agent_injects_bad_case_context_for_autonomous_generation(
    monkeypatch,
    tmp_path,
) -> None:
    captured = {}
    retrieval_calls: list[str] = []
    retrieval_payload = {
        "source_files": [],
        "load_summary": None,
        "clause_split_summary": {
            "clause_split_mode": "clause_only",
            "clause_count": 1,
            "clauses": [],
        },
        "retrieval_mode": "bm25_only",
        "warnings": [],
        "failure_summary": None,
        "clauses": [],
        "injected_bad_cases": [
            {
                "injection_rank": 1,
                "case_id": "TW_COMMENT_SHOULD_STAY_IN_LOG",
                "score": 0.95,
                "risk_type": "参数指纹",
                "risk_pattern": "精确小数参数可能形成供应商指向性",
                "recommended_comment_policy": "建议提示：改为合理区间。",
                "applicability_boundary": "适用于技术参数过细场景。",
                "anchor_policy": "锚定当前文本中的精确小数参数。",
            }
        ],
    }

    _patch_word_success(monkeypatch)

    def fake_bad_case_context(polished_text: str):
        retrieval_calls.append(polished_text)
        return (
            [
                {
                    "risk_type": "参数指纹",
                    "risk_pattern": "精确小数参数可能形成供应商指向性",
                    "recommended_comment_policy": "建议提示：改为合理区间。",
                    "applicability_boundary": "适用于技术参数过细场景。",
                    "anchor_policy": "锚定当前文本中的精确小数参数。",
                    "case_id": "TW_COMMENT_SHOULD_NOT_APPEAR",
                    "score": 0.99,
                }
            ],
            retrieval_payload,
        )

    def fake_run_comment_agent(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            validation=SimpleNamespace(passed=[object()], failed=[], skipped=[]),
            writeback_result={
                "total": 1,
                "attempted": 1,
                "added": 1,
                "failed": 0,
                "skipped": 0,
                "issues": [],
            },
            audit_log_path=None,
            final_proposed_comments=[
                {
                    "reference_text": "心率检测精度为12.5",
                    "comment_text": "建议提示：改为合理区间。",
                }
            ],
        )

    monkeypatch.setattr(
        comment_agent_node,
        "_build_bad_case_context_for_comment_agent",
        fake_bad_case_context,
    )
    monkeypatch.setattr(comment_agent_node, "run_comment_agent", fake_run_comment_agent)

    result = comment_agent_writeback(
        {
            "generation_mode": "agent",
            "task_kind": "generate",
            "tender_type": "xjcg",
            "task_id": "task-3",
            "project_number": "261127",
            "project_name": "便携式人体成分分析仪",
            "prepared_doc_path": "D:/UploadFiles/output.docx",
            "polished_text": "1、心率检测精度为12.5。",
            "polished_comments": [],
            "generated_comment_count": 0,
            "insertion_before_text": "第三章  采购需求",
            "insertion_after_text": "第四章  响应文件有关格式",
        },
        config={
            "configurable": {
                "task_id": "task-3",
                "task_kind": "generate",
                "generation_mode": "agent",
            }
        },
    )

    assert retrieval_calls == ["1、心率检测精度为12.5。"]
    assert captured["allow_comment_generation"] is True
    instruction = captured["comment_generation_instruction"]
    assert "可能包含【bad_case参考规则】" in instruction
    assert "【bad_case参考规则】" in instruction
    assert "精确小数参数可能形成供应商指向性" in instruction
    assert "TW_COMMENT_SHOULD_NOT_APPEAR" not in instruction
    assert "0.99" not in instruction
    assert result["comment_writeback_result"]["generated"] == 1

    prompt_files = list(tmp_path.glob("*_comment_generation_prompt_*.txt"))
    retrieval_files = list(tmp_path.glob("*_comments_bad_case_retrieval_*.json"))
    assert len(prompt_files) == 1
    assert prompt_files[0].read_text(encoding="utf-8") == instruction
    assert len(retrieval_files) == 1
    saved_payload = json.loads(retrieval_files[0].read_text(encoding="utf-8"))
    assert saved_payload["polished_text"] == "1、心率检测精度为12.5。"
    assert saved_payload["injected_bad_cases"][0]["case_id"] == "TW_COMMENT_SHOULD_STAY_IN_LOG"
    assert "comments_bad_case_retrieval_file" not in result


def test_comment_agent_repair_mode_does_not_retrieve_bad_case(monkeypatch) -> None:
    captured = {}
    retrieval_calls: list[str] = []
    _patch_word_success(monkeypatch)

    monkeypatch.setattr(
        comment_agent_node,
        "_build_bad_case_context_for_comment_agent",
        lambda polished_text: retrieval_calls.append(polished_text),
    )

    def fake_run_comment_agent(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            validation=SimpleNamespace(passed=[object()], failed=[], skipped=[]),
            writeback_result={
                "total": 1,
                "attempted": 1,
                "added": 1,
                "failed": 0,
                "skipped": 0,
                "issues": [],
            },
            audit_log_path=None,
            final_proposed_comments=[
                {
                    "reference_text": "投标人须提供原厂授权函",
                    "comment_text": "建议提示：不得要求原厂授权函。",
                }
            ],
        )

    monkeypatch.setattr(comment_agent_node, "run_comment_agent", fake_run_comment_agent)

    result = comment_agent_writeback(
        {
            "generation_mode": "agent",
            "task_kind": "generate",
            "tender_type": "xjcg",
            "prepared_doc_path": "D:/UploadFiles/output.docx",
            "polished_text": "投标人须提供原厂授权函。",
            "polished_comments": [
                {
                    "reference_text": "投标人须提供原厂授权函",
                    "comment_text": "建议提示：不得要求原厂授权函。",
                }
            ],
            "generated_comment_count": 1,
            "insertion_before_text": "第三章  采购需求",
            "insertion_after_text": "第四章  响应文件有关格式",
        },
        config={
            "configurable": {
                "task_id": "task-4",
                "task_kind": "generate",
                "generation_mode": "agent",
            }
        },
    )

    assert retrieval_calls == []
    assert captured["allow_comment_generation"] is False
    assert captured["comment_generation_instruction"] is None
    assert result["comment_writeback_result"]["generated"] == 1


def test_comment_agent_does_not_retrieve_before_word_context_is_ready(monkeypatch) -> None:
    retrieval_calls: list[str] = []
    monkeypatch.setattr(
        comment_agent_node,
        "_build_bad_case_context_for_comment_agent",
        lambda polished_text: retrieval_calls.append(polished_text),
    )

    result = comment_agent_writeback(
        {
            "generation_mode": "agent",
            "task_kind": "generate",
            "tender_type": "xjcg",
            "polished_text": "投标人须提供原厂授权函。",
            "polished_comments": [],
            "generated_comment_count": 0,
        },
        config={
            "configurable": {
                "task_id": "task-5",
                "task_kind": "generate",
                "generation_mode": "agent",
            }
        },
    )

    assert retrieval_calls == []
    assert "缺少 prepared_doc_path" in result["insertion_log"]
