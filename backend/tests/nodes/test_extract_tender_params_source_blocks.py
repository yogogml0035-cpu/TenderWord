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


def _build_state(doc_path: Path, **overrides: Any) -> dict[str, Any]:
    state: dict[str, Any] = {
        "template_path": str(doc_path),
        "tender_type": "xjcg",
        "insertion_before_text": "第三章 采购需求",
        "insertion_after_text": "第四章 响应文件有关格式",
    }
    state.update(overrides)
    return state


def _patch_structured_extract(
    monkeypatch,
    *,
    outputs_by_stem: dict[str, tuple[str, list[dict[str, Any]]]],
) -> list[tuple[str, str]]:
    """按文件名分发结构化抽取结果，并记录 (table_id_prefix, stem) 调用顺序。"""
    calls: list[tuple[str, str]] = []

    def _fake(file_path_obj: Path, *, file_index: int):
        stem = file_path_obj.stem
        calls.append((f"TP{file_index}_", stem))
        text, models = outputs_by_stem.get(stem, (f"技术参数:{stem}", []))
        return text, models

    monkeypatch.setattr(
        extract_module,
        "_extract_structured_tender_param_file",
        _fake,
    )
    return calls


def test_extract_tender_params_builds_ordered_source_blocks_from_tender_param_files(
    monkeypatch, tmp_path: Path
) -> None:
    """多份技术参数文件按顺序拼成“第一份/第二份...”来源块，文件名用上传原名。"""
    doc_path = tmp_path / "template.docx"
    doc_path.write_bytes(b"docx")
    param_one = tmp_path / "uuid-1.docx"
    param_two = tmp_path / "uuid-2.docx"
    param_one.write_bytes(b"param-one")
    param_two.write_bytes(b"param-two")

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
    calls = _patch_structured_extract(
        monkeypatch,
        outputs_by_stem={
            "uuid-1": ("第一包正文\n[[TABLE:TP1_1]]", []),
            "uuid-2": ("第二包正文", []),
        },
    )

    result = extract_module.extract_tender_params(
        _build_state(
            doc_path,
            tender_param_files=[
                {"file_path": str(param_one), "original_name": "第一包技术参数.docx"},
                {"file_path": str(param_two), "original_name": "第二包技术参数.docx"},
            ],
        ),
        config=None,
    )

    tender_params = result["tender_params"]
    # 按界面顺序拼成两块；中文数字序号；文件名取上传原名。
    assert "第一份技术参数文件名称为：第一包技术参数.docx" in tender_params
    assert "第二份技术参数文件名称为：第二包技术参数.docx" in tender_params
    assert tender_params.index("第一份") < tender_params.index("第二份")
    # 内容前后顺序与界面一致。
    assert tender_params.index("第一包正文") < tender_params.index("第二包正文")
    # [[TABLE:...]] 占位符保持不变。
    assert "[[TABLE:TP1_1]]" in tender_params
    # 结构化抽取按 file_index 分配 table_id 前缀。
    assert calls == [("TP1_", "uuid-1"), ("TP2_", "uuid-2")]


def test_extract_tender_params_keeps_source_block_when_content_empty(
    monkeypatch, tmp_path: Path
) -> None:
    """抽取内容为空的文件不被跳过，`内容：` 后为空但来源块仍在。"""
    doc_path = tmp_path / "template.docx"
    doc_path.write_bytes(b"docx")
    empty_param = tmp_path / "empty.docx"
    empty_param.write_bytes(b"empty")
    nonempty_param = tmp_path / "content.docx"
    nonempty_param.write_bytes(b"content")

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
    _patch_structured_extract(
        monkeypatch,
        outputs_by_stem={
            "empty": ("", []),
            "content": ("真实正文", []),
        },
    )

    result = extract_module.extract_tender_params(
        _build_state(
            doc_path,
            tender_param_files=[
                {"file_path": str(empty_param), "original_name": "空文件.docx"},
                {"file_path": str(nonempty_param), "original_name": "有内容.docx"},
            ],
        ),
        config=None,
    )

    tender_params = result["tender_params"]
    assert "第一份技术参数文件名称为：空文件.docx" in tender_params
    assert "第二份技术参数文件名称为：有内容.docx" in tender_params
    # 空文件块仍在，`内容：` 后为空（紧跟下一块或行尾）。
    assert "第一份技术参数文件名称为：空文件.docx\n内容：\n" in tender_params
    assert "真实正文" in tender_params


def test_extract_tender_params_falls_back_to_filename_when_original_name_missing(
    monkeypatch, tmp_path: Path
) -> None:
    """缺 original_name 时用文件本身名称作为来源线索。"""
    doc_path = tmp_path / "template.docx"
    doc_path.write_bytes(b"docx")
    param = tmp_path / "无名称.docx"
    param.write_bytes(b"param")

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
    _patch_structured_extract(monkeypatch, outputs_by_stem={})

    result = extract_module.extract_tender_params(
        _build_state(
            doc_path,
            tender_param_files=[{"file_path": str(param)}],
        ),
        config=None,
    )

    tender_params = result["tender_params"]
    assert "第一份技术参数文件名称为：无名称.docx" in tender_params


def test_extract_tender_params_prefers_tender_param_files_over_paths(
    monkeypatch, tmp_path: Path
) -> None:
    """同时存在 tender_param_files 和 tender_param_paths 时，前者优先。"""
    doc_path = tmp_path / "template.docx"
    doc_path.write_bytes(b"docx")
    file_param = tmp_path / "from-files.docx"
    path_param = tmp_path / "from-paths.docx"
    file_param.write_bytes(b"files")
    path_param.write_bytes(b"paths")

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
    _patch_structured_extract(monkeypatch, outputs_by_stem={})

    result = extract_module.extract_tender_params(
        _build_state(
            doc_path,
            tender_param_files=[{"file_path": str(file_param), "original_name": "对象来源.docx"}],
            tender_param_paths=[str(path_param)],
        ),
        config=None,
    )

    tender_params = result["tender_params"]
    assert "第一份技术参数文件名称为：对象来源.docx" in tender_params
    # 不应抽取 paths 来源里的文件。
    assert "from-paths" not in tender_params
    assert "from-files" in tender_params


def test_extract_tender_params_legacy_paths_still_get_source_blocks(
    monkeypatch, tmp_path: Path
) -> None:
    """旧 tender_param_paths（纯路径）也加来源标记，文件名取后端保存文件名。"""
    doc_path = tmp_path / "template.docx"
    doc_path.write_bytes(b"docx")
    param = tmp_path / "legacy.docx"
    param.write_bytes(b"param")

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
    _patch_structured_extract(monkeypatch, outputs_by_stem={})

    result = extract_module.extract_tender_params(
        _build_state(doc_path, tender_param_paths=[str(param)]),
        config=None,
    )

    tender_params = result["tender_params"]
    assert "第一份技术参数文件名称为：legacy.docx" in tender_params
