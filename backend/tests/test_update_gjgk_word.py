import ast
import re
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "nodes"
    / "gjgk_word_nodes"
    / "update_gjgk_word.py"
)
MODULE_SOURCE = MODULE_PATH.read_text(encoding="utf-8")
MODULE_AST = ast.parse(MODULE_SOURCE)


def _get_constant(name: str):
    for node in MODULE_AST.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == name:
                return ast.literal_eval(node.value)
    raise KeyError(name)


def _load_functions(*names: str, extra_globals=None):
    selected_nodes = []
    for node in MODULE_AST.body:
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "__future__"
            and any(alias.name == "annotations" for alias in node.names)
        ):
            selected_nodes.append(node)
            continue
        if isinstance(node, ast.FunctionDef) and node.name in names:
            selected_nodes.append(node)

    subset_module = ast.Module(body=selected_nodes, type_ignores=[])
    ast.fix_missing_locations(subset_module)

    namespace = {
        "re": re,
        "pathlib": __import__("pathlib"),
        "Any": object,
        "Callable": object,
        "Dict": dict,
        "List": list,
        "Optional": object,
        "DEFAULT_TEST_SUFFIX": _get_constant("DEFAULT_TEST_SUFFIX"),
        "DEFAULT_DELETE_TEST_SUFFIX": _get_constant("DEFAULT_DELETE_TEST_SUFFIX"),
        "MANUAL_TEST_INSERT_TEXT": _get_constant("MANUAL_TEST_INSERT_TEXT"),
        "GjgkTenderGraphState": dict,
    }
    if extra_globals:
        namespace.update(extra_globals)

    exec(compile(subset_module, str(MODULE_PATH), "exec"), namespace)
    return namespace


def test_build_insert_items_preserves_text_table_text_order():
    namespace = _load_functions(
        "_is_table_separator_line",
        "_parse_table_row",
        "_looks_like_table_row",
        "_parse_table_block",
        "_build_insert_items",
    )

    polished_text = """一、项目概述
| 序号 | 名称 |
| --- | --- |
| 1 | 设备A |
二、技术需求"""

    items = namespace["_build_insert_items"](polished_text)

    assert [item["type"] for item in items] == ["text", "table", "text"]
    assert items[0]["line"] == "一、项目概述"
    assert items[1]["rows"] == [["序号", "名称"], ["1", "设备A"]]
    assert items[2]["line"] == "二、技术需求"


def test_build_insert_items_skips_blank_lines_without_creating_empty_items():
    namespace = _load_functions(
        "_is_table_separator_line",
        "_parse_table_row",
        "_looks_like_table_row",
        "_parse_table_block",
        "_build_insert_items",
    )

    polished_text = """

一、项目概述

须提供详细技术需求。

| 序号 | 内容 |
| --- | --- |
| 1 | 主机 |

"""

    items = namespace["_build_insert_items"](polished_text)

    assert len(items) == 3
    assert items[0] == {"type": "text", "line": "一、项目概述"}
    assert items[1] == {"type": "text", "line": "须提供详细技术需求。"}
    assert items[2]["type"] == "table"


def test_resolve_gjgk_content_range_uses_allow_empty(monkeypatch):
    captured = {}

    def fake_resolve_anchor_content_range(**kwargs):
        captured.update(kwargs)
        return {
            "range_start": 10,
            "range_end": 10,
            "start_page": 3,
            "end_page": 3,
            "before_page": 3,
            "after_page": 3,
        }

    namespace = _load_functions(
        "_resolve_gjgk_content_range",
        extra_globals={
            "resolve_anchor_content_range": fake_resolve_anchor_content_range,
        },
    )

    result = namespace["_resolve_gjgk_content_range"](
        doc=object(),
        word_app=object(),
        before_hit={"page": 3, "end": 100},
        after_hit={"page": 3, "start": 100},
    )

    assert captured["tender_type"] == "gjgk"
    assert captured["allow_empty"] is True
    assert result["range_start"] == 10
    assert result["range_end"] == 10


def test_build_manual_test_state_uses_gjgk_defaults():
    prepared_doc_path = "D:/tmp/gjgk-test.doc"
    before_text = "技术规格及要求"
    after_text = "附件1：投标文件封面（格式）"

    namespace = _load_functions(
        "_build_manual_test_state",
        extra_globals={
            "get_default_anchor_texts": lambda tender_type: (before_text, after_text)
        },
    )
    state = namespace["_build_manual_test_state"](prepared_doc_path)

    assert state["tender_type"] == "gjgk"
    assert state["prepared_doc_path"] == prepared_doc_path
    assert state["insertion_before_text"] == before_text
    assert state["insertion_after_text"] == after_text
    assert state["polished_text"] == _get_constant("MANUAL_TEST_INSERT_TEXT")


def test_build_manual_delete_state_uses_gjgk_defaults():
    prepared_doc_path = "D:/tmp/gjgk-delete-test.doc"
    before_text = "技术规格及要求"
    after_text = "附件1：投标文件封面（格式）"

    namespace = _load_functions(
        "_build_manual_delete_state",
        extra_globals={
            "get_default_anchor_texts": lambda tender_type: (before_text, after_text)
        },
    )
    state = namespace["_build_manual_delete_state"](prepared_doc_path)

    assert state["tender_type"] == "gjgk"
    assert state["prepared_doc_path"] == prepared_doc_path
    assert state["insertion_before_text"] == before_text
    assert state["insertion_after_text"] == after_text
    assert "polished_text" not in state


def test_build_manual_test_output_path_appends_suffix():
    source_doc_path = Path("D:/tmp/sample.doc")
    namespace = _load_functions("_build_manual_test_output_path")

    output_path = namespace["_build_manual_test_output_path"](source_doc_path)

    assert output_path.name == "sample-gjgk-update-test.doc"


def test_build_manual_delete_output_path_appends_suffix():
    source_doc_path = Path("D:/tmp/sample.doc")
    namespace = _load_functions("_build_manual_delete_output_path")

    output_path = namespace["_build_manual_delete_output_path"](source_doc_path)

    assert output_path.name == "sample-gjgk-delete-test.doc"


def test_apply_standard_insert_format_clears_pagination_flags():
    class _Font:
        def __init__(self):
            self.Name = None
            self.Size = None
            self.Bold = True

    class _ParagraphFormat:
        def __init__(self):
            self.LineSpacingRule = None
            self.LeftIndent = None
            self.FirstLineIndent = None
            self.OutlineLevel = None
            self.SpaceBeforeAuto = None
            self.SpaceAfterAuto = None
            self.SpaceBefore = None
            self.SpaceAfter = None
            self.PageBreakBefore = True
            self.KeepWithNext = True
            self.KeepTogether = True
            self.WidowControl = True

    class _Range:
        def __init__(self):
            self.Font = _Font()
            self.ParagraphFormat = _ParagraphFormat()

    namespace = _load_functions(
        "_apply_standard_insert_format",
        extra_globals={
            "INSERT_FONT_NAME": "宋体",
            "INSERT_FONT_SIZE": 12,
            "wdLineSpace1pt5": 1.5,
            "wdOutlineLevelBodyText": 10,
        },
    )

    rng = _Range()
    namespace["_apply_standard_insert_format"](rng)

    assert rng.Font.Name == "宋体"
    assert rng.Font.Size == 12
    assert rng.Font.Bold is False
    assert rng.ParagraphFormat.PageBreakBefore is False
    assert rng.ParagraphFormat.KeepWithNext is False
    assert rng.ParagraphFormat.KeepTogether is False
    assert rng.ParagraphFormat.WidowControl is False


def test_find_first_insert_position_on_anchor_page_skips_locked_positions():
    class _ProbeRange:
        def __init__(self, position: int, table_positions: set[int]):
            self.Start = position
            self._table_positions = table_positions

        def Information(self, flag):
            assert flag == "wdWithInTable"
            return self.Start in self._table_positions

    class _Doc:
        class Content:
            End = 10

        def __init__(self, table_positions: set[int]):
            self._table_positions = table_positions

        def Range(self, start, end):
            return _ProbeRange(start, self._table_positions)

    namespace = _load_functions(
        "_find_first_insert_position_on_anchor_page",
        extra_globals={
            "_get_position_page": lambda doc, pos, fallback_page: 3 if pos <= 5 else 4,
            "_is_range_locked": lambda doc, rng: int(rng.Start) < 3,
            "wdWithInTable": "wdWithInTable",
        },
    )

    result = namespace["_find_first_insert_position_on_anchor_page"](
        _Doc(set()),
        start_pos=1,
        bound_start=1,
        get_bound_end=lambda: 8,
        anchor_page=3,
    )

    assert result == 3


def test_find_first_insert_position_on_anchor_page_rejects_leftover_table_host():
    class _ProbeRange:
        def __init__(self, position: int, table_positions: set[int]):
            self.Start = position
            self._table_positions = table_positions

        def Information(self, flag):
            assert flag == "wdWithInTable"
            return self.Start in self._table_positions

    class _Doc:
        class Content:
            End = 10

        def __init__(self, table_positions: set[int]):
            self._table_positions = table_positions

        def Range(self, start, end):
            return _ProbeRange(start, self._table_positions)

    namespace = _load_functions(
        "_find_first_insert_position_on_anchor_page",
        extra_globals={
            "_get_position_page": lambda doc, pos, fallback_page: 3,
            "_is_range_locked": lambda doc, rng: False,
            "wdWithInTable": "wdWithInTable",
        },
    )

    with pytest.raises(ValueError, match="旧表格宿主"):
        namespace["_find_first_insert_position_on_anchor_page"](
            _Doc({1}),
            start_pos=1,
            bound_start=1,
            get_bound_end=lambda: 8,
            anchor_page=3,
        )


def test_pick_outermost_table_returns_largest_span():
    class _TableRange:
        def __init__(self, start: int, end: int):
            self.Start = start
            self.End = end

    class _Table:
        def __init__(self, start: int, end: int):
            self.Range = _TableRange(start, end)

    class _Tables:
        def __init__(self):
            self._tables = [_Table(10, 20), _Table(5, 40)]
            self.Count = len(self._tables)

        def __call__(self, index):
            return self._tables[index - 1]

    namespace = _load_functions("_pick_outermost_table")

    result = namespace["_pick_outermost_table"](_Tables())

    assert result.Range.Start == 5
    assert result.Range.End == 40


def test_move_insert_range_after_current_table_inserts_paragraph_after_outermost_host():
    class _TableRange:
        def __init__(self, start: int, end: int):
            self.Start = start
            self.End = end
            self.insert_paragraph_after_calls = 0

        def InsertParagraphAfter(self):
            self.insert_paragraph_after_calls += 1
            self.End = 12

    class _Table:
        def __init__(self, start: int, end: int):
            self.Range = _TableRange(start, end)

    class _Tables:
        def __init__(self):
            self._tables = [_Table(6, 9), _Table(2, 11)]
            self.Count = len(self._tables)

        def __call__(self, index):
            return self._tables[index - 1]

    class _InsertRange:
        def __init__(self, tables):
            self.Start = 8
            self.Tables = tables

        def Information(self, flag):
            assert flag == "wdWithInTable"
            return self.Start < 12

    collapsed_positions = []

    def _set_collapsed_range(insert_range, position):
        insert_range.Start = position
        collapsed_positions.append(position)

    namespace = _load_functions(
        "_pick_outermost_table",
        "_is_within_table",
        "_move_insert_range_after_current_table",
        extra_globals={
            "_set_collapsed_range": _set_collapsed_range,
            "_find_next_non_table_editable_pos_bounded": (
                lambda doc, start_pos, bound_start, get_bound_end: 12
            ),
            "wdWithInTable": "wdWithInTable",
        },
    )

    tables = _Tables()
    insert_range = _InsertRange(tables)

    result = namespace["_move_insert_range_after_current_table"](
        object(),
        insert_range,
        bound_start=1,
        get_bound_end=lambda: 20,
    )

    assert result is True
    assert tables(2).Range.insert_paragraph_after_calls == 1
    assert collapsed_positions[-1] == 12


def test_find_next_editable_pos_bounded_can_return_none_when_disabled():
    class _Range:
        def __init__(self, start: int):
            self.Start = start
            self.End = start

    class _Doc:
        class Content:
            End = 5

        def Range(self, start, end):
            return _Range(start)

    namespace = _load_functions(
        "_find_next_editable_pos_bounded",
        extra_globals={
            "_is_range_locked": lambda doc, rng: True,
        },
    )

    result = namespace["_find_next_editable_pos_bounded"](
        _Doc(),
        start_pos=1,
        bound_start=1,
        get_bound_end=lambda: 4,
        raise_on_missing=False,
    )

    assert result is None


def test_prime_empty_insert_slot_consumes_first_insert_and_resets_cursor():
    class _InsertRange:
        def __init__(self):
            self.Start = 8
            self.End = 8

        def SetRange(self, start, end):
            self.Start = start
            self.End = end

    inserted_lines = []

    def fake_insert_text_line(doc, insert_range, line, **kwargs):
        inserted_lines.append(line)
        insert_range.SetRange(99, 99)

    def fake_set_collapsed_range(insert_range, position):
        insert_range.SetRange(position, position)

    namespace = _load_functions(
        "_prime_empty_insert_slot",
        extra_globals={
            "_build_bootstrap_marker": lambda: "BOOTSTRAP-MARKER",
            "_insert_text_line": fake_insert_text_line,
            "_set_collapsed_range": fake_set_collapsed_range,
        },
    )

    insert_range = _InsertRange()
    log_parts = []
    marker = namespace["_prime_empty_insert_slot"](
        object(),
        insert_range,
        bound_start=8,
        get_bound_end=lambda: 8,
        log_parts=log_parts,
    )

    assert marker == "BOOTSTRAP-MARKER"
    assert inserted_lines == ["BOOTSTRAP-MARKER"]
    assert insert_range.Start == 8
    assert insert_range.End == 8
    assert any("bootstrap 标记" in part for part in log_parts)


def test_ensure_insert_range_only_normalizes_bounds_and_locks():
    class _InsertRange:
        def __init__(self):
            self.Start = 5
            self.End = 5
            self._in_table = False

        def Collapse(self, _flag):
            return None

        def SetRange(self, start, end):
            self.Start = start
            self.End = end

        def Information(self, flag):
            assert flag == "wdWithInTable"
            return self._in_table

    class _ProbeRange:
        def __init__(self, start: int):
            self.Start = start
            self.End = start

    class _Doc:
        def Range(self, start, end):
            return _ProbeRange(start)

    namespace = _load_functions(
        "_ensure_insert_range",
        extra_globals={
            "_set_collapsed_range": lambda insert_range, position: insert_range.SetRange(
                position, position
            ),
            "_is_range_locked": lambda doc, rng: False,
            "wdCollapseStart": "wdCollapseStart",
        },
    )

    insert_range = _InsertRange()
    namespace["_ensure_insert_range"](
        _Doc(),
        insert_range,
        bound_start=1,
        get_bound_end=lambda: 20,
    )

    assert insert_range.Start == 5
    assert insert_range.End == 5


def test_remove_marker_paragraphs_deletes_only_matching_bootstrap_marker():
    class _Range:
        def __init__(self, text: str):
            self.Text = text
            self.deleted = False

        def Delete(self):
            self.deleted = True

    class _Paragraph:
        def __init__(self, text: str):
            self.Range = _Range(text)

    class _DocRange:
        def __init__(self, paragraphs):
            self.Paragraphs = paragraphs

    class _Doc:
        def __init__(self, paragraphs):
            self._paragraphs = paragraphs

        def Range(self, start, end):
            return _DocRange(self._paragraphs)

    namespace = _load_functions(
        "_normalize_visible_paragraph_text",
        "_remove_marker_paragraphs",
    )

    paragraphs = [
        _Paragraph("普通正文\r"),
        _Paragraph("BOOTSTRAP-MARKER\r"),
        _Paragraph("其他正文\r"),
    ]
    log_parts = []

    removed = namespace["_remove_marker_paragraphs"](
        _Doc(paragraphs),
        marker_text="BOOTSTRAP-MARKER",
        search_start=0,
        search_end=100,
        log_parts=log_parts,
    )

    assert removed == 1
    assert paragraphs[0].Range.deleted is False
    assert paragraphs[1].Range.deleted is True
    assert paragraphs[2].Range.deleted is False
    assert any("bootstrap 标记段落" in part for part in log_parts)


def test_insert_table_allows_post_table_cursor_to_remain_at_table_end():
    class _ParagraphFormat:
        def __init__(self):
            self.Alignment = None

    class _CellRange:
        def __init__(self):
            self.Start = 0
            self.End = 1
            self.ParagraphFormat = _ParagraphFormat()

        def InsertBefore(self, text):
            self.text = text

    class _Cell:
        def __init__(self):
            self.Range = _CellRange()
            self.VerticalAlignment = None

    class _TableRange:
        def __init__(self, start: int, end: int):
            self.Start = start
            self.End = end

    class _Borders:
        def __init__(self):
            self.Enable = None

    class _Table:
        def __init__(self, start: int, end: int):
            self.Range = _TableRange(start, end)
            self.Borders = _Borders()

        def Cell(self, row, col):
            return _Cell()

    class _TablesApi:
        def __init__(self, table):
            self._table = table

        def Add(self, table_range, rows, cols):
            return self._table

    class _DocRange:
        def __init__(self, start: int, end: int):
            self.Start = start
            self.End = end

        def Delete(self):
            return None

    class _Doc:
        def __init__(self, table):
            self.Tables = _TablesApi(table)

        def Range(self, start, end):
            return _DocRange(start, end)

    class _InsertRange:
        def __init__(self):
            self.Start = 5
            self.End = 5
            self._in_table = True

        def Information(self, flag):
            assert flag == "wdWithInTable"
            return self._in_table

        def SetRange(self, start, end):
            self.Start = start
            self.End = end
            self._in_table = start == 8

        def Collapse(self, _flag):
            return None

        @property
        def Tables(self):
            class _ParentTables:
                Count = 1

                def __call__(self, index):
                    assert index == 1
                    return table

            return _ParentTables()

    namespace = _load_functions(
        "_insert_table",
        extra_globals={
            "_ensure_insert_range": lambda doc, insert_range, **kwargs: None,
            "_apply_standard_insert_format": lambda inserted_rng: None,
            "_set_collapsed_range": lambda insert_range, position: insert_range.SetRange(
                position, position
            ),
            "wdCollapseStart": "wdCollapseStart",
            "wdCollapseEnd": "wdCollapseEnd",
            "wdWithInTable": "wdWithInTable",
        },
    )

    table = _Table(5, 8)
    doc = _Doc(table)
    insert_range = _InsertRange()

    result = namespace["_insert_table"](
        doc,
        insert_range,
        [["序号", "名称"], ["1", "设备A"]],
        bound_start=1,
        get_bound_end=lambda: 20,
    )

    assert result is table
    assert insert_range.Start == 8
    assert insert_range.End == 8


def test_insert_text_line_can_continue_from_table_end_cursor():
    class _ParagraphFormat:
        def __init__(self):
            self.LineSpacingRule = None
            self.LeftIndent = None
            self.FirstLineIndent = None
            self.OutlineLevel = None

    class _Font:
        def __init__(self):
            self.Name = None
            self.Size = None
            self.Bold = None

    class _InsertedRange:
        def __init__(self, start: int, end: int):
            self.Start = start
            self.End = end
            self.Font = _Font()
            self.ParagraphFormat = _ParagraphFormat()

    class _Doc:
        def __init__(self):
            self.write_calls = []

        def Range(self, start, end):
            return _InsertedRange(start, end)

    class _InsertRange:
        def __init__(self, doc):
            self.Start = 8
            self.End = 8
            self._doc = doc

        def SetRange(self, start, end):
            self.Start = start
            self.End = end

        def Collapse(self, _flag):
            return None

        def InsertAfter(self, text):
            self._doc.write_calls.append((self.Start, text))
            # 模拟真实 Word COM：执行插入后，当前 live range 仍可能停留在原位置。

    ensured = {"calls": 0}

    def fake_ensure(doc, target_range, *, get_bound_end, **kwargs):
        ensured["calls"] += 1
        bound_end = get_bound_end()
        if target_range.Start > bound_end:
            target_range.SetRange(bound_end, bound_end)

    def fake_set_collapsed_range(target_range, position):
        target_range.SetRange(position, position)

    namespace = _load_functions(
        "_insert_text_line",
        extra_globals={
            "_ensure_insert_range": fake_ensure,
            "_set_collapsed_range": fake_set_collapsed_range,
            "_apply_standard_insert_format": lambda inserted_rng: None,
        },
    )

    doc = _Doc()
    insert_range = _InsertRange(doc)

    inserted_rng = namespace["_insert_text_line"](
        doc,
        insert_range,
        "续写正文",
        bound_start=1,
        get_bound_end=lambda: 8,
    )

    assert inserted_rng.Start == 8
    assert inserted_rng.End == 12
    assert insert_range.Start == insert_range.End
    assert insert_range.Start > 8
    assert doc.write_calls == [(8, "续写正文\r")]
    assert ensured["calls"] == 2


def test_insert_text_line_prefers_live_range_end_when_word_relocates_first_write():
    class _ParagraphFormat:
        def __init__(self):
            self.LineSpacingRule = None
            self.LeftIndent = None
            self.FirstLineIndent = None
            self.OutlineLevel = None

    class _Font:
        def __init__(self):
            self.Name = None
            self.Size = None
            self.Bold = None

    class _InsertedRange:
        def __init__(self, start: int, end: int):
            self.Start = start
            self.End = end
            self.Font = _Font()
            self.ParagraphFormat = _ParagraphFormat()

    class _Doc:
        def __init__(self):
            self.write_calls = []
            self.actual_write_positions = [30, 37]

        def Range(self, start, end):
            return _InsertedRange(start, end)

    class _InsertRange:
        def __init__(self, doc):
            self.Start = 8
            self.End = 8
            self._doc = doc

        def SetRange(self, start, end):
            self.Start = start
            self.End = end

        def Collapse(self, _flag):
            return None

        def InsertAfter(self, text):
            actual_start = self._doc.actual_write_positions.pop(0)
            self._doc.write_calls.append((actual_start, text))
            self.Start = actual_start
            self.End = actual_start + len(text)

    def fake_set_collapsed_range(target_range, position):
        target_range.SetRange(position, position)

    def fake_ensure(doc, target_range, *, bound_start, get_bound_end, **kwargs):
        bound_end = get_bound_end()
        pos = target_range.Start
        if pos < bound_start:
            pos = bound_start
        if pos > bound_end:
            pos = bound_end
        target_range.SetRange(pos, pos)

    namespace = _load_functions(
        "_insert_text_line",
        extra_globals={
            "_ensure_insert_range": fake_ensure,
            "_set_collapsed_range": fake_set_collapsed_range,
            "_apply_standard_insert_format": lambda inserted_rng: None,
        },
    )

    doc = _Doc()
    insert_range = _InsertRange(doc)
    insert_cursor_bound_end = [8]

    def get_bound_end():
        return max(8, insert_cursor_bound_end[0])

    namespace["_insert_text_line"](
        doc,
        insert_range,
        "一、项目概述",
        bound_start=8,
        get_bound_end=get_bound_end,
    )
    insert_cursor_bound_end[0] = max(insert_cursor_bound_end[0], insert_range.Start)

    namespace["_insert_text_line"](
        doc,
        insert_range,
        "1、设备名称及数量：",
        bound_start=8,
        get_bound_end=get_bound_end,
    )

    assert doc.write_calls == [(30, "一、项目概述\r"), (37, "1、设备名称及数量：\r")]
    assert insert_range.Start == 48
    assert insert_range.End == 48


def test_insert_text_line_sequence_advances_cursor_when_bound_updates_after_each_write():
    class _ParagraphFormat:
        def __init__(self):
            self.LineSpacingRule = None
            self.LeftIndent = None
            self.FirstLineIndent = None
            self.OutlineLevel = None

    class _Font:
        def __init__(self):
            self.Name = None
            self.Size = None
            self.Bold = None

    class _InsertedRange:
        def __init__(self, start: int, end: int):
            self.Start = start
            self.End = end
            self.Font = _Font()
            self.ParagraphFormat = _ParagraphFormat()

    class _Doc:
        def __init__(self):
            self.write_calls = []

        def Range(self, start, end):
            return _InsertedRange(start, end)

    class _InsertRange:
        def __init__(self, pos: int, doc):
            self.Start = pos
            self.End = pos
            self._doc = doc

        def SetRange(self, start, end):
            self.Start = start
            self.End = end

        def Collapse(self, _flag):
            return None

        def InsertAfter(self, text):
            self._doc.write_calls.append((self.Start, text))

    def fake_set_collapsed_range(target_range, position):
        target_range.SetRange(position, position)

    def fake_ensure(doc, target_range, *, bound_start, get_bound_end, **kwargs):
        bound_end = get_bound_end()
        pos = target_range.Start
        if pos < bound_start:
            pos = bound_start
        if pos > bound_end:
            pos = bound_end
        target_range.SetRange(pos, pos)

    namespace = _load_functions(
        "_insert_text_line",
        extra_globals={
            "_ensure_insert_range": fake_ensure,
            "_set_collapsed_range": fake_set_collapsed_range,
            "_apply_standard_insert_format": lambda inserted_rng: None,
        },
    )

    doc = _Doc()
    insert_start = 8
    insert_range = _InsertRange(insert_start, doc)
    insert_cursor_bound_end = [insert_start]
    anchor_bound_end = 8

    def get_bound_end():
        return max(anchor_bound_end, insert_cursor_bound_end[0])

    cursor_history = []
    for line in ["第1行", "第2行", "第3行"]:
        namespace["_insert_text_line"](
            doc,
            insert_range,
            line,
            bound_start=insert_start,
            get_bound_end=get_bound_end,
        )
        insert_cursor_bound_end[0] = max(
            insert_cursor_bound_end[0],
            insert_range.Start,
            insert_range.End,
        )
        cursor_history.append(insert_range.Start)

    assert cursor_history == [12, 16, 20]
    assert doc.write_calls == [(8, "第1行\r"), (12, "第2行\r"), (16, "第3行\r")]


def test_reposition_insert_range_if_locked_does_not_rewind_to_insert_start():
    class _ProbeRange:
        def __init__(self, start: int):
            self.Start = start
            self.End = start

    class _Doc:
        def Range(self, start, end):
            return _ProbeRange(start)

    class _InsertRange:
        def __init__(self, pos: int):
            self.Start = pos
            self.End = pos

        def SetRange(self, start, end):
            self.Start = start
            self.End = end

    collapsed_positions = []

    def fake_set_collapsed_range(target_range, position):
        collapsed_positions.append(position)
        target_range.SetRange(position, position)

    def fake_find_next_editable_pos_bounded(
        doc,
        *,
        start_pos,
        bound_start,
        get_bound_end,
        raise_on_missing=False,
    ):
        if start_pos == 8:
            return 8
        return None

    namespace = _load_functions(
        "_reposition_insert_range_if_locked",
        extra_globals={
            "_is_range_locked": lambda doc, rng: True,
            "_find_next_editable_pos_bounded": fake_find_next_editable_pos_bounded,
            "_find_next_editable_pos_on_page_bounded": (
                lambda doc, start_pos, anchor_page, get_bound_end: None
            ),
            "_set_collapsed_range": fake_set_collapsed_range,
        },
    )

    insert_range = _InsertRange(20)

    result = namespace["_reposition_insert_range_if_locked"](
        _Doc(),
        insert_range,
        insert_start=8,
        anchor_page=3,
        get_bound_end=lambda: 20,
        log_parts=[],
    )

    assert result is False
    assert insert_range.Start == 20
    assert insert_range.End == 20
    assert collapsed_positions == []
