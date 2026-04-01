import ast
import re
from pathlib import Path


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


def test_build_manual_test_output_path_appends_suffix():
    source_doc_path = Path("D:/tmp/sample.doc")
    namespace = _load_functions("_build_manual_test_output_path")

    output_path = namespace["_build_manual_test_output_path"](source_doc_path)

    assert output_path.name == "sample-gjgk-update-test.doc"
