from __future__ import annotations

import importlib
from pathlib import Path

import pytest

prepare_module = importlib.import_module(
    "backend.nodes.common_word_nodes.prepare_template"
)


class _FakeDoc:
    def Close(self, SaveChanges=False) -> None:  # noqa: N803 - Word COM naming
        self.save_changes = SaveChanges


class _FakeDocuments:
    def __init__(self, opened_files: list[str]) -> None:
        self.opened_files = opened_files

    def Open(self, **kwargs) -> _FakeDoc:  # noqa: N802 - Word COM naming
        self.opened_files.append(kwargs["FileName"])
        return _FakeDoc()


class _FakeWord:
    def __init__(self, opened_files: list[str]) -> None:
        self.Documents = _FakeDocuments(opened_files)


def test_prepare_template_requires_template_path() -> None:
    with pytest.raises(ValueError) as exc_info:
        prepare_module.prepare_template(
            {
                "clean_draft_path": "D:/legacy-clean.docx",
                "origin_tender_path": "D:/legacy-review.docx",
            },
            config=None,
        )

    message = str(exc_info.value)
    assert "template_path" in message
    assert "clean_draft" not in message
    assert "origin_tender" not in message
    assert "清洁稿" not in message
    assert "送审稿" not in message


def test_prepare_template_copies_template_path_and_ignores_legacy_slots(
    monkeypatch,
    tmp_path: Path,
) -> None:
    template_path = tmp_path / "template.docx"
    template_path.write_bytes(b"template bytes")
    opened_files: list[str] = []

    monkeypatch.setattr(
        prepare_module,
        "create_word_application",
        lambda **_kwargs: (_FakeWord(opened_files), False),
    )
    monkeypatch.setattr(
        prepare_module,
        "close_word_application",
        lambda **_kwargs: None,
    )

    result = prepare_module.prepare_template(
        {
            "template_path": str(template_path),
            "clean_draft_path": str(tmp_path / "legacy-clean.docx"),
            "origin_tender_path": str(tmp_path / "legacy-review.docx"),
            "project_number": "PN001",
            "project_name": "DemoProject",
        },
        config=None,
    )

    prepared_path = Path(result["prepared_doc_path"])
    assert prepared_path.exists()
    assert prepared_path.parent == tmp_path
    assert prepared_path.name.startswith("PN001-DemoProject-初稿-")
    assert prepared_path.suffix == ".docx"
    assert prepared_path.read_bytes() == b"template bytes"
    assert opened_files == [str(prepared_path)]
