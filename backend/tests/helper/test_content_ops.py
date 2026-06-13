from __future__ import annotations

import pytest
import backend.helper.word_helper.content_ops as content_ops_module

from backend.helper.word_helper.content_ops import (
    apply_standard_insert_format,
    ensure_following_body_paragraph_insert_pos,
    insert_content_with_formatting,
    insert_items_inline_at_end_of_paragraph,
    insert_table_with_formatting,
    reset_generated_text_font_format,
    resolve_following_insert_pos,
)


def test_resolve_following_insert_pos_prefers_distinct_paragraph_boundary() -> None:
    calls: list[tuple[int, int, int]] = []

    def _fake_next(start: int, bound_end: int, *, max_lookahead: int = 0) -> int | None:
        calls.append((int(start), int(bound_end), int(max_lookahead)))
        return int(start)

    pos, prefer_distinct_paragraph = resolve_following_insert_pos(
        content_end=120,
        paragraph_end=136,
        bound_end=260,
        find_next_editable_pos_bounded=_fake_next,
    )

    assert pos == 136
    assert prefer_distinct_paragraph is True
    assert calls == [(136, 260, 20000)]


def test_resolve_following_insert_pos_falls_back_to_after_content_when_paragraph_boundary_missing() -> None:
    calls: list[int] = []

    def _fake_next(start: int, bound_end: int, *, max_lookahead: int = 0) -> int | None:
        calls.append(int(start))
        if int(start) == 136:
            return None
        return 124

    pos, prefer_distinct_paragraph = resolve_following_insert_pos(
        content_end=120,
        paragraph_end=136,
        bound_end=260,
        find_next_editable_pos_bounded=_fake_next,
    )

    assert pos == 124
    assert prefer_distinct_paragraph is False
    assert calls == [136, 121]


def test_resolve_following_insert_pos_uses_backward_fallback_when_forward_scan_is_blocked() -> None:
    def _fake_next(start: int, bound_end: int, *, max_lookahead: int = 0) -> int | None:
        return None

    def _fake_prev(start: int, *, max_lookback: int = 0) -> int | None:
        return 180

    pos, prefer_distinct_paragraph = resolve_following_insert_pos(
        content_end=120,
        paragraph_end=136,
        bound_end=260,
        find_next_editable_pos_bounded=_fake_next,
        find_prev_editable_pos=_fake_prev,
    )

    assert pos == 180
    assert prefer_distinct_paragraph is False


class _BoundEndRef:
    def __init__(self, value: int):
        self.value = int(value)


class _FakeParagraphRange:
    def __init__(self, end: int, text: str = ""):
        self.Start = 0
        self.End = int(end)
        self.Text = str(text or "")


class _FakeDoc:
    pass


class _FakeParagraphAccessor:
    def __init__(self, paragraph_range: _FakeParagraphRange):
        self._paragraph_range = paragraph_range

    def __call__(self, index: int):
        if index != 1:
            raise IndexError(index)
        return type("_FakeParagraph", (), {"Range": self._paragraph_range})()


class _FakeAnchorRange:
    def __init__(self, start: int, end: int, paragraph_range: _FakeParagraphRange):
        self.Start = int(start)
        self.End = int(end)
        self.Paragraphs = _FakeParagraphAccessor(paragraph_range)


class _FakeFont:
    def __init__(self, *, fail_attrs: set[str] | None = None):
        object.__setattr__(self, "_fail_attrs", set(fail_attrs or set()))
        object.__setattr__(self, "Name", "旧字体")
        object.__setattr__(self, "Size", 9)
        object.__setattr__(self, "Bold", True)
        object.__setattr__(self, "Italic", True)
        object.__setattr__(self, "Underline", 1)
        object.__setattr__(self, "StrikeThrough", True)
        object.__setattr__(self, "Color", 255)

    def __setattr__(self, name: str, value):
        if name == "HighlightColorIndex":
            raise AttributeError("Font has no HighlightColorIndex in this fake")
        if name in getattr(self, "_fail_attrs", set()):
            raise RuntimeError(f"{name} write failed")
        object.__setattr__(self, name, value)


class _FakeParagraphFormat:
    def __init__(self):
        self.LineSpacingRule = None
        self.LeftIndent = None
        self.FirstLineIndent = None
        self.OutlineLevel = None
        self.SpaceBeforeAuto = None
        self.SpaceAfterAuto = None
        self.SpaceBefore = None
        self.SpaceAfter = None
        self.PageBreakBefore = None
        self.KeepWithNext = None
        self.KeepTogether = None
        self.WidowControl = None


class _EmptyCollection:
    Count = 0

    def __call__(self, index: int):
        raise IndexError(index)


class _FakeFormatRange:
    def __init__(
        self,
        doc: "_FakeFormatDoc",
        start: int,
        end: int,
        *,
        text: str = "",
        fail_font_attrs: set[str] | None = None,
    ):
        self.doc = doc
        self.Start = int(start)
        self.End = int(end)
        self.Text = text
        self.Font = _FakeFont(fail_attrs=fail_font_attrs)
        self.HighlightColorIndex = 7
        self.ParagraphFormat = _FakeParagraphFormat()
        self.Tables = _EmptyCollection()

    def InsertAfter(self, value: str) -> None:
        self.doc.inserted.append((int(self.End), str(value)))
        self.End = int(self.End) + len(str(value))

    def Collapse(self, *_args) -> None:
        self.Start = int(self.End)

    def SetRange(self, start: int, end: int) -> None:
        self.Start = int(start)
        self.End = int(end)

    def Information(self, *_args) -> int:
        return 0


class _FakeFormatDoc:
    def __init__(self, *, fail_font_attrs: set[str] | None = None):
        self.fail_font_attrs = set(fail_font_attrs or set())
        self.created_ranges: list[_FakeFormatRange] = []
        self.inserted: list[tuple[int, str]] = []

    def Range(self, start: int, end: int) -> _FakeFormatRange:
        range_obj = _FakeFormatRange(
            self,
            start,
            end,
            fail_font_attrs=self.fail_font_attrs,
        )
        self.created_ranges.append(range_obj)
        return range_obj


class _FakeCellRange:
    def __init__(self, start: int = 0, end: int = 2):
        self.Start = int(start)
        self.End = int(end)
        self.Font = _FakeFont()
        self.HighlightColorIndex = 0
        self.ParagraphFormat = _FakeParagraphFormat()

    def InsertBefore(self, value: str) -> None:
        self.inserted_text = str(value)


class _FakeCell:
    def __init__(self, row: int, col: int):
        self.row = int(row)
        self.col = int(col)
        self.Range = _FakeCellRange()
        self.VerticalAlignment = None
        self.merge_calls: list[tuple[int, int, int, int]] = []

    def Merge(self, other: "_FakeCell") -> None:
        self.merge_calls.append((self.row, self.col, other.row, other.col))


class _FakeBorders:
    def __init__(self):
        self.Enable = False


class _FakeTable:
    def __init__(self, rows: int, cols: int):
        self.rows = int(rows)
        self.cols = int(cols)
        self.Borders = _FakeBorders()
        self.Range = type("_FakeTableRange", (), {"End": 999})()
        self.cells = {
            (row, col): _FakeCell(row, col)
            for row in range(1, rows + 1)
            for col in range(1, cols + 1)
        }

    def Cell(self, row: int, col: int) -> _FakeCell:
        return self.cells[(int(row), int(col))]


class _FakeTablesCollection:
    def __init__(self, owner: "_FakeTableDoc"):
        self.owner = owner

    def Add(self, _table_range, rows: int, cols: int) -> _FakeTable:
        table = _FakeTable(rows, cols)
        self.owner.created_tables.append(table)
        return table


class _FakeTableDoc(_FakeFormatDoc):
    def __init__(self):
        super().__init__()
        self.created_tables: list[_FakeTable] = []
        self.Tables = _FakeTablesCollection(self)
        self.deleted_ranges: list[tuple[int, int]] = []

    def Range(self, start: int, end: int):
        if int(end) < int(start):
            end = start
        range_obj = _FakeFormatRange(self, start, end)
        range_obj.Delete = lambda: self.deleted_ranges.append((int(start), int(end)))
        return range_obj


def assert_clean_generated_font(font: _FakeFont, *, name: str = "宋体", size: int = 12) -> None:
    assert font.Name == name
    assert font.Size == size
    assert font.Bold is False
    assert font.Italic is False
    assert font.Underline == 0
    assert font.StrikeThrough is False
    assert font.Color == 0


def assert_clean_generated_format(
    range_obj: _FakeFormatRange,
    *,
    name: str = "宋体",
    size: int = 12,
) -> None:
    assert_clean_generated_font(range_obj.Font, name=name, size=size)
    assert range_obj.HighlightColorIndex == 0


def test_reset_generated_text_font_format_clears_inherited_visible_styles() -> None:
    doc = _FakeFormatDoc()
    range_obj = doc.Range(10, 20)

    reset_generated_text_font_format(range_obj, font_name="黑体", font_size=14)

    assert_clean_generated_format(range_obj, name="黑体", size=14)


def test_reset_generated_text_font_format_reports_critical_failures() -> None:
    doc = _FakeFormatDoc(fail_font_attrs={"Color"})
    range_obj = doc.Range(10, 20)
    log_parts: list[str] = []

    with pytest.raises(
        RuntimeError,
        match="generated_insert_format_reset_version=font_sanitize_v1",
    ):
        reset_generated_text_font_format(range_obj, log_parts=log_parts)

    assert any("Color:Color write failed" in item for item in log_parts)


def test_apply_standard_insert_format_resets_font_and_keeps_paragraph_contract() -> None:
    doc = _FakeFormatDoc()
    range_obj = doc.Range(10, 20)

    apply_standard_insert_format(range_obj)

    assert_clean_generated_format(range_obj)
    assert range_obj.ParagraphFormat.LeftIndent == 0
    assert range_obj.ParagraphFormat.FirstLineIndent == 0
    assert range_obj.ParagraphFormat.KeepWithNext is False


def test_insert_content_with_formatting_sanitizes_inserted_range() -> None:
    doc = _FakeFormatDoc()
    insert_range = doc.Range(10, 10)

    inserted_range = insert_content_with_formatting(
        doc,
        insert_range,
        "红色宿主后的正文",
        bound_start=0,
        get_bound_end=lambda: 100,
    )

    assert_clean_generated_format(inserted_range)
    assert doc.inserted[-1] == (10, "红色宿主后的正文\r")


def test_insert_items_inline_at_end_of_paragraph_sanitizes_inline_text() -> None:
    doc = _FakeFormatDoc()
    paragraph = _FakeParagraphRange(20, "付款方式：旧值\r")

    inserted = insert_items_inline_at_end_of_paragraph(
        doc,
        paragraph,
        [{"type": "text", "line": "新增正文"}],
        get_bound_end=lambda: 100,
    )

    assert inserted == 1
    assert_clean_generated_format(doc.created_ranges[-1])


def test_insert_items_inline_table_fallback_sanitizes_text_rows(monkeypatch) -> None:
    doc = _FakeFormatDoc()
    paragraph = _FakeParagraphRange(20, "付款方式：旧值\r")
    seen: dict[str, object] = {}

    def _raise_table_error(*_args, **kwargs):
        seen["log_parts"] = kwargs.get("log_parts")
        raise RuntimeError("table insert failed")

    monkeypatch.setattr(content_ops_module, "insert_table_with_formatting", _raise_table_error)
    log_parts: list[str] = []

    inserted = insert_items_inline_at_end_of_paragraph(
        doc,
        paragraph,
        [{"type": "table", "rows": [["A", "B"]]}],
        get_bound_end=lambda: 100,
        log_parts=log_parts,
    )

    assert inserted == 1
    assert seen["log_parts"] is log_parts
    assert_clean_generated_format(doc.created_ranges[-1])


def test_insert_items_inline_structured_table_fallback_sanitizes_text_rows(monkeypatch) -> None:
    doc = _FakeFormatDoc()
    paragraph = _FakeParagraphRange(20, "付款方式：旧值\r")

    monkeypatch.setattr(
        content_ops_module,
        "insert_table_with_formatting",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("structured insert failed")),
    )

    inserted = insert_items_inline_at_end_of_paragraph(
        doc,
        paragraph,
        [
            {
                "type": "structured_table",
                "table_id": "TP1",
                "table_model": {
                    "table_id": "TP1",
                    "rows": 1,
                    "cols": 2,
                    "cells": [
                        {"row": 1, "col": 1, "row_span": 1, "col_span": 2, "text": "合计"}
                    ],
                },
            }
        ],
        get_bound_end=lambda: 100,
    )

    assert inserted == 1
    assert_clean_generated_format(doc.created_ranges[-1])


def test_insert_table_with_formatting_restores_structured_merge_topology() -> None:
    doc = _FakeTableDoc()
    insert_range = doc.Range(10, 10)

    table = insert_table_with_formatting(
        doc,
        insert_range,
        structured_table={
            "table_id": "TP1",
            "rows": 3,
            "cols": 3,
            "cells": [
                {"row": 1, "col": 1, "row_span": 2, "col_span": 2, "text": "楼宇"},
                {"row": 1, "col": 3, "row_span": 1, "col_span": 1, "text": "岗位"},
                {"row": 2, "col": 3, "row_span": 1, "col_span": 1, "text": "安保"},
                {"row": 3, "col": 1, "row_span": 1, "col_span": 3, "text": "合计"},
            ],
        },
        get_bound_end=lambda: 100,
    )

    assert table is doc.created_tables[0]
    assert table.Cell(1, 1).merge_calls == [(1, 1, 2, 2)]
    assert table.Cell(3, 1).merge_calls == [(3, 1, 3, 3)]
    assert table.Cell(1, 1).Range.inserted_text == "楼宇"
    assert table.Cell(3, 1).Range.inserted_text == "合计"


def test_ensure_following_body_paragraph_insert_pos_creates_new_paragraph_when_gap_missing(
    monkeypatch,
) -> None:
    """
    付款方式典型场景：字段段末本就存在 \r（下一段是标题，不可写）。
    resolve_following_insert_pos 会返回 prefer_distinct_paragraph=True，
    但可写性校验不通过，因此走主动造段分支，helper 返回新拆段的可写落点。
    """
    bound_end_ref = _BoundEndRef(140)
    doc = _FakeDoc()
    paragraph_range = _FakeParagraphRange(140)
    anchor_range = _FakeAnchorRange(120, 128, paragraph_range)

    # resolve_following_insert_pos 会调用 find_next_editable_pos_bounded 返回“边界”，
    # 但随后 caller 用 is_writable_body_paragraph_pos 判定其不是可写正文段。
    def _fake_next(start: int, bound_end: int, *, max_lookahead: int = 0) -> int | None:
        return int(start)

    # 模拟：resolve 返回的位置（140）不是可写正文段；而 helper 造出来的位置（139）是。
    def _fake_is_writable(doc, pos: int) -> bool:
        return pos == 139

    def _fake_ensure_break(*args, **kwargs):
        del args, kwargs
        bound_end_ref.value = 148
        return True, 139

    monkeypatch.setattr(
        content_ops_module,
        "ensure_paragraph_break_after_paragraph",
        _fake_ensure_break,
    )
    monkeypatch.setattr(
        content_ops_module,
        "is_writable_body_paragraph_pos",
        _fake_is_writable,
    )

    pos, created_new_paragraph = ensure_following_body_paragraph_insert_pos(
        doc,
        anchor_range,
        bound_end=140,
        get_bound_end=lambda: bound_end_ref.value,
        find_next_editable_pos_bounded=_fake_next,
        find_prev_editable_pos=lambda start, *, max_lookback=0: None,
        field_label="付款方式",
    )

    assert pos == 139
    assert created_new_paragraph is True


def test_ensure_following_body_paragraph_insert_pos_reuses_existing_writable_paragraph(
    monkeypatch,
) -> None:
    """交付日期场景：resolve 已定位现成的可写正文段，无需造段。"""
    bound_end_ref = _BoundEndRef(200)
    doc = _FakeDoc()
    paragraph_range = _FakeParagraphRange(140)
    anchor_range = _FakeAnchorRange(120, 128, paragraph_range)

    def _fake_next(start: int, bound_end: int, *, max_lookahead: int = 0) -> int | None:
        return int(start)

    monkeypatch.setattr(
        content_ops_module,
        "is_writable_body_paragraph_pos",
        lambda doc, pos: True,
    )

    def _unexpected_ensure_break(*args, **kwargs):
        raise AssertionError("已有可写正文段时不应调用 helper 造段")

    monkeypatch.setattr(
        content_ops_module,
        "ensure_paragraph_break_after_paragraph",
        _unexpected_ensure_break,
    )

    pos, created_new_paragraph = ensure_following_body_paragraph_insert_pos(
        doc,
        anchor_range,
        bound_end=200,
        get_bound_end=lambda: bound_end_ref.value,
        find_next_editable_pos_bounded=_fake_next,
        find_prev_editable_pos=lambda start, *, max_lookback=0: None,
        field_label="交付日期",
    )

    assert pos == 140
    assert created_new_paragraph is False


def test_ensure_following_body_paragraph_insert_pos_fails_when_helper_cannot_create(
    monkeypatch,
) -> None:
    """
    helper 无法造段、且向后扫描也找不到任何可编辑位置时才 fail-fast。
    （软回车兜底始终被禁止。）
    """
    bound_end_ref = _BoundEndRef(140)
    doc = _FakeDoc()
    paragraph_range = _FakeParagraphRange(140)
    anchor_range = _FakeAnchorRange(120, 128, paragraph_range)

    monkeypatch.setattr(
        content_ops_module,
        "is_writable_body_paragraph_pos",
        lambda doc, pos: False,
    )
    monkeypatch.setattr(
        content_ops_module,
        "ensure_paragraph_break_after_paragraph",
        lambda *args, **kwargs: (False, None),
    )

    with pytest.raises(ValueError, match="创建正文段落失败"):
        ensure_following_body_paragraph_insert_pos(
            doc,
            anchor_range,
            bound_end=140,
            get_bound_end=lambda: bound_end_ref.value,
            find_next_editable_pos_bounded=lambda start, bound_end, *, max_lookahead=0: None,
            find_prev_editable_pos=lambda start, *, max_lookback=0: None,
            field_label="付款方式",
        )


def test_ensure_following_body_paragraph_insert_pos_falls_back_to_forward_scan_when_split_fails(
    monkeypatch,
) -> None:
    """
    gngk 模板典型场景：helper 无法在字段段内拆段（SDT 锁住 pilcrow 前），
    但向后扫描仍能找到可编辑位置。这种情况下应该走兜底，而不是报“未找到可写独立正文段”。
    """
    bound_end_ref = _BoundEndRef(260)
    doc = _FakeDoc()
    paragraph_range = _FakeParagraphRange(140)
    anchor_range = _FakeAnchorRange(120, 128, paragraph_range)

    monkeypatch.setattr(
        content_ops_module,
        "is_writable_body_paragraph_pos",
        lambda doc, pos: False,  # resolve 判不可写 → 走 create 分支。
    )
    monkeypatch.setattr(
        content_ops_module,
        "ensure_paragraph_break_after_paragraph",
        lambda *args, **kwargs: (False, None),  # helper 也拒绝造段。
    )

    def _forward_scan(start: int, bound_end: int, *, max_lookahead: int = 0) -> int | None:
        return 200  # 兜底扫描命中。

    pos, created_new_paragraph = ensure_following_body_paragraph_insert_pos(
        doc,
        anchor_range,
        bound_end=260,
        get_bound_end=lambda: bound_end_ref.value,
        find_next_editable_pos_bounded=_forward_scan,
        find_prev_editable_pos=lambda start, *, max_lookback=0: None,
        field_label="付款方式",
    )

    assert pos == 200
    assert created_new_paragraph is True
