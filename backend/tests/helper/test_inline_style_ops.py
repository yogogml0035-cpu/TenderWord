from __future__ import annotations

from typing import Any

from backend.helper.word_helper import inline_style_ops as style_ops
from backend.helper.word_helper.semantic_matcher import normalize_semantic_text


EMPTY_SIGNATURE = {
    "style_flags": {
        "strikethrough": False,
        "underline": False,
        "bold": False,
        "italic": False,
    }
}


class _FakeFont:
    def __init__(self) -> None:
        self.StrikeThrough = False
        self.Bold = False
        self.Italic = False
        self.Underline = 0
        self.Color = None
        self.HighlightColorIndex = None


class _FakeAppliedRange:
    def __init__(self, start: int, end: int) -> None:
        self.Start = int(start)
        self.End = int(end)
        self.Font = _FakeFont()


class _FakeDoc:
    def __init__(self) -> None:
        self.applied_ranges: list[_FakeAppliedRange] = []

    def Range(self, start: int, end: int) -> _FakeAppliedRange:
        applied = _FakeAppliedRange(start, end)
        self.applied_ranges.append(applied)
        return applied


class _FailingDoc(_FakeDoc):
    def Range(self, start: int, end: int) -> _FakeAppliedRange:
        raise RuntimeError("RPC write failed")


def _make_candidate(
    *,
    text: str,
    start: int,
    container_type: str = "paragraph",
    locator: dict[str, int] | None = None,
    position_ratio: float = 0.2,
) -> Any:
    normalized, normalized_map = style_ops._build_normalized_text_with_visible_map(text)
    visible_chars = []
    for index, char in enumerate(text):
        visible_chars.append(
            style_ops._VisibleChar(
                text=char,
                start=start + index,
                end=start + index + 1,
                visible_start=index,
                visible_end=index + 1,
                signature=dict(EMPTY_SIGNATURE),
            )
        )

    return style_ops._ContainerCandidate(
        container_type=container_type,
        container_locator=locator or {"paragraph_index": 1},
        visible_chars=visible_chars,
        visible_text=text,
        normalized_text=normalized,
        normalized_index_to_visible=normalized_map,
        position_ratio=position_ratio,
        range_start=start,
        range_end=start + len(text),
    )


def test_normalize_semantic_text_ignores_numbering_spacing_and_punctuation() -> None:
    assert normalize_semantic_text("1、 服务内容： 测试。") == normalize_semantic_text(
        "2.服务内容 测试"
    )


def test_build_inline_style_fragments_from_text_runs_merges_adjacent_same_signature() -> None:
    bold_signature = {
        "style_flags": {
            "strikethrough": False,
            "underline": False,
            "bold": True,
            "italic": False,
        },
        "font_color": None,
        "highlight_color": None,
        "font_name": None,
        "font_size": None,
        "underline_style": None,
    }

    fragments = style_ops.build_inline_style_fragments_from_text_runs(
        container_type="paragraph",
        container_locator={"paragraph_index": 1},
        container_text="1、重点要求",
        position_ratio=0.1,
        runs=[
            {"text": "1", "start": 0, "end": 1, "signature": bold_signature},
            {"text": "、", "start": 1, "end": 2, "signature": bold_signature},
            {"text": "重", "start": 2, "end": 3, "signature": bold_signature},
            {"text": "点", "start": 3, "end": 4, "signature": bold_signature},
            {"text": "要", "start": 4, "end": 5, "signature": bold_signature},
            {"text": "求", "start": 5, "end": 6, "signature": bold_signature},
        ],
    )

    assert len(fragments) == 1
    assert fragments[0]["source_text"] == "1、重点要求"
    assert fragments[0]["source_span_kind"] == "full_container"
    assert fragments[0]["style_flags"]["bold"] is True


def test_apply_inline_style_fragments_matches_full_container_after_renumbering(monkeypatch) -> None:
    fragment = {
        "container_type": "paragraph",
        "container_locator": {"paragraph_index": 1},
        "source_text": "1、原条款内容",
        "normalized_text": normalize_semantic_text("1、原条款内容"),
        "container_text": "1、原条款内容",
        "normalized_container_text": normalize_semantic_text("1、原条款内容"),
        "context_before": "",
        "context_after": "",
        "position_ratio": 0.15,
        "style_flags": {
            "strikethrough": True,
            "underline": False,
            "bold": False,
            "italic": False,
        },
        "font_color": 255,
        "highlight_color": None,
        "font_name": None,
        "font_size": None,
        "underline_style": None,
        "source_span_kind": "full_container",
    }
    candidate = _make_candidate(text="2、原条款内容", start=100, position_ratio=0.15)
    monkeypatch.setattr(style_ops, "_build_target_containers", lambda *args, **kwargs: [candidate])

    doc = _FakeDoc()
    log_parts: list[str] = []
    result = style_ops.apply_inline_style_fragments(
        doc=doc,
        inline_style_fragments=[fragment],
        bound_start=0,
        bound_end=200,
        log_parts=log_parts,
    )

    assert result["applied"] == 1
    assert len(doc.applied_ranges) == 1
    assert doc.applied_ranges[0].Start == 100
    assert doc.applied_ranges[0].End == 100 + len("2、原条款内容")
    assert doc.applied_ranges[0].Font.StrikeThrough is True
    assert doc.applied_ranges[0].Font.Color == 255


def test_apply_inline_style_fragments_matches_short_title_when_target_paragraph_is_extended(monkeypatch) -> None:
    fragment = {
        "container_type": "paragraph",
        "container_locator": {"paragraph_index": 7},
        "source_text": "二、技术需求",
        "normalized_text": normalize_semantic_text("二、技术需求"),
        "container_text": "二、技术需求",
        "normalized_container_text": normalize_semantic_text("二、技术需求"),
        "context_before": "",
        "context_after": "",
        "position_ratio": 0.78,
        "local_position_ratio": 0.5,
        "style_flags": {
            "strikethrough": False,
            "underline": False,
            "bold": True,
            "italic": False,
        },
        "font_color": None,
        "highlight_color": None,
        "font_name": None,
        "font_size": None,
        "underline_style": None,
        "source_span_kind": "full_container",
    }
    candidates = [
        _make_candidate(
            text="一、项目概述",
            start=10,
            locator={"paragraph_index": 1},
            position_ratio=0.08,
        ),
        _make_candidate(
            text="二、技术需求（一）大功率电场发生装置★1、常规单极模式：",
            start=180,
            locator={"paragraph_index": 8},
            position_ratio=0.79,
        ),
        _make_candidate(
            text="三、其他要求",
            start=260,
            locator={"paragraph_index": 9},
            position_ratio=0.92,
        ),
    ]
    monkeypatch.setattr(style_ops, "_build_target_containers", lambda *args, **kwargs: candidates)

    doc = _FakeDoc()
    result = style_ops.apply_inline_style_fragments(
        doc=doc,
        inline_style_fragments=[fragment],
        bound_start=0,
        bound_end=320,
        log_parts=[],
    )

    assert result["applied"] == 1
    assert doc.applied_ranges[0].Start == 180
    assert doc.applied_ranges[0].End == 180 + len("二、技术需求（一）大功率电场发生装置★1、常规单极模式：")
    assert doc.applied_ranges[0].Font.Bold is True


def test_apply_inline_style_fragments_matches_partial_span_in_unique_candidate(monkeypatch) -> None:
    fragment = {
        "container_type": "paragraph",
        "container_locator": {"paragraph_index": 1},
        "source_text": "红字",
        "normalized_text": normalize_semantic_text("红字"),
        "container_text": "投标人需提供红字证明材料",
        "normalized_container_text": normalize_semantic_text("投标人需提供红字证明材料"),
        "context_before": "提供",
        "context_after": "证明",
        "position_ratio": 0.25,
        "local_position_ratio": 0.52,
        "style_flags": {
            "strikethrough": False,
            "underline": False,
            "bold": True,
            "italic": False,
        },
        "font_color": None,
        "highlight_color": 7,
        "font_name": None,
        "font_size": None,
        "underline_style": None,
        "source_span_kind": "partial_span",
    }
    candidate_text = "投标人应继续提供新增红字证明材料"
    candidate = _make_candidate(text=candidate_text, start=50, position_ratio=0.25)
    monkeypatch.setattr(style_ops, "_build_target_containers", lambda *args, **kwargs: [candidate])

    doc = _FakeDoc()
    result = style_ops.apply_inline_style_fragments(
        doc=doc,
        inline_style_fragments=[fragment],
        bound_start=0,
        bound_end=200,
        log_parts=[],
    )

    expected_start = 50 + candidate_text.index("红")
    assert result["applied"] == 1
    assert doc.applied_ranges[0].Start == expected_start
    assert doc.applied_ranges[0].End == expected_start + len("红字")
    assert doc.applied_ranges[0].Font.Bold is True
    assert doc.applied_ranges[0].Font.HighlightColorIndex == 7


def test_apply_inline_style_fragments_prefers_nearest_position_when_multiple_candidates_are_close(monkeypatch) -> None:
    fragment = {
        "container_type": "paragraph",
        "container_locator": {"paragraph_index": 1},
        "source_text": "原条款内容",
        "normalized_text": normalize_semantic_text("原条款内容"),
        "container_text": "原条款内容",
        "normalized_container_text": normalize_semantic_text("原条款内容"),
        "context_before": "",
        "context_after": "",
        "position_ratio": 0.5,
        "local_position_ratio": 0.5,
        "style_flags": {
            "strikethrough": False,
            "underline": True,
            "bold": False,
            "italic": False,
        },
        "font_color": None,
        "highlight_color": None,
        "font_name": None,
        "font_size": None,
        "underline_style": 1,
        "source_span_kind": "full_container",
    }
    candidates = [
        _make_candidate(text="原条款内容", start=10, locator={"paragraph_index": 1}, position_ratio=0.49),
        _make_candidate(text="原条款内容", start=80, locator={"paragraph_index": 2}, position_ratio=0.82),
    ]
    monkeypatch.setattr(style_ops, "_build_target_containers", lambda *args, **kwargs: candidates)

    doc = _FakeDoc()
    result = style_ops.apply_inline_style_fragments(
        doc=doc,
        inline_style_fragments=[fragment],
        bound_start=0,
        bound_end=200,
        log_parts=[],
    )

    assert result["applied"] == 1
    assert result["skipped"] == 0
    assert doc.applied_ranges[0].Start == 10
    assert doc.applied_ranges[0].Font.Underline == 1


def test_apply_inline_style_fragments_relocates_table_cell_within_same_table(monkeypatch) -> None:
    fragment = {
        "container_type": "table_cell",
        "container_locator": {"table_index": 1, "row": 2, "col": 1},
        "source_text": "★质保期",
        "normalized_text": normalize_semantic_text("★质保期"),
        "container_text": "★质保期",
        "normalized_container_text": normalize_semantic_text("★质保期"),
        "context_before": "",
        "context_after": "",
        "position_ratio": 0.6,
        "local_position_ratio": 0.5,
        "style_flags": {
            "strikethrough": False,
            "underline": False,
            "bold": True,
            "italic": False,
        },
        "font_color": None,
        "highlight_color": None,
        "font_name": None,
        "font_size": None,
        "underline_style": None,
        "source_span_kind": "full_container",
    }
    candidate = _make_candidate(
        text="★质保期",
        start=30,
        container_type="table_cell",
        locator={"table_index": 1, "row": 1, "col": 1},
        position_ratio=0.6,
    )
    monkeypatch.setattr(style_ops, "_build_target_containers", lambda *args, **kwargs: [candidate])

    doc = _FakeDoc()
    result = style_ops.apply_inline_style_fragments(
        doc=doc,
        inline_style_fragments=[fragment],
        bound_start=0,
        bound_end=100,
        log_parts=[],
    )

    assert result["applied"] == 1
    assert result["skipped"] == 0
    assert doc.applied_ranges[0].Start == 30
    assert doc.applied_ranges[0].Font.Bold is True


def test_build_style_writeback_summary_payload_keeps_summary_fields() -> None:
    payload = style_ops.build_style_writeback_summary_payload(
        {
            "extracted": 3,
            "attempted": 3,
            "applied": 2,
            "skipped": 1,
            "failed": 0,
            "issues": [],
            "applied_by_style": {"bold": 2},
            "skipped_by_reason": {"low_confidence": 1},
        },
        "样式回填: 抽取=3, 尝试=3, 成功=2, 跳过=1, 失败=0",
    )

    assert payload == {
        "summary": "样式回填: 抽取=3, 尝试=3, 成功=2, 跳过=1, 失败=0",
        "extracted": 3,
        "attempted": 3,
        "applied": 2,
        "skipped": 1,
        "failed": 0,
        "applied_by_style": {"bold": 2},
        "skipped_by_reason": {"low_confidence": 1},
    }


def test_build_inline_style_extraction_logs_formats_chinese_details() -> None:
    logs = style_ops.build_inline_style_extraction_logs(
        [
            {
                "container_type": "table_cell",
                "container_locator": {"table_index": 2, "row": 3, "col": 1},
                "source_text": "这是一段非常长的样式文本" * 7,
                "style_flags": {
                    "strikethrough": False,
                    "underline": False,
                    "bold": True,
                    "italic": False,
                },
                "highlight_color": 7,
                "source_span_kind": "partial_span",
            }
        ]
    )

    assert len(logs) == 1
    assert "样式提取[1/1]" in logs[0]
    assert "样式=" in logs[0]
    assert "加粗" in logs[0]
    assert "高亮" in logs[0]
    assert "容器=表格#2 第3行第1列" in logs[0]
    assert "范围=局部片段" in logs[0]
    assert "..." in logs[0]


def test_apply_inline_style_fragments_emits_success_detail_logs(monkeypatch) -> None:
    fragment = {
        "container_type": "paragraph",
        "container_locator": {"paragraph_index": 1},
        "source_text": "红字",
        "normalized_text": normalize_semantic_text("红字"),
        "container_text": "投标人需提供红字证明材料",
        "normalized_container_text": normalize_semantic_text("投标人需提供红字证明材料"),
        "context_before": "提供",
        "context_after": "证明",
        "position_ratio": 0.25,
        "local_position_ratio": 0.52,
        "style_flags": {
            "strikethrough": False,
            "underline": False,
            "bold": True,
            "italic": False,
        },
        "font_color": None,
        "highlight_color": 7,
        "font_name": None,
        "font_size": None,
        "underline_style": None,
        "source_span_kind": "partial_span",
    }
    candidate_text = "投标人应继续提供新增红字证明材料"
    candidate = _make_candidate(text=candidate_text, start=50, position_ratio=0.25)
    monkeypatch.setattr(style_ops, "_build_target_containers", lambda *args, **kwargs: [candidate])

    doc = _FakeDoc()
    progress_messages: list[str] = []
    diagnostic_messages: list[str] = []
    result = style_ops.apply_inline_style_fragments(
        doc=doc,
        inline_style_fragments=[fragment],
        bound_start=0,
        bound_end=200,
        log_parts=[],
        progress_logger=progress_messages.append,
        diagnostic_logger=diagnostic_messages.append,
    )

    assert result["applied"] == 1
    assert any("开始回填行内样式，共 1 个片段" in message for message in progress_messages)
    assert any(
        "样式回填成功[1/1] 加粗、高亮" in message
        and '"红字" -> "红字"' in message
        and "候选=" not in message
        and "得分=" not in message
        for message in progress_messages
    )
    assert any("命中样式: 加粗=1, 高亮=1" in message for message in progress_messages)
    assert any('样式回填命中 | 加粗、高亮 "红字" -> "红字"' in message for message in progress_messages)
    assert any(
        "样式回填诊断[1/1] 成功" in message
        and "得分=" in message
        and "候选=" in message
        for message in diagnostic_messages
    )


def test_apply_inline_style_fragments_copies_font_color_for_partial_span(monkeypatch) -> None:
    fragment = {
        "container_type": "paragraph",
        "container_locator": {"paragraph_index": 2},
        "source_text": "提供",
        "normalized_text": normalize_semantic_text("提供"),
        "container_text": "供应商需提供原件",
        "normalized_container_text": normalize_semantic_text("供应商需提供原件"),
        "context_before": "需",
        "context_after": "原件",
        "position_ratio": 0.35,
        "local_position_ratio": 0.5,
        "style_flags": {
            "strikethrough": False,
            "underline": False,
            "bold": False,
            "italic": False,
        },
        "font_color": 255,
        "highlight_color": None,
        "font_name": None,
        "font_size": None,
        "underline_style": None,
        "source_span_kind": "partial_span",
    }
    candidate_text = "供应商应按要求提供纸质原件"
    candidate = _make_candidate(text=candidate_text, start=40, position_ratio=0.34)
    monkeypatch.setattr(style_ops, "_build_target_containers", lambda *args, **kwargs: [candidate])

    doc = _FakeDoc()
    result = style_ops.apply_inline_style_fragments(
        doc=doc,
        inline_style_fragments=[fragment],
        bound_start=0,
        bound_end=120,
        log_parts=[],
    )

    assert result["applied"] == 1
    assert doc.applied_ranges[0].Font.Color == 255
    assert doc.applied_ranges[0].Start == 40 + candidate_text.index("提")


def test_apply_inline_style_fragments_emits_short_skip_logs_and_keeps_diagnostics(monkeypatch) -> None:
    fragment = {
        "container_type": "paragraph",
        "container_locator": {"paragraph_index": 7},
        "source_text": "二、技术需求",
        "normalized_text": normalize_semantic_text("二、技术需求"),
        "container_text": "二、技术需求",
        "normalized_container_text": normalize_semantic_text("二、技术需求"),
        "context_before": "",
        "context_after": "",
        "position_ratio": 0.78,
        "local_position_ratio": 0.5,
        "style_flags": {
            "strikethrough": False,
            "underline": False,
            "bold": True,
            "italic": False,
        },
        "font_color": None,
        "highlight_color": None,
        "font_name": None,
        "font_size": None,
        "underline_style": None,
        "source_span_kind": "full_container",
    }
    candidates = [
        _make_candidate(
            text="一、项目概述",
            start=10,
            locator={"paragraph_index": 1},
            position_ratio=0.08,
        ),
        _make_candidate(
            text="付款方式：分期付款，合同签订后支付预付款。",
            start=60,
            locator={"paragraph_index": 4},
            position_ratio=0.34,
        ),
    ]
    monkeypatch.setattr(style_ops, "_build_target_containers", lambda *args, **kwargs: candidates)

    progress_messages: list[str] = []
    diagnostic_messages: list[str] = []
    result = style_ops.apply_inline_style_fragments(
        doc=_FakeDoc(),
        inline_style_fragments=[fragment],
        bound_start=0,
        bound_end=100,
        log_parts=[],
        progress_logger=progress_messages.append,
        diagnostic_logger=diagnostic_messages.append,
    )

    assert result["skipped"] == 1
    assert any(
        "样式回填跳过[1/1] 加粗" in message
        and '"二、技术需求"' in message
        and "原因：未找到可承接标题样式的目标段落" in message
        and "候选=" not in message
        and "段落#1" not in message
        for message in progress_messages
    )
    assert any(
        "样式回填诊断[1/1] 跳过" in message
        and "候选=" in message
        and "段落#1" in message
        for message in diagnostic_messages
    )


def test_apply_inline_style_fragments_emits_failure_logs(monkeypatch) -> None:
    fragment = {
        "container_type": "paragraph",
        "container_locator": {"paragraph_index": 1},
        "source_text": "红字",
        "normalized_text": normalize_semantic_text("红字"),
        "container_text": "红字",
        "normalized_container_text": normalize_semantic_text("红字"),
        "context_before": "",
        "context_after": "",
        "position_ratio": 0.2,
        "style_flags": {
            "strikethrough": False,
            "underline": False,
            "bold": True,
            "italic": False,
        },
        "font_color": None,
        "highlight_color": None,
        "font_name": None,
        "font_size": None,
        "underline_style": None,
        "source_span_kind": "full_container",
    }
    candidate = _make_candidate(text="红字", start=10, position_ratio=0.2)
    monkeypatch.setattr(style_ops, "_build_target_containers", lambda *args, **kwargs: [candidate])

    progress_messages: list[str] = []
    diagnostic_messages: list[str] = []
    result = style_ops.apply_inline_style_fragments(
        doc=_FailingDoc(),
        inline_style_fragments=[fragment],
        bound_start=0,
        bound_end=100,
        log_parts=[],
        progress_logger=progress_messages.append,
        diagnostic_logger=diagnostic_messages.append,
    )

    assert result["failed"] == 1
    assert any(
        "样式回填失败[1/1] 加粗" in message
        and '"红字"' in message
        and "错误：RPC write failed" in message
        and "候选=" not in message
        for message in progress_messages
    )
    assert any(
        "样式回填诊断[1/1] 失败" in message
        and "原因=写回样式失败" in message
        and "错误=RPC write failed" in message
        for message in diagnostic_messages
    )
