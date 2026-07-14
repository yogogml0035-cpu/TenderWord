from __future__ import annotations

from backend.nodes.common_word_nodes.comment_writeback import (
    apply_correction_and_ai_comments,
    empty_comment_writeback_result,
    merge_comment_writeback_results,
)


def test_merge_comment_writeback_results() -> None:
    a = empty_comment_writeback_result()
    a["total"] = 2
    a["added"] = 2
    b = empty_comment_writeback_result()
    b["total"] = 3
    b["added"] = 1
    b["skipped"] = 2
    merged = merge_comment_writeback_results(a, b)
    assert merged["total"] == 5
    assert merged["added"] == 3
    assert merged["skipped"] == 2


def test_apply_writes_correction_even_when_ai_suppressed(monkeypatch) -> None:
    calls: list[str] = []

    def _fake_write(*, polished_comments, step_label, **kwargs):
        calls.append(step_label)
        result = empty_comment_writeback_result()
        result["total"] = len(list(polished_comments or []))
        result["attempted"] = result["total"]
        result["added"] = result["total"]
        return result

    monkeypatch.setattr(
        "backend.nodes.common_word_nodes.comment_writeback.write_polished_comments",
        _fake_write,
    )
    log_parts: list[str] = []
    merged, summary = apply_correction_and_ai_comments(
        doc=object(),
        state={
            "correction_comments": [
                {"reference_text": "▲1", "comment_text": '原技术参数为“△1”，现改为“▲1”'}
            ],
            "polished_comments": [
                {"reference_text": "售后", "comment_text": "建议明确响应时效"}
            ],
            "generated_comment_count": 1,
        },
        bound_start=0,
        bound_end=100,
        log_parts=log_parts,
        step_label="步骤6",
        suppress_ai_comment_writeback=True,
    )
    assert any("更正批注" in c for c in calls)
    assert not any(c == "步骤6" for c in calls)
    assert merged["added"] == 1
    assert "更正批注成功=1" in summary["summary"]
    assert summary["generated"] == 2  # 1 更正 + 1 普通生成计数


def test_apply_writes_both_when_not_suppressed(monkeypatch) -> None:
    calls: list[str] = []

    def _fake_write(*, polished_comments, step_label, **kwargs):
        calls.append((step_label, len(list(polished_comments or []))))
        result = empty_comment_writeback_result()
        result["total"] = len(list(polished_comments or []))
        result["attempted"] = result["total"]
        result["added"] = result["total"]
        return result

    monkeypatch.setattr(
        "backend.nodes.common_word_nodes.comment_writeback.write_polished_comments",
        _fake_write,
    )
    merged, summary = apply_correction_and_ai_comments(
        doc=object(),
        state={
            "correction_comments": [
                {"reference_text": "▲1", "comment_text": "c1"}
            ],
            "polished_comments": [
                {"reference_text": "a", "comment_text": "c2"},
                {"reference_text": "b", "comment_text": "c3"},
            ],
            "generated_comment_count": 2,
        },
        bound_start=0,
        bound_end=10,
        log_parts=[],
        step_label="步骤7",
        suppress_ai_comment_writeback=False,
    )
    assert len(calls) == 2
    assert calls[0][0].endswith("更正批注")
    assert calls[1][0] == "步骤7"
    assert merged["added"] == 3
    assert summary["generated"] == 3
