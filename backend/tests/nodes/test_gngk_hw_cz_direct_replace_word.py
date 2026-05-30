from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from backend.config.tender_config import CONTENT_UPDATE_MODE_DIRECT_REPLACE

common_update_module = importlib.import_module(
    "backend.nodes.common_word_nodes.update_word"
)
delete_module = importlib.import_module(
    "backend.nodes.gngk_word_nodes.gngk_hw_cz_delete_tender_param"
)
update_module = importlib.import_module(
    "backend.nodes.gngk_word_nodes.gngk_hw_cz_update_word"
)


class _FakeRange:
    def __init__(self, doc: "_FakeDoc", start: int, end: int) -> None:
        self.doc = doc
        self.Start = int(start)
        self.End = int(end)

    def SetRange(self, start: int, end: int) -> None:
        self.Start = int(start)
        self.End = int(end)

    def Collapse(self, *_args) -> None:
        self.End = self.Start

    def Delete(self) -> None:
        self.doc.deleted_ranges.append((int(self.Start), int(self.End)))

    def Information(self, *_args) -> int:
        return self.doc.page_for_position(int(self.Start), int(self.End))


class _FakeDoc:
    def __init__(self) -> None:
        self.Content = SimpleNamespace(End=200)
        self.deleted_ranges: list[tuple[int, int]] = []
        self.saved = False

    def Range(self, start: int, end: int) -> _FakeRange:
        return _FakeRange(self, start, end)

    @staticmethod
    def page_for_position(start: int, end: int) -> int:
        del end
        return 1 if int(start) < 100 else 2


class _FakeWord:
    Selection = object()


def _build_doc_path(tmp_path: Path) -> Path:
    doc_path = tmp_path / "prepared.docx"
    doc_path.write_bytes(b"docx")
    return doc_path


def _style_result() -> dict[str, Any]:
    return {
        "extracted": 1,
        "attempted": 1,
        "applied": 1,
        "skipped": 0,
        "failed": 0,
        "issues": [],
        "applied_by_style": {"bold": 1},
        "skipped_by_reason": {},
    }


def _patch_hw_cz_update_runtime(
    monkeypatch,
    fake_doc: _FakeDoc,
    *,
    inserted_items: list[tuple[str, Any]] | None = None,
    cleanup_calls: list[tuple[int, int]] | None = None,
    comment_result: dict[str, Any] | None = None,
    size_calls: list[str] | None = None,
    mode_calls: list[str] | None = None,
    range_calls: list[str] | None = None,
) -> list[dict[str, Any]]:
    style_calls: list[dict[str, Any]] = []

    monkeypatch.setattr(
        update_module,
        "create_word_application",
        lambda **_kwargs: (_FakeWord(), False),
    )
    monkeypatch.setattr(
        update_module,
        "open_document_with_retry",
        lambda **_kwargs: fake_doc,
    )
    monkeypatch.setattr(
        update_module,
        "unprotect_document",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        update_module,
        "save_document_with_retry",
        lambda *_args, **_kwargs: setattr(fake_doc, "saved", True),
    )
    monkeypatch.setattr(
        update_module,
        "close_word_application",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        update_module,
        "get_anchor_target_sizes",
        lambda tender_type: (
            size_calls.append(str(tender_type)) if size_calls is not None else None,
            22.0,
            22.0,
        )[1:],
    )
    monkeypatch.setattr(
        update_module,
        "get_content_update_mode",
        lambda tender_type: (
            mode_calls.append(str(tender_type)) if mode_calls is not None else None,
            CONTENT_UPDATE_MODE_DIRECT_REPLACE,
        )[1],
    )
    monkeypatch.setattr(
        update_module,
        "find_anchor_range",
        lambda *_args, **_kwargs: (
            {"start": 10, "end": 20, "page": 1, "font": "宋体", "size": 22.0},
            {"start": 90, "end": 95, "page": 1, "font": "宋体", "size": 22.0},
        ),
    )
    monkeypatch.setattr(
        update_module,
        "resolve_anchor_content_range",
        lambda **kwargs: (
            range_calls.append(str(kwargs["tender_type"]))
            if range_calls is not None
            else None,
            {
                "range_start": 20,
                "range_end": 80,
                "start_page": 1,
                "end_page": 1,
            },
        )[1],
    )
    monkeypatch.setattr(update_module, "_delete_original_content", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        update_module,
        "_trim_leading_layout_controls",
        lambda *args, **kwargs: 20,
    )
    monkeypatch.setattr(
        update_module,
        "_find_first_insert_position_on_anchor_page",
        lambda *args, **kwargs: 20,
    )
    monkeypatch.setattr(
        update_module,
        "_describe_range_state",
        lambda *args, **kwargs: "range-state",
    )

    def _fake_set_collapsed_range(insert_range, position: int) -> None:
        insert_range.SetRange(int(position), int(position))

    monkeypatch.setattr(update_module, "_set_collapsed_range", _fake_set_collapsed_range)
    monkeypatch.setattr(update_module, "_ensure_insert_range", lambda *args, **kwargs: None)

    def _fake_insert_text_line(_doc, insert_range, line: str, **_kwargs) -> None:
        if inserted_items is not None:
            inserted_items.append(("text", line))
        next_pos = int(insert_range.Start) + max(1, len(line) or 1)
        insert_range.SetRange(next_pos, next_pos)

    def _fake_insert_table(_doc, insert_range, rows: list[list[str]], **_kwargs) -> None:
        if inserted_items is not None:
            inserted_items.append(("table", rows))
        next_pos = int(insert_range.Start) + max(1, len(rows))
        insert_range.SetRange(next_pos, next_pos)

    monkeypatch.setattr(update_module, "_insert_text_line", _fake_insert_text_line)
    monkeypatch.setattr(update_module, "_insert_table", _fake_insert_table)
    monkeypatch.setattr(
        update_module,
        "_reposition_insert_range_if_locked",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        update_module,
        "_prime_empty_insert_slot",
        lambda *args, **kwargs: "[[BOOTSTRAP]]",
    )
    monkeypatch.setattr(
        update_module,
        "_remove_marker_paragraphs",
        lambda *args, **kwargs: 0,
    )
    monkeypatch.setattr(
        update_module,
        "cleanup_blank_paragraphs",
        lambda _doc, *, range_start, range_end, **_kwargs: (
            cleanup_calls.append((int(range_start), int(range_end)))
            if cleanup_calls is not None
            else None
        ),
    )

    def _fake_apply_inline_style_fragments(**kwargs):
        style_calls.append(kwargs)
        return _style_result()

    monkeypatch.setattr(
        update_module,
        "apply_inline_style_fragments",
        _fake_apply_inline_style_fragments,
    )
    monkeypatch.setattr(
        update_module,
        "summarize_style_writeback_result",
        lambda _result: "样式摘要",
    )
    monkeypatch.setattr(
        update_module,
        "write_polished_comments",
        lambda **_kwargs: comment_result
        or {"added": 0, "failed": 0, "skipped": 0, "issues": []},
    )

    return style_calls


def test_delete_node_defaults_to_gngk_hw_cz_and_deletes_same_page_content_range(
    monkeypatch,
    tmp_path: Path,
) -> None:
    doc_path = _build_doc_path(tmp_path)
    fake_doc = _FakeDoc()
    size_calls: list[str] = []
    anchor_calls: list[tuple[str, str, float, float, str, str]] = []

    monkeypatch.setattr(
        delete_module,
        "create_word_application",
        lambda **_kwargs: (_FakeWord(), False),
    )
    monkeypatch.setattr(
        delete_module,
        "open_document_with_retry",
        lambda **_kwargs: fake_doc,
    )
    monkeypatch.setattr(
        delete_module,
        "save_document_with_retry",
        lambda *_args, **_kwargs: setattr(fake_doc, "saved", True),
    )
    monkeypatch.setattr(
        delete_module,
        "close_word_application",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        delete_module,
        "unprotect_document",
        lambda *_args, **_kwargs: False,
    )

    def _fake_get_anchor_target_sizes(tender_type: str) -> tuple[float, float]:
        size_calls.append(str(tender_type))
        return 22.0, 22.0

    def _fake_find_anchor_range(**kwargs):
        anchor_calls.append(
            (
                str(kwargs["before_text"]),
                str(kwargs["after_text"]),
                float(kwargs["before_size"]),
                float(kwargs["after_size"]),
                str(kwargs["prefer_before"]),
                str(kwargs["prefer_after"]),
            )
        )
        return (
            {"start": 10, "end": 20, "page": 1, "used_text": kwargs["before_text"]},
            {"start": 80, "end": 90, "page": 1, "used_text": kwargs["after_text"]},
        )

    monkeypatch.setattr(
        delete_module,
        "get_anchor_target_sizes",
        _fake_get_anchor_target_sizes,
    )
    monkeypatch.setattr(
        delete_module,
        "find_anchor_range",
        _fake_find_anchor_range,
    )

    result = delete_module.gngk_hw_cz_delete_tender_param(
        {"prepared_doc_path": str(doc_path)},
        config=None,
    )

    assert dict(result) == {"prepared_doc_path": str(doc_path)}
    assert size_calls == ["gngk_hw_cz"]
    assert anchor_calls == [
        ("第四章  招标需求", "第五章  评标方法与程序", 22.0, 22.0, "last", "first")
    ]
    assert fake_doc.deleted_ranges == [(20, 80)]
    assert fake_doc.saved is True


def test_delete_node_routes_through_lock_aware_deletion(
    monkeypatch,
    tmp_path: Path,
) -> None:
    doc_path = _build_doc_path(tmp_path)
    fake_doc = _FakeDoc()
    captured: dict[str, Any] = {}

    monkeypatch.setattr(
        delete_module,
        "create_word_application",
        lambda **_kwargs: (_FakeWord(), False),
    )
    monkeypatch.setattr(
        delete_module,
        "open_document_with_retry",
        lambda **_kwargs: fake_doc,
    )
    monkeypatch.setattr(
        delete_module,
        "save_document_with_retry",
        lambda *_args, **_kwargs: setattr(fake_doc, "saved", True),
    )
    monkeypatch.setattr(
        delete_module,
        "close_word_application",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        delete_module,
        "unprotect_document",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        delete_module,
        "get_anchor_target_sizes",
        lambda _tender_type: (22.0, 22.0),
    )
    monkeypatch.setattr(
        delete_module,
        "find_anchor_range",
        lambda **_kwargs: (
            {"start": 10, "end": 20, "page": 1},
            {"start": 80, "end": 90, "page": 1},
        ),
    )

    def _fake_delete_content_between_anchors(doc, **kwargs):
        captured["doc"] = doc
        captured["kwargs"] = kwargs
        kwargs["log_parts"].append("锁感知删除测试日志")
        return {
            "deleted_tables": 0,
            "skipped_tables": 0,
            "deleted_paragraphs": 1,
            "skipped_paragraphs": 1,
            "used_fallback_delete": False,
        }

    monkeypatch.setattr(
        delete_module,
        "_delete_content_between_anchors",
        _fake_delete_content_between_anchors,
    )

    delete_module.gngk_hw_cz_delete_tender_param(
        {
            "prepared_doc_path": str(doc_path),
            "insertion_before_text": "第四章 招标需求",
            "insertion_after_text": "第五章 评标方法与程序",
        },
        config=None,
    )

    assert captured["doc"] is fake_doc
    assert captured["kwargs"]["range_start"] == 20
    assert captured["kwargs"]["range_end"] == 80
    assert captured["kwargs"]["after_anchor_start"] == 80
    assert fake_doc.deleted_ranges == []
    assert fake_doc.saved is True


def test_delete_node_uses_state_tender_type_instead_of_hardcoded_gjgk(
    monkeypatch,
    tmp_path: Path,
) -> None:
    doc_path = _build_doc_path(tmp_path)
    fake_doc = _FakeDoc()
    captured: dict[str, str] = {}

    monkeypatch.setattr(
        delete_module,
        "create_word_application",
        lambda **_kwargs: (_FakeWord(), False),
    )
    monkeypatch.setattr(
        delete_module,
        "open_document_with_retry",
        lambda **_kwargs: fake_doc,
    )
    monkeypatch.setattr(
        delete_module,
        "save_document_with_retry",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        delete_module,
        "close_word_application",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        delete_module,
        "unprotect_document",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        delete_module,
        "find_anchor_range",
        lambda **_kwargs: (
            {"start": 10, "end": 20, "page": 1},
            {"start": 80, "end": 90, "page": 1},
        ),
    )

    def _fake_get_anchor_target_sizes(tender_type: str) -> tuple[float, float]:
        captured["anchor_tender_type"] = str(tender_type)
        return 22.0, 22.0

    def _fake_get_content_update_mode(tender_type: str) -> str:
        captured["mode_tender_type"] = str(tender_type)
        return CONTENT_UPDATE_MODE_DIRECT_REPLACE

    def _fake_resolve_anchor_content_range(**kwargs):
        captured["range_tender_type"] = str(kwargs["tender_type"])
        return {
            "range_start": 20,
            "range_end": 80,
            "start_page": 1,
            "end_page": 1,
        }

    monkeypatch.setattr(
        delete_module,
        "get_anchor_target_sizes",
        _fake_get_anchor_target_sizes,
    )
    monkeypatch.setattr(
        delete_module,
        "get_content_update_mode",
        _fake_get_content_update_mode,
    )
    monkeypatch.setattr(
        delete_module,
        "resolve_anchor_content_range",
        _fake_resolve_anchor_content_range,
    )

    delete_module.gngk_hw_cz_delete_tender_param(
        {
            "prepared_doc_path": str(doc_path),
            "tender_type": "custom_direct_replace",
            "insertion_before_text": "第四章 招标需求",
            "insertion_after_text": "第五章 评标方法与程序",
        },
        config=None,
    )

    assert captured == {
        "anchor_tender_type": "custom_direct_replace",
        "mode_tender_type": "custom_direct_replace",
        "range_tender_type": "custom_direct_replace",
    }


def test_delete_node_rejects_non_direct_replace_mode(
    monkeypatch,
    tmp_path: Path,
) -> None:
    doc_path = _build_doc_path(tmp_path)

    monkeypatch.setattr(
        delete_module,
        "get_anchor_target_sizes",
        lambda _tender_type: (22.0, 22.0),
    )
    monkeypatch.setattr(
        delete_module,
        "get_content_update_mode",
        lambda _tender_type: "protected_fields",
    )

    with pytest.raises(ValueError, match="仅支持 direct_replace 模式"):
        delete_module.gngk_hw_cz_delete_tender_param(
            {
                "prepared_doc_path": str(doc_path),
                "tender_type": "gngk_hw_zc",
                "insertion_before_text": "第三章 招标内容及要求",
                "insertion_after_text": "第四章 投标文件有关格式",
            },
            config=None,
        )


def test_update_node_inserts_text_blank_lines_and_markdown_tables_without_protected_field_split(
    monkeypatch,
    tmp_path: Path,
) -> None:
    doc_path = _build_doc_path(tmp_path)
    fake_doc = _FakeDoc()
    inserted_items: list[tuple[str, Any]] = []
    cleanup_calls: list[tuple[int, int]] = []
    style_calls = _patch_hw_cz_update_runtime(
        monkeypatch,
        fake_doc,
        inserted_items=inserted_items,
        cleanup_calls=cleanup_calls,
        comment_result={"added": 1, "failed": 0, "skipped": 0, "issues": []},
    )

    monkeypatch.setattr(
        common_update_module,
        "split_polished_text_into_blocks",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("common protected-field split should not be used")
        ),
    )

    result = update_module.gngk_hw_cz_update_word(
        {
            "prepared_doc_path": str(doc_path),
            "polished_text": "第一段\n\n| 列1 | 列2 |\n| --- | --- |\n| A | B |",
            "inline_style_fragments": [{"source_text": "模板样式"}],
            "style_writeback_mode": "bold_only",
            "polished_comments": [{"reference_text": "条款A", "comment_text": "批注A"}],
            "generated_comment_count": 1,
        },
        config=None,
    )

    assert inserted_items == [
        ("text", "第一段\n"),
        ("table", [["列1", "列2"], ["A", "B"]]),
    ]
    assert cleanup_calls == []
    assert len(style_calls) == 1
    assert style_calls[0]["bound_start"] == 20
    assert style_calls[0]["bound_end"] == 90
    assert style_calls[0]["step_label"] == "步骤6"
    assert result["style_writeback_result"] == _style_result()
    assert result["style_writeback_summary"] == "样式摘要"
    assert result["comment_writeback_summary"] == "AI批注写入: 生成=1, 成功=1, 失败=0, 跳过=0"
    assert result["comment_writeback_added"] == 1
    assert result["comment_writeback_failed"] == 0
    assert result["comment_writeback_skipped"] == 0
    assert fake_doc.saved is True


def test_merge_adjacent_text_items_keeps_tables_as_boundaries() -> None:
    merged = update_module._merge_adjacent_text_items(
        [
            {"type": "text", "line": "第一段"},
            {"type": "text", "line": ""},
            {"type": "text", "line": "第二段"},
            {"type": "table", "rows": [["A"]]},
            {"type": "text", "line": "第三段"},
        ]
    )

    assert merged == [
        {"type": "text", "line": "第一段\n\n第二段"},
        {"type": "table", "rows": [["A"]]},
        {"type": "text", "line": "第三段"},
    ]


def test_update_node_uses_state_tender_type_for_anchor_mode_and_style_bounds(
    monkeypatch,
    tmp_path: Path,
) -> None:
    doc_path = _build_doc_path(tmp_path)
    fake_doc = _FakeDoc()
    size_calls: list[str] = []
    mode_calls: list[str] = []
    range_calls: list[str] = []
    style_calls = _patch_hw_cz_update_runtime(
        monkeypatch,
        fake_doc,
        size_calls=size_calls,
        mode_calls=mode_calls,
        range_calls=range_calls,
    )

    monkeypatch.setattr(
        update_module,
        "_build_insert_items",
        lambda _text: [{"type": "text", "line": "财政货物正文"}],
    )

    result = update_module.gngk_hw_cz_update_word(
        {
            "prepared_doc_path": str(doc_path),
            "polished_text": "不会走 common split",
            "tender_type": "custom_direct_replace",
            "insertion_before_text": "第四章 招标需求",
            "insertion_after_text": "第五章 评标方法与程序",
            "inline_style_fragments": [{"source_text": "模板样式"}],
        },
        config=None,
    )

    assert size_calls == ["custom_direct_replace"]
    assert mode_calls == ["custom_direct_replace"]
    assert range_calls == ["custom_direct_replace"]
    assert len(style_calls) == 1
    assert style_calls[0]["bound_start"] == 20
    assert style_calls[0]["bound_end"] == 90
    assert result["style_writeback_summary"] == "样式摘要"


def test_update_node_warns_when_comments_generated_but_none_written(
    monkeypatch,
    tmp_path: Path,
) -> None:
    doc_path = _build_doc_path(tmp_path)
    fake_doc = _FakeDoc()
    _patch_hw_cz_update_runtime(
        monkeypatch,
        fake_doc,
        comment_result={
            "added": 0,
            "failed": 2,
            "skipped": 0,
            "issues": [
                {"reference_text": "条款A", "reason": "reference_text_not_found"},
            ],
        },
    )

    progress_warnings: list[str] = []
    progress_errors: list[str] = []
    monkeypatch.setattr(
        update_module.progress_log,
        "warning",
        lambda message, *args: progress_warnings.append(
            message % args if args else str(message)
        ),
    )
    monkeypatch.setattr(
        update_module.progress_log,
        "error",
        lambda message, *args: progress_errors.append(message % args if args else str(message)),
    )

    result = update_module.gngk_hw_cz_update_word(
        {
            "prepared_doc_path": str(doc_path),
            "polished_text": "新的正文",
            "polished_comments": [{"reference_text": "条款A", "comment_text": "批注A"}],
            "generated_comment_count": 2,
        },
        config=None,
    )

    assert result["comment_writeback_result"] == {
        "summary": "AI批注写入: 生成=2, 成功=0, 失败=2, 跳过=0",
        "generated": 2,
        "added": 0,
        "failed": 2,
        "skipped": 0,
        "warning": True,
    }
    assert progress_warnings == ["AI批注写入: 生成=2, 成功=0, 失败=2, 跳过=0"]
    assert progress_errors == []
