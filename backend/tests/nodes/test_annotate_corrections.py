from __future__ import annotations

from backend.nodes.common_word_nodes.annotate_corrections import annotate_corrections


def test_annotate_corrections_normalizes_text_and_tables(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.nodes.common_word_nodes.annotate_corrections._run_annotation_llm",
        lambda **kwargs: [],
    )
    state = {
        "polished_text": "△1.1.1.4 管仓设计\n*5.1 原厂保修\n温升 ΔT 正常",
        "tender_params": "△1.1.1.4 管仓设计\n*5.1 原厂保修",
        "tender_param_table_models": [
            {
                "table_id": "TP1",
                "rows": 1,
                "cols": 1,
                "cells": [
                    {
                        "row": 1,
                        "col": 1,
                        "row_span": 1,
                        "col_span": 1,
                        "text": "※验收要求",
                    }
                ],
            }
        ],
    }

    result = annotate_corrections(state, config={"configurable": {"model_provider": "deepseek"}})

    assert result["polished_text"] == "▲1.1.1.4 管仓设计\n★5.1 原厂保修\n温升 ΔT 正常"
    assert result["tender_param_table_models"][0]["cells"][0]["text"] == "★验收要求"
    comments = result["correction_comments"]
    assert len(comments) >= 3
    texts = " ".join(c["comment_text"] for c in comments)
    assert "原技术参数为" in texts
    assert "现改为" in texts
    for c in comments:
        assert c["reference_text"]
        assert "▲" in c["reference_text"] or "★" in c["reference_text"]


def test_annotate_corrections_merges_llm_comments(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.nodes.common_word_nodes.annotate_corrections._run_annotation_llm",
        lambda **kwargs: [
            {
                "reference_text": "分辨率",
                "comment_text": '原技术参数为“分辩率”，现改为“分辨率”',
            }
        ],
    )
    result = annotate_corrections(
        {
            "polished_text": "1、分辨率：4K",
            "tender_params": "1、分辩率：4K",
        },
        config=None,
    )
    assert any("分辩率" in c["comment_text"] for c in result["correction_comments"])


def test_annotate_corrections_skips_llm_when_no_params(monkeypatch) -> None:
    called = {"n": 0}

    def _boom(**kwargs):
        called["n"] += 1
        raise AssertionError("should not call LLM")

    monkeypatch.setattr(
        "backend.nodes.common_word_nodes.annotate_corrections._run_annotation_llm",
        _boom,
    )
    result = annotate_corrections({"polished_text": "△1 条款", "tender_params": ""})
    assert called["n"] == 0
    assert result["polished_text"] == "▲1 条款"
    assert result["correction_comments"]


def test_run_annotation_llm_passes_temperature_via_extra_params(monkeypatch) -> None:
    captured: dict = {}

    async def _fake_stream(**kwargs):
        captured.update(kwargs)
        return "[]"

    monkeypatch.setattr(
        "backend.nodes.common_word_nodes.annotate_corrections.stream_llm_completion",
        _fake_stream,
    )
    from backend.nodes.common_word_nodes.annotate_corrections import _run_annotation_llm

    comments = _run_annotation_llm(
        tender_params="原参数",
        polished_text="现正文",
        model_provider="deepseek",
    )
    assert comments == []
    assert "temperature" not in captured
    assert captured.get("extra_params_override") == {"temperature": 0.1}
