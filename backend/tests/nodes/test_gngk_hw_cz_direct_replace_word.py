from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.config.tender_config import CONTENT_UPDATE_MODE_DIRECT_REPLACE

delete_module = importlib.import_module(
    "backend.nodes.gngk_word_nodes.gngk_hw_cz_delete_tender_param"
)


class _FakeRange:
    def __init__(self, doc: "_FakeDoc", start: int, end: int) -> None:
        self.doc = doc
        self.Start = int(start)
        self.End = int(end)

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
