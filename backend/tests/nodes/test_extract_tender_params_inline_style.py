from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest

extract_module = importlib.import_module(
    "backend.nodes.common_word_nodes.extract_tender_params"
)


class _FakeTables:
    def __iter__(self):
        return iter(())


class _FakeRange:
    def __init__(self, start: int, end: int) -> None:
        self.Start = int(start)
        self.End = int(end)
        self.Tables = _FakeTables()


class _FakeDoc:
    def __init__(self) -> None:
        self.range_calls: list[tuple[int, int]] = []

    def Range(self, start: int, end: int) -> _FakeRange:
        self.range_calls.append((int(start), int(end)))
        return _FakeRange(start, end)


def _patch_extract_runtime(
    monkeypatch,
    *,
    doc: _FakeDoc,
    style_fragments: list[dict[str, Any]] | Exception,
    progress_messages: list[str],
    progress_warnings: list[str],
    debug_messages: list[str],
) -> dict[str, Any]:
    style_call: dict[str, Any] = {}

    monkeypatch.setattr(
        extract_module,
        "create_word_application",
        lambda **_kwargs: ("word", False),
    )

    def _fake_open_document_with_retry(**kwargs):
        style_call["opened_file_path"] = kwargs["file_path"]
        return doc

    monkeypatch.setattr(
        extract_module,
        "open_document_with_retry",
        _fake_open_document_with_retry,
    )
    monkeypatch.setattr(
        extract_module,
        "unprotect_document",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        extract_module,
        "find_anchor_range",
        lambda **_kwargs: (
            {"start": 10, "end": 20, "page": 2, "font": "宋体", "size": 12},
            {"start": 90, "end": 100, "page": 4, "font": "宋体", "size": 12},
        ),
    )
    monkeypatch.setattr(
        extract_module,
        "resolve_anchor_content_range",
        lambda **_kwargs: {
            "range_start": 20,
            "range_end": 80,
            "start_page": 2,
            "end_page": 4,
        },
    )
    monkeypatch.setattr(
        extract_module,
        "extract_content_with_tables",
        lambda _rng: "原始采购需求",
    )

    def _fake_extract_inline_style_fragments(*args, **kwargs):
        style_call["args"] = args
        style_call["kwargs"] = kwargs
        if isinstance(style_fragments, Exception):
            raise style_fragments
        return style_fragments

    monkeypatch.setattr(
        extract_module,
        "extract_inline_style_fragments",
        _fake_extract_inline_style_fragments,
    )
    monkeypatch.setattr(
        extract_module,
        "close_word_application",
        lambda **_kwargs: None,
    )

    def _fake_extract_text_from_word_file(file_path: str) -> str:
        extracted_paths = style_call.setdefault("tender_param_paths", [])
        extracted_paths.append(file_path)
        return f"技术参数:{Path(file_path).stem}"

    monkeypatch.setattr(
        extract_module,
        "extract_text_from_word_file",
        _fake_extract_text_from_word_file,
    )
    monkeypatch.setattr(
        extract_module.progress_log,
        "info",
        lambda message, *args: progress_messages.append(
            message % args if args else str(message)
        ),
    )
    monkeypatch.setattr(
        extract_module.progress_log,
        "warning",
        lambda message, *args: progress_warnings.append(
            message % args if args else str(message)
        ),
    )
    monkeypatch.setattr(
        extract_module.progress_log,
        "debug",
        lambda message, *args, **_kwargs: debug_messages.append(
            message % args if args else str(message)
        ),
    )
    return style_call


def _build_state(doc_path: Path) -> dict[str, Any]:
    return {
        "template_path": str(doc_path),
        "tender_type": "xjcg",
        "insertion_before_text": "第三章 采购需求",
        "insertion_after_text": "第四章 响应文件有关格式",
    }


def test_extract_tender_params_requires_template_path() -> None:
    with pytest.raises(ValueError) as exc_info:
        extract_module.extract_tender_params(
            {
                "insertion_before_text": "第三章 采购需求",
                "insertion_after_text": "第四章 响应文件有关格式",
            },
            config=None,
        )

    message = str(exc_info.value)
    assert "template_path" in message


def test_extract_tender_params_records_inline_style_fragments(
    monkeypatch,
    tmp_path: Path,
) -> None:
    doc_path = tmp_path / "template.docx"
    doc_path.write_bytes(b"docx")
    fake_doc = _FakeDoc()
    progress_messages: list[str] = []
    progress_warnings: list[str] = []
    debug_messages: list[str] = []
    fragments = [
        {
            "source_text": "加粗标题",
            "container_type": "paragraph",
            "container_locator": {"paragraph_index": 1},
            "style_flags": {"bold": True},
        }
    ]

    style_call = _patch_extract_runtime(
        monkeypatch,
        doc=fake_doc,
        style_fragments=fragments,
        progress_messages=progress_messages,
        progress_warnings=progress_warnings,
        debug_messages=debug_messages,
    )

    result = extract_module.extract_tender_params(_build_state(doc_path), config=None)

    assert result["template_reference_text"] == "原始采购需求"
    assert result["inline_style_fragments"] == fragments
    assert result["start_page"] == 2
    assert result["end_page"] == 4
    assert style_call["args"] == (fake_doc,)
    assert style_call["kwargs"] == {"bound_start": 20, "bound_end": 80}
    assert style_call["opened_file_path"] == str(doc_path)
    assert (20, 80) in fake_doc.range_calls
    assert any(
        "模板样式提取完成，片段 1 个" in message
        for message in progress_messages
    )
    assert not progress_warnings
    assert not debug_messages


def test_extract_tender_params_joins_multiple_tender_param_paths(
    monkeypatch,
    tmp_path: Path,
) -> None:
    doc_path = tmp_path / "template.docx"
    doc_path.write_bytes(b"docx")
    param_one = tmp_path / "param-one.docx"
    param_two = tmp_path / "param-two.docx"
    param_one.write_bytes(b"param-one")
    param_two.write_bytes(b"param-two")
    fake_doc = _FakeDoc()
    progress_messages: list[str] = []
    progress_warnings: list[str] = []
    debug_messages: list[str] = []

    style_call = _patch_extract_runtime(
        monkeypatch,
        doc=fake_doc,
        style_fragments=[],
        progress_messages=progress_messages,
        progress_warnings=progress_warnings,
        debug_messages=debug_messages,
    )
    structured_extract_calls: list[str] = []

    def _fake_extract_content_with_table_models(_range, *, table_id_prefix: str = "TP"):
        structured_extract_calls.append(table_id_prefix)
        return (
            "技术参数:param-one\n[[TABLE:TP1_1]]",
            [
                {
                    "table_id": "TP1_1",
                    "rows": 1,
                    "cols": 2,
                    "cells": [
                        {"row": 1, "col": 1, "row_span": 1, "col_span": 2, "text": "合计"}
                    ],
                }
            ],
        )

    monkeypatch.setattr(
        extract_module,
        "_extract_structured_tender_param_file",
        lambda file_path_obj, *, file_index: _fake_extract_content_with_table_models(
            file_path_obj,
            table_id_prefix=f"TP{file_index}_",
        ),
    )

    result = extract_module.extract_tender_params(
        {
            **_build_state(doc_path),
            "tender_param_paths": [str(param_one)],
        },
        config=None,
    )

    assert result["template_reference_text"] == "原始采购需求"
    assert result["tender_params"] == "技术参数:param-one\n[[TABLE:TP1_1]]"
    assert result["tender_param_table_models"] == [
        {
            "table_id": "TP1_1",
            "rows": 1,
            "cols": 2,
            "cells": [
                {"row": 1, "col": 1, "row_span": 1, "col_span": 2, "text": "合计"}
            ],
        }
    ]
    assert style_call["opened_file_path"] == str(doc_path)
    assert structured_extract_calls == ["TP1_"]


def test_extract_tender_params_keeps_table_context_without_markdown_projection(
    monkeypatch,
    tmp_path: Path,
) -> None:
    doc_path = tmp_path / "template.docx"
    doc_path.write_bytes(b"docx")
    param_one = tmp_path / "param-one.docx"
    param_one.write_bytes(b"param-one")
    fake_doc = _FakeDoc()
    progress_messages: list[str] = []
    progress_warnings: list[str] = []
    debug_messages: list[str] = []

    _patch_extract_runtime(
        monkeypatch,
        doc=fake_doc,
        style_fragments=[],
        progress_messages=progress_messages,
        progress_warnings=progress_warnings,
        debug_messages=debug_messages,
    )

    monkeypatch.setattr(
        extract_module,
        "_extract_structured_tender_param_file",
        lambda _file_path_obj, *, file_index: (
            "附件三 技术参数表\n楼宇 / 岗位\n[[TABLE:TP1_1]]\n注：按附件执行",
            [
                {
                    "table_id": "TP1_1",
                    "rows": 2,
                    "cols": 2,
                    "cells": [
                        {"row": 1, "col": 1, "row_span": 1, "col_span": 2, "text": "楼宇"},
                        {"row": 2, "col": 1, "row_span": 1, "col_span": 1, "text": "岗位"},
                    ],
                }
            ],
        ),
    )

    result = extract_module.extract_tender_params(
        {
            **_build_state(doc_path),
            "tender_param_paths": [str(param_one)],
        },
        config=None,
    )

    assert "附件三 技术参数表" in result["tender_params"]
    assert "[[TABLE:TP1_1]]" in result["tender_params"]
    assert "注：按附件执行" in result["tender_params"]
    assert "| --- |" not in result["tender_params"]
    assert result["tender_param_table_models"][0]["cells"][0]["col_span"] == 2


def test_extract_tender_params_style_extraction_failure_is_best_effort(
    monkeypatch, tmp_path: Path
) -> None:
    doc_path = tmp_path / "template.docx"
    doc_path.write_bytes(b"docx")
    fake_doc = _FakeDoc()
    progress_messages: list[str] = []
    progress_warnings: list[str] = []
    debug_messages: list[str] = []

    _patch_extract_runtime(
        monkeypatch,
        doc=fake_doc,
        style_fragments=RuntimeError("style extraction exploded"),
        progress_messages=progress_messages,
        progress_warnings=progress_warnings,
        debug_messages=debug_messages,
    )

    result = extract_module.extract_tender_params(_build_state(doc_path), config=None)

    assert result["template_reference_text"] == "原始采购需求"
    assert result["inline_style_fragments"] == []
    assert any("模板样式抽取失败，已跳过" in message for message in progress_warnings)
    assert any("style extraction exploded" in message for message in debug_messages)


def test_extract_tender_params_keeps_generate_progress_outcome_first_when_verbose(
    monkeypatch, tmp_path: Path
) -> None:
    doc_path = tmp_path / "template.docx"
    doc_path.write_bytes(b"docx")
    fake_doc = _FakeDoc()
    progress_messages: list[str] = []
    progress_warnings: list[str] = []
    debug_messages: list[str] = []

    _patch_extract_runtime(
        monkeypatch,
        doc=fake_doc,
        style_fragments=[
            {"source_text": "不应进入用户态日志", "style_flags": {"bold": True}}
        ],
        progress_messages=progress_messages,
        progress_warnings=progress_warnings,
        debug_messages=debug_messages,
    )

    result = extract_module.extract_tender_params(
        {**_build_state(doc_path), "verbose_style_progress_logs": True},
        config=None,
    )

    assert result["inline_style_fragments"]
    assert not any("不应进入用户态日志" in message for message in progress_messages)
    assert not progress_warnings
    assert not debug_messages
