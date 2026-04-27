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


class _FakeListLevel:
    def __init__(self, font: _FakeFont) -> None:
        self.Font = font


class _FakeListLevels:
    def __init__(self, level: _FakeListLevel) -> None:
        self.level = level

    def __call__(self, index: int) -> _FakeListLevel:
        del index
        return self.level

    def Item(self, index: int) -> _FakeListLevel:
        del index
        return self.level


class _FakeListTemplate:
    def __init__(self, font: _FakeFont) -> None:
        self.ListLevels = _FakeListLevels(_FakeListLevel(font))


class _FakeListFormat:
    def __init__(self, *, list_string: str, font: _FakeFont) -> None:
        self.ListType = 3
        self.ListString = list_string
        self.ListLevelNumber = 2
        self.ListTemplate = _FakeListTemplate(font)


class _FakeParagraphRange:
    def __init__(self, list_format: _FakeListFormat) -> None:
        self.ListFormat = list_format


class _FakeListRange(_FakeAppliedRange):
    def __init__(self, start: int, end: int, list_format: _FakeListFormat) -> None:
        super().__init__(start, end)
        self.ListFormat = list_format


class _FakeListLabelDoc:
    def __init__(self, list_format: _FakeListFormat) -> None:
        self.list_format = list_format
        self.ranges: list[_FakeListRange] = []

    def Range(self, start: int, end: int) -> _FakeListRange:
        resolved = _FakeListRange(start, end, self.list_format)
        self.ranges.append(resolved)
        return resolved


def _make_candidate(
    *,
    text: str,
    start: int,
    container_type: str = "paragraph",
    locator: dict[str, int] | None = None,
    position_ratio: float = 0.2,
    logical_bound_start: int | None = None,
    logical_bound_end: int | None = None,
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
    logical_lines = style_ops._build_logical_lines(
        visible_chars,
        bound_start=start if logical_bound_start is None else int(logical_bound_start),
        bound_end=(
            start + max(len(text), 1) + 1
            if logical_bound_end is None
            else int(logical_bound_end)
        ),
    )

    return style_ops._ContainerCandidate(
        container_type=container_type,
        container_locator=locator or {"paragraph_index": 1},
        visible_chars=visible_chars,
        visible_text=text,
        normalized_text=normalized,
        normalized_index_to_visible=normalized_map,
        logical_lines=logical_lines,
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


def test_build_inline_style_fragments_preserves_styled_number_prefix_only_run() -> None:
    red_signature = {
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
    }

    fragments = style_ops.build_inline_style_fragments_from_text_runs(
        container_type="paragraph",
        container_locator={"paragraph_index": 1},
        container_text="16.1、配置专用外置连接电阻网络盒",
        position_ratio=0.1,
        runs=[
            {"text": "1", "start": 0, "end": 1, "signature": red_signature},
            {"text": "6", "start": 1, "end": 2, "signature": red_signature},
            {"text": ".", "start": 2, "end": 3, "signature": red_signature},
            {"text": "1", "start": 3, "end": 4, "signature": red_signature},
            {"text": "、", "start": 4, "end": 5, "signature": red_signature},
        ],
    )

    assert len(fragments) == 1
    assert fragments[0]["source_span_kind"] == "number_prefix"
    assert fragments[0]["source_text"] == "16.1、"
    assert fragments[0]["number_prefix_text"] == "16.1、"
    assert fragments[0]["normalized_text"] == normalize_semantic_text("配置专用外置连接电阻网络盒")
    assert fragments[0]["font_color"] == 255


def test_build_number_prefix_fragment_from_word_list_level_font() -> None:
    list_font = _FakeFont()
    list_font.Color = 255
    candidate = _make_candidate(
        text="配置专用外置连接电阻网络盒",
        start=20,
        locator={"paragraph_index": 9},
        position_ratio=0.3,
    )

    fragment = style_ops._build_number_prefix_fragment_from_paragraph_list(
        container_locator={"paragraph_index": 9},
        paragraph_range=_FakeParagraphRange(
            _FakeListFormat(list_string="16.1、", font=list_font)
        ),
        candidate=candidate,
    )

    assert fragment is not None
    assert fragment["source_span_kind"] == "number_prefix"
    assert fragment["source_text"] == "16.1、"
    assert fragment["font_color"] == 255
    assert fragment["normalized_text"] == normalize_semantic_text("配置专用外置连接电阻网络盒")


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


def test_apply_inline_style_fragments_copies_font_color_to_renumbered_prefix(monkeypatch) -> None:
    fragment = {
        "container_type": "paragraph",
        "container_locator": {"paragraph_index": 3},
        "source_text": "16.1、",
        "number_prefix_text": "16.1、",
        "normalized_text": normalize_semantic_text("配置专用外置连接电阻网络盒"),
        "container_text": "16.1、配置专用外置连接电阻网络盒",
        "normalized_container_text": normalize_semantic_text("16.1、配置专用外置连接电阻网络盒"),
        "context_before": "",
        "context_after": "配置专用外置连接电阻网络盒",
        "position_ratio": 0.25,
        "local_position_ratio": 0.05,
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
        "source_span_kind": "number_prefix",
    }
    candidate_text = "16.2、配置专用外置连接电阻网络盒"
    candidate = _make_candidate(text=candidate_text, start=100, position_ratio=0.25)
    monkeypatch.setattr(style_ops, "_build_target_containers", lambda *args, **kwargs: [candidate])

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
    assert doc.applied_ranges[0].Start == 100
    assert doc.applied_ranges[0].End == 100 + len("16.2、")
    assert doc.applied_ranges[0].Font.Color == 255


def test_apply_inline_style_fragments_skips_high_visible_number_prefix(monkeypatch) -> None:
    fragment = {
        "container_type": "paragraph",
        "container_locator": {"paragraph_index": 3},
        "source_text": "五、",
        "number_prefix_text": "五、",
        "normalized_text": normalize_semantic_text("售后服务"),
        "container_text": "五、售后服务",
        "normalized_container_text": normalize_semantic_text("五、售后服务"),
        "context_before": "",
        "context_after": "售后服务",
        "position_ratio": 0.62,
        "local_position_ratio": 0.05,
        "style_flags": {
            "strikethrough": True,
            "underline": False,
            "bold": False,
            "italic": True,
        },
        "font_color": None,
        "highlight_color": None,
        "font_name": None,
        "font_size": None,
        "underline_style": None,
        "source_span_kind": "number_prefix",
    }
    candidate = _make_candidate(
        text="五、售后服务",
        start=120,
        position_ratio=0.62,
    )
    monkeypatch.setattr(style_ops, "_build_target_containers", lambda *args, **kwargs: [candidate])

    doc = _FakeDoc()
    result = style_ops.apply_inline_style_fragments(
        doc=doc,
        inline_style_fragments=[fragment],
        bound_start=0,
        bound_end=200,
        log_parts=[],
    )

    assert result["applied"] == 0
    assert result["skipped"] == 1
    assert doc.applied_ranges == []
    assert result["issues"][0]["reason"] == "number_prefix_high_visible_style"


def test_apply_inline_style_fragments_skips_number_prefix_when_target_has_no_prefix(monkeypatch) -> None:
    fragment = {
        "container_type": "paragraph",
        "container_locator": {"paragraph_index": 3},
        "source_text": "16.1、",
        "number_prefix_text": "16.1、",
        "normalized_text": normalize_semantic_text("配置专用外置连接电阻网络盒"),
        "container_text": "16.1、配置专用外置连接电阻网络盒",
        "normalized_container_text": normalize_semantic_text("16.1、配置专用外置连接电阻网络盒"),
        "context_before": "",
        "context_after": "配置专用外置连接电阻网络盒",
        "position_ratio": 0.25,
        "local_position_ratio": 0.05,
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
        "source_span_kind": "number_prefix",
    }
    candidate = _make_candidate(
        text="配置专用外置连接电阻网络盒",
        start=100,
        position_ratio=0.25,
    )
    monkeypatch.setattr(style_ops, "_build_target_containers", lambda *args, **kwargs: [candidate])

    result = style_ops.apply_inline_style_fragments(
        doc=_FakeDoc(),
        inline_style_fragments=[fragment],
        bound_start=0,
        bound_end=200,
        log_parts=[],
    )

    assert result["applied"] == 0
    assert result["skipped"] == 1
    assert result["issues"][0]["reason"] == "no_number_prefix_target"


def test_apply_inline_style_fragments_copies_font_color_to_word_list_label(monkeypatch) -> None:
    fragment = {
        "container_type": "paragraph",
        "container_locator": {"paragraph_index": 3},
        "source_text": "16.1、",
        "number_prefix_text": "16.1、",
        "normalized_text": normalize_semantic_text("配置专用外置连接电阻网络盒"),
        "container_text": "16.1、配置专用外置连接电阻网络盒",
        "normalized_container_text": normalize_semantic_text("16.1、配置专用外置连接电阻网络盒"),
        "context_before": "",
        "context_after": "配置专用外置连接电阻网络盒",
        "position_ratio": 0.25,
        "local_position_ratio": 0.05,
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
        "source_span_kind": "number_prefix",
    }
    candidate = _make_candidate(
        text="配置专用外置连接电阻网络盒",
        start=100,
        position_ratio=0.25,
    )
    monkeypatch.setattr(style_ops, "_build_target_containers", lambda *args, **kwargs: [candidate])

    list_font = _FakeFont()
    list_font.Color = 0
    doc = _FakeListLabelDoc(_FakeListFormat(list_string="16.2、", font=list_font))
    result = style_ops.apply_inline_style_fragments(
        doc=doc,
        inline_style_fragments=[fragment],
        bound_start=0,
        bound_end=200,
        log_parts=[],
    )

    assert result["applied"] == 1
    assert result["skipped"] == 0
    assert list_font.Color == 255
    assert doc.ranges[-1].Start == 100
    assert doc.ranges[-1].End == 100 + len("配置专用外置连接电阻网络盒")


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
            logical_bound_start=0,
            logical_bound_end=320,
        ),
        _make_candidate(
            text="4、付款方式：分期付款\n二、技术需求\n（一）大功率电场发生装置",
            start=180,
            locator={"paragraph_index": 8},
            position_ratio=0.79,
            logical_bound_start=0,
            logical_bound_end=320,
        ),
        _make_candidate(
            text="三、其他要求",
            start=260,
            locator={"paragraph_index": 9},
            position_ratio=0.92,
            logical_bound_start=0,
            logical_bound_end=320,
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
    candidate_text = "4、付款方式：分期付款\n二、技术需求\n（一）大功率电场发生装置"
    expected_start = 180 + candidate_text.index("二")
    assert doc.applied_ranges[0].Start == expected_start
    assert doc.applied_ranges[0].End == expected_start + len("二、技术需求")
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


def test_apply_inline_style_fragments_keeps_table_same_cell_short_exact_match(monkeypatch) -> None:
    fragment = {
        "container_type": "table_cell",
        "container_locator": {"table_index": 1, "row": 2, "col": 1},
        "source_text": "质",
        "normalized_text": normalize_semantic_text("质"),
        "container_text": "质保期",
        "normalized_container_text": normalize_semantic_text("质保期"),
        "context_before": "",
        "context_after": "保期",
        "position_ratio": 0.6,
        "local_position_ratio": 0.1,
        "style_flags": {
            "strikethrough": False,
            "underline": False,
            "bold": False,
            "italic": True,
        },
        "font_color": None,
        "highlight_color": None,
        "font_name": None,
        "font_size": None,
        "underline_style": None,
        "source_span_kind": "partial_span",
    }
    candidate = _make_candidate(
        text="质保期",
        start=70,
        container_type="table_cell",
        locator={"table_index": 1, "row": 2, "col": 1},
        position_ratio=0.6,
    )
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
    assert result["skipped"] == 0
    assert doc.applied_ranges[0].Start == 70
    assert doc.applied_ranges[0].End == 71
    assert doc.applied_ranges[0].Font.Italic is True


def test_apply_inline_style_fragments_skips_table_cross_cell_short_without_structure(monkeypatch) -> None:
    fragment = {
        "container_type": "table_cell",
        "container_locator": {"table_index": 1, "row": 2, "col": 1},
        "source_text": "质",
        "normalized_text": normalize_semantic_text("质"),
        "container_text": "质保期",
        "normalized_container_text": normalize_semantic_text("质保期"),
        "context_before": "",
        "context_after": "",
        "position_ratio": 0.6,
        "local_position_ratio": 0.1,
        "style_flags": {
            "strikethrough": True,
            "underline": False,
            "bold": False,
            "italic": True,
        },
        "font_color": None,
        "highlight_color": None,
        "font_name": None,
        "font_size": None,
        "underline_style": None,
        "source_span_kind": "partial_span",
    }
    candidate = _make_candidate(
        text="质保期",
        start=90,
        container_type="table_cell",
        locator={"table_index": 1, "row": 8, "col": 4},
        position_ratio=0.6,
    )
    monkeypatch.setattr(style_ops, "_build_target_containers", lambda *args, **kwargs: [candidate])

    doc = _FakeDoc()
    result = style_ops.apply_inline_style_fragments(
        doc=doc,
        inline_style_fragments=[fragment],
        bound_start=0,
        bound_end=140,
        log_parts=[],
    )

    assert result["applied"] == 0
    assert result["skipped"] == 1
    assert doc.applied_ranges == []
    assert result["issues"][0]["reason"] == "short_fragment_semantic_mismatch"


def test_short_partial_gate_rejects_table_number_prefix_exact_match() -> None:
    fragment = {
        "container_type": "table_cell",
        "container_locator": {"table_index": 1, "row": 3, "col": 1},
        "source_text": "五",
        "normalized_text": normalize_semantic_text("五"),
        "container_text": "设备五套",
        "normalized_container_text": normalize_semantic_text("设备五套"),
        "context_before": "设备",
        "context_after": "套",
        "position_ratio": 0.5,
        "local_position_ratio": 0.5,
        "style_flags": {
            "strikethrough": True,
            "underline": False,
            "bold": False,
            "italic": True,
        },
        "font_color": None,
        "highlight_color": None,
        "font_name": None,
        "font_size": None,
        "underline_style": None,
        "source_span_kind": "partial_span",
    }
    candidate = _make_candidate(
        text="五、售后服务",
        start=120,
        container_type="table_cell",
        locator={"table_index": 1, "row": 3, "col": 1},
        position_ratio=0.5,
    )
    match = style_ops._LocalMatch(
        visible_start=0,
        visible_end=1,
        actual_start=120,
        actual_end=121,
        score=1.0,
        context_score=1.0,
        local_position_score=1.0,
        text_score=1.0,
        is_exact=True,
    )
    probe = style_ops._CandidateProbe(
        candidate=candidate,
        container_score=1.0,
        local_hint_score=1.0,
        position_score=1.0,
        structure_score=1.0,
    )

    assert (
        style_ops._short_partial_match_gate_reason(fragment, probe, match)
        == "short_fragment_prefix_conflict"
    )


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


def test_apply_inline_style_fragments_matches_short_partial_inside_logical_line(monkeypatch) -> None:
    fragment = {
        "container_type": "paragraph",
        "container_locator": {"paragraph_index": 62},
        "source_text": "提供",
        "normalized_text": normalize_semantic_text("提供"),
        "container_text": "供应商需提供原件",
        "normalized_container_text": normalize_semantic_text("供应商需提供原件"),
        "context_before": "需",
        "context_after": "原件",
        "position_ratio": 0.76,
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
    candidate_text = "4、付款方式：按节点支付\n供应商需提供原件\n三、其他要求"
    candidate = _make_candidate(text=candidate_text, start=120, position_ratio=0.74)
    monkeypatch.setattr(style_ops, "_build_target_containers", lambda *args, **kwargs: [candidate])

    doc = _FakeDoc()
    result = style_ops.apply_inline_style_fragments(
        doc=doc,
        inline_style_fragments=[fragment],
        bound_start=0,
        bound_end=260,
        log_parts=[],
    )

    expected_start = 120 + candidate_text.index("提")
    assert result["applied"] == 1
    assert doc.applied_ranges[0].Start == expected_start
    assert doc.applied_ranges[0].End == expected_start + len("提供")
    assert doc.applied_ranges[0].Font.Color == 255


def test_short_partial_gate_rejects_paragraph_number_prefix_exact_match() -> None:
    fragment = {
        "container_type": "paragraph",
        "container_locator": {"paragraph_index": 4},
        "source_text": "五",
        "normalized_text": normalize_semantic_text("五"),
        "container_text": "设备五套",
        "normalized_container_text": normalize_semantic_text("设备五套"),
        "context_before": "设备",
        "context_after": "套",
        "position_ratio": 0.5,
        "local_position_ratio": 0.5,
        "style_flags": {
            "strikethrough": True,
            "underline": False,
            "bold": False,
            "italic": True,
        },
        "font_color": None,
        "highlight_color": None,
        "font_name": None,
        "font_size": None,
        "underline_style": None,
        "source_span_kind": "partial_span",
    }
    candidate = _make_candidate(
        text="五、售后服务\n1. 提供电话热线服务",
        start=300,
        position_ratio=0.5,
    )
    match = style_ops._LocalMatch(
        visible_start=0,
        visible_end=1,
        actual_start=300,
        actual_end=301,
        score=1.0,
        context_score=1.0,
        local_position_score=1.0,
        text_score=1.0,
        is_exact=True,
    )
    probe = style_ops._CandidateProbe(
        candidate=candidate,
        container_score=1.0,
        local_hint_score=1.0,
        position_score=1.0,
    )

    assert (
        style_ops._short_partial_match_gate_reason(fragment, probe, match)
        == "short_fragment_prefix_conflict"
    )


def test_short_partial_gate_rejects_dotted_number_prefix_exact_match() -> None:
    fragment = {
        "container_type": "paragraph",
        "container_locator": {"paragraph_index": 5},
        "source_text": "2.6.1",
        "normalized_text": normalize_semantic_text("2.6.1"),
        "container_text": "2.6.1 培训要求",
        "normalized_container_text": normalize_semantic_text("2.6.1 培训要求"),
        "context_before": "",
        "context_after": "培训",
        "position_ratio": 0.5,
        "local_position_ratio": 0.1,
        "style_flags": {
            "strikethrough": True,
            "underline": False,
            "bold": False,
            "italic": True,
        },
        "font_color": None,
        "highlight_color": None,
        "font_name": None,
        "font_size": None,
        "underline_style": None,
        "source_span_kind": "partial_span",
    }
    candidate = _make_candidate(
        text="2.6.1 售后服务",
        start=360,
        position_ratio=0.5,
    )
    match = style_ops._LocalMatch(
        visible_start=0,
        visible_end=len("2.6.1"),
        actual_start=360,
        actual_end=360 + len("2.6.1"),
        score=1.0,
        context_score=1.0,
        local_position_score=1.0,
        text_score=1.0,
        is_exact=True,
    )
    probe = style_ops._CandidateProbe(
        candidate=candidate,
        container_score=1.0,
        local_hint_score=1.0,
        position_score=1.0,
    )

    assert (
        style_ops._short_partial_match_gate_reason(fragment, probe, match)
        == "short_fragment_prefix_conflict"
    )


def test_apply_inline_style_fragments_keeps_short_exact_non_prefix_match(monkeypatch) -> None:
    fragment = {
        "container_type": "paragraph",
        "container_locator": {"paragraph_index": 8},
        "source_text": "五",
        "normalized_text": normalize_semantic_text("五"),
        "container_text": "设备五套",
        "normalized_container_text": normalize_semantic_text("设备五套"),
        "context_before": "设备",
        "context_after": "套",
        "position_ratio": 0.45,
        "local_position_ratio": 0.5,
        "style_flags": {
            "strikethrough": True,
            "underline": False,
            "bold": False,
            "italic": True,
        },
        "font_color": None,
        "highlight_color": None,
        "font_name": None,
        "font_size": None,
        "underline_style": None,
        "source_span_kind": "partial_span",
    }
    candidate_text = "投标人需提供设备五套用于现场部署"
    candidate = _make_candidate(text=candidate_text, start=420, position_ratio=0.45)
    monkeypatch.setattr(style_ops, "_build_target_containers", lambda *args, **kwargs: [candidate])

    doc = _FakeDoc()
    result = style_ops.apply_inline_style_fragments(
        doc=doc,
        inline_style_fragments=[fragment],
        bound_start=0,
        bound_end=520,
        log_parts=[],
    )

    expected_start = 420 + candidate_text.index("五")
    assert result["applied"] == 1
    assert doc.applied_ranges[0].Start == expected_start
    assert doc.applied_ranges[0].End == expected_start + len("五")
    assert doc.applied_ranges[0].Font.StrikeThrough is True
    assert doc.applied_ranges[0].Font.Italic is True


def test_apply_inline_style_fragments_skips_ambiguous_short_partial_across_logical_lines(monkeypatch) -> None:
    fragment = {
        "container_type": "paragraph",
        "container_locator": {"paragraph_index": 62},
        "source_text": "提供",
        "normalized_text": normalize_semantic_text("提供"),
        "container_text": "提供",
        "normalized_container_text": normalize_semantic_text("提供"),
        "context_before": "",
        "context_after": "",
        "position_ratio": 0.76,
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
    candidate = _make_candidate(
        text="第一行提供资料\n第二行提供原件",
        start=200,
        locator={"paragraph_index": 5},
        position_ratio=0.76,
    )
    monkeypatch.setattr(style_ops, "_build_target_containers", lambda *args, **kwargs: [candidate])

    result = style_ops.apply_inline_style_fragments(
        doc=_FakeDoc(),
        inline_style_fragments=[fragment],
        bound_start=0,
        bound_end=260,
        log_parts=[],
    )

    assert result["applied"] == 0
    assert result["skipped"] == 1
    assert result["issues"][0]["reason"] == "multiple_local_candidates"


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
