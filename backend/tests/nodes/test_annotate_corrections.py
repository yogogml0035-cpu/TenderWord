from __future__ import annotations

from backend.nodes.common_word_nodes.annotate_corrections import (
    _CORRECTION_REVIEW_SYSTEM,
    _CORRECTION_SYSTEM,
    _build_user_prompt,
    _parse_correction_comments,
    annotate_corrections,
)


def test_annotate_corrections_normalizes_text_and_tables(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.nodes.common_word_nodes.annotate_corrections._write_correction_log_artifact",
        lambda **_kwargs: None,
    )
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
        "backend.nodes.common_word_nodes.annotate_corrections._write_correction_log_artifact",
        lambda **_kwargs: None,
    )
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
    monkeypatch.setattr(
        "backend.nodes.common_word_nodes.annotate_corrections._write_correction_log_artifact",
        lambda **_kwargs: None,
    )
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


def test_run_annotation_llm_passes_temperature_via_extra_params(monkeypatch, tmp_path) -> None:
    captured: dict = {}

    async def _fake_stream(**kwargs):
        captured.update(kwargs)
        return "[]"

    monkeypatch.setattr(
        "backend.nodes.common_word_nodes.annotate_corrections.stream_llm_completion",
        _fake_stream,
    )
    monkeypatch.setattr(
        "backend.nodes.common_word_nodes.annotate_corrections.get_generate_context_log_dir",
        lambda _anchor: tmp_path,
    )
    from backend.nodes.common_word_nodes.annotate_corrections import _run_annotation_llm

    comments = _run_annotation_llm(
        tender_params="原参数",
        polished_text="现正文",
        model_provider="deepseek",
        task_id="task-annotation-log",
    )
    assert comments == []
    assert "temperature" not in captured
    assert captured.get("extra_params_override") == {"temperature": 0.1}
    artifacts = {path.name: path.read_text(encoding="utf-8") for path in tmp_path.glob("*.txt")}
    assert any("prompt" in name and "原参数" in content for name, content in artifacts.items())
    assert any("raw_output" in name and content == "[]" for name, content in artifacts.items())


def test_correction_prompts_use_a_clear_fact_value_gate() -> None:
    assert "输入同时提供【原始技术参数】与【最终正文】" in _CORRECTION_SYSTEM
    assert "不要因为两个字符串不同就直接输出批注" in _CORRECTION_SYSTEM
    assert "原技术参数为“aaa”，现改为“bbb”" in _CORRECTION_SYSTEM
    assert "-1、2、3 通道或向量导联记录" in _CORRECTION_SYSTEM
    assert "-2GB 内存" in _CORRECTION_SYSTEM
    assert "1动态心电血压测试仪1套" in _CORRECTION_SYSTEM
    assert "重要性标识" in _CORRECTION_SYSTEM
    assert "必须生成更正批注" in _CORRECTION_SYSTEM
    assert "更正批注的最终审核器" in _CORRECTION_REVIEW_SYSTEM
    assert "不确定时不要保留" in _CORRECTION_REVIEW_SYSTEM

    prompt = _build_user_prompt(
        tender_params="维保设备：磁共振系统",
        polished_text="设备名称：医用核磁共振系统",
        marker_already_applied=True,
    )
    assert "先排除展示壳变化" in prompt
    assert "不要因为两个字符串不同就直接输出批注" in prompt
    assert "只授权项目名称槽位" in prompt
    assert "必须生成该标识更正批注" in prompt

    duplicate_prompt = _build_user_prompt(
        tender_params="* 医用跑台",
        polished_text="★ 医用跑台",
        marker_already_applied=True,
        marker_correction_comments=[
            {
                "reference_text": "★ 医用跑台",
                "comment_text": "原技术参数为“* 医用跑台”，现改为“★ 医用跑台”",
            }
        ],
    )
    assert "不要重复输出这些同一位置的批注" in duplicate_prompt


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


def test_correction_review_drops_display_only_candidates(monkeypatch, tmp_path) -> None:
    responses = iter(
        [
            """[
              {"reference_text":"动态心电血压仪（1套）","comment_text":"原技术参数为“.动态心电血压仪（1套）”，现改为“动态心电血压仪（1套）”"},
              {"reference_text":"9.2、1、2、3 通道或向量导联记录","comment_text":"原技术参数为“-1、2、3 通道或向量导联记录”，现改为“9.2、1、2、3 通道或向量导联记录”"},
              {"reference_text":"10.2、2GB 内存","comment_text":"原技术参数为“-2GB 内存”，现改为“10.2、2GB 内存”"},
              {"reference_text":"1、★运动心电记录仪 CFDA 注册证","comment_text":"原技术参数为“1. * 运动心电记录仪 CFDA 注册证”，现改为“1、★运动心电记录仪 CFDA 注册证”"},
              {"reference_text":"1、动态心电血压记录仪 14个","comment_text":"原技术参数为“1 动态心电血压记录仪 13个”，现改为“1、动态心电血压记录仪 14个”"}
            ]""",
            "[4, 5]",
        ]
    )

    async def _fake_stream(**_kwargs):
        return next(responses)

    monkeypatch.setattr(
        "backend.nodes.common_word_nodes.annotate_corrections.stream_llm_completion",
        _fake_stream,
    )
    monkeypatch.setattr(
        "backend.nodes.common_word_nodes.annotate_corrections.get_generate_context_log_dir",
        lambda _anchor: tmp_path,
    )
    from backend.nodes.common_word_nodes.annotate_corrections import _run_annotation_llm

    comments = _run_annotation_llm(
        tender_params=".动态心电血压仪（1套）\n-1、2、3 通道或向量导联记录\n-2GB 内存\n1. * 运动心电记录仪 CFDA 注册证\n1 动态心电血压记录仪 13个",
        polished_text="动态心电血压仪（1套）\n9.2、1、2、3 通道或向量导联记录\n10.2、2GB 内存\n1、★运动心电记录仪 CFDA 注册证\n1、动态心电血压记录仪 14个",
        model_provider="deepseek",
        task_id="task-correction-review",
    )

    assert comments == [
        {
            "reference_text": "1、★运动心电记录仪 CFDA 注册证",
            "comment_text": "原技术参数为“1. * 运动心电记录仪 CFDA 注册证”，现改为“1、★运动心电记录仪 CFDA 注册证”",
        },
        {
            "reference_text": "1、动态心电血压记录仪 14个",
            "comment_text": "原技术参数为“1 动态心电血压记录仪 13个”，现改为“1、动态心电血压记录仪 14个”",
        }
    ]
    assert next(tmp_path.glob("*review_prompt.txt"))
    assert next(tmp_path.glob("*review_raw_output.txt")).read_text(encoding="utf-8") == "[4, 5]"


def test_annotate_corrections_logs_accepted_comments(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "backend.nodes.common_word_nodes.annotate_corrections.get_generate_context_log_dir",
        lambda _anchor: tmp_path,
    )
    monkeypatch.setattr(
        "backend.nodes.common_word_nodes.annotate_corrections._run_annotation_llm",
        lambda **_kwargs: [
            {
                "reference_text": "医用核磁共振系统",
                "comment_text": "原技术参数为“磁共振系统”，现改为“医用核磁共振系统”",
            }
        ],
    )

    annotate_corrections(
        {
            "task_id": "task-annotation-log",
            "polished_text": "设备名称：医用核磁共振系统",
            "tender_params": "维保设备：磁共振系统",
        }
    )

    accepted = next(tmp_path.glob("*accepted_comments.txt"))
    assert "磁共振系统" in accepted.read_text(encoding="utf-8")


def test_annotate_corrections_passes_project_sources_to_diff_prompt(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.nodes.common_word_nodes.annotate_corrections._write_correction_log_artifact",
        lambda **_kwargs: None,
    )
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
