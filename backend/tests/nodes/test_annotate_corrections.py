from __future__ import annotations

from backend.nodes.common_word_nodes.annotate_corrections import (
    _CORRECTION_SYSTEM,
    _build_user_prompt,
    _parse_correction_comments,
    annotate_corrections,
)


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


def test_correction_prompt_marks_all_parameter_text_changes() -> None:
    assert "建立事实账本" in _CORRECTION_SYSTEM
    assert "增字、减字、替换或拼接" in _CORRECTION_SYSTEM
    assert "项目名称`描述整个项目" in _CORRECTION_SYSTEM
    assert "`维保设备`可对齐设备清单的`设备名称`" in _CORRECTION_SYSTEM
    assert "`数量：1套`可对齐`数量=1`与`单位=套`" in _CORRECTION_SYSTEM
    assert "无标签文本" in _CORRECTION_SYSTEM
    assert "不得靠猜测拆分并覆盖原始技术参数" in _CORRECTION_SYSTEM
    assert "原技术参数为“aaa”，现改为“bbb”" in _CORRECTION_SYSTEM
    assert "磁共振系统" in _CORRECTION_SYSTEM
    assert "医用核磁共振系统" in _CORRECTION_SYSTEM
    assert "服务期限：3年" in _CORRECTION_SYSTEM
    assert "服务期限：三年" in _CORRECTION_SYSTEM
    assert "编号隔离硬规则" in _CORRECTION_SYSTEM
    assert "通道反转分析" in _CORRECTION_SYSTEM

    prompt = _build_user_prompt(
        tender_params="维保设备：磁共振系统",
        polished_text="设备名称：医用核磁共振系统",
        marker_already_applied=True,
    )
    assert "先按包、对象、来源字段标签和目标语义槽位拆分" in prompt
    assert "只标注事实值字符变化，不标注纯结构变化" in prompt
    assert "通道反转分析" in prompt
    assert "只授权项目名称槽位" in prompt


def test_correction_parser_enforces_sources_anchor_and_fixed_wording() -> None:
    raw = """[
      {"reference_text":"医用核磁共振系统","comment_text":"原技术参数为“磁共振系统”，现改为“医用核磁共振系统”"},
      {"reference_text":"不存在的锚点","comment_text":"原技术参数为“磁共振系统”，现改为“其它系统”"},
      {"reference_text":"医用核磁共振系统","comment_text":"建议确认是否修改设备名称"},
      {"reference_text":"医用核磁共振系统","comment_text":"原技术参数为“模板旧设备”，现改为“医用核磁共振系统”"}
    ]"""

    comments = _parse_correction_comments(
        raw,
        tender_params="维保设备：磁共振系统",
        polished_text="设备名称：医用核磁共振系统",
    )

    assert comments == [
        {
            "reference_text": "医用核磁共振系统",
            "comment_text": "原技术参数为“磁共振系统”，现改为“医用核磁共振系统”",
        }
    ]


def test_correction_parser_drops_number_only_changes() -> None:
    raw = """[
      {"reference_text":"4、通道反转分析","comment_text":"原技术参数为“通道反转分析”，现改为“4、通道反转分析”"},
      {"reference_text":"2、★独立婴幼儿分析模式","comment_text":"原技术参数为“*独立婴幼儿分析模式”，现改为“2、★独立婴幼儿分析模式”"},
      {"reference_text":"5、通道反转分析，支持自动记录","comment_text":"原技术参数为“通道反转分析”，现改为“5、通道反转分析，支持自动记录”"}
    ]"""

    comments = _parse_correction_comments(
        raw,
        tender_params="通道反转分析\n*独立婴幼儿分析模式",
        polished_text="4、通道反转分析\n2、★独立婴幼儿分析模式\n5、通道反转分析，支持自动记录",
    )

    assert comments == [
        {
            "reference_text": "5、通道反转分析，支持自动记录",
            "comment_text": "原技术参数为“通道反转分析”，现改为“5、通道反转分析，支持自动记录”",
        }
    ]


def test_annotate_corrections_passes_project_sources_to_diff_prompt(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def _capture(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(
        "backend.nodes.common_word_nodes.annotate_corrections._run_annotation_llm",
        _capture,
    )
    annotate_corrections(
        {
            "polished_text": "设备名称：医用核磁共振系统",
            "tender_params": "维保设备：磁共振系统",
            "project_name": "医用核磁共振系统维保",
            "project_content": "医用核磁共振系统维保\t叁年",
        }
    )

    assert captured["project_name"] == "医用核磁共振系统维保"
    assert captured["project_info"] == "医用核磁共振系统维保\t叁年"
