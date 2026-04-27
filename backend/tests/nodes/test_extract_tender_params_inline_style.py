from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

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
    monkeypatch.setattr(
        extract_module,
        "open_document_with_retry",
        lambda **_kwargs: doc,
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
        "clean_draft_path": str(doc_path),
        "tender_type": "xjcg",
        "insertion_before_text": "第三章 采购需求",
        "insertion_after_text": "第四章 响应文件有关格式",
    }


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

    assert result["origin_tender_params"] == "原始采购需求"
    assert result["inline_style_fragments"] == fragments
    assert result["start_page"] == 2
    assert result["end_page"] == 4
    assert style_call["args"] == (fake_doc,)
    assert style_call["kwargs"] == {"bound_start": 20, "bound_end": 80}
    assert (20, 80) in fake_doc.range_calls
    assert any(
        "模板样式提取完成，片段 1 个" in message
        for message in progress_messages
    )
    assert not progress_warnings
    assert not debug_messages


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

    assert result["origin_tender_params"] == "原始采购需求"
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
