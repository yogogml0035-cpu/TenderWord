from __future__ import annotations

from backend.nodes.common_word_nodes.get_replacements_core import (
    ExtractorSpec,
    ReplacementFieldSpec,
    run_get_replacements,
)


class _FakeContent:
    def __init__(self, text: str) -> None:
        self.Text = text


class _FakeHeaderRange:
    def __init__(self, text: str) -> None:
        self.Text = text


class _FakeHeader:
    def __init__(self, text: str) -> None:
        self.Range = _FakeHeaderRange(text)


class _FakeSection:
    def __init__(self, header_text: str) -> None:
        self._header = _FakeHeader(header_text)

    def Headers(self, _index: int) -> _FakeHeader:
        return self._header


class _FakeSections:
    def __init__(self, header_text: str) -> None:
        self._section = _FakeSection(header_text)

    def __call__(self, _index: int) -> _FakeSection:
        return self._section


class _FakeDocument:
    def __init__(self, *, body_text: str, header_text: str) -> None:
        self.Content = _FakeContent(body_text)
        self.Sections = _FakeSections(header_text)


def test_run_get_replacements_prefers_project_name_when_old_value_conflicts(
    monkeypatch,
    tmp_path,
) -> None:
    doc_path = tmp_path / "prepared.docx"
    doc_path.write_text("fake", encoding="utf-8")
    doc = _FakeDocument(body_text="正文", header_text="页眉")

    monkeypatch.setattr(
        "backend.nodes.common_word_nodes.get_replacements_core.create_word_application",
        lambda **_kwargs: (object(), True),
    )
    monkeypatch.setattr(
        "backend.nodes.common_word_nodes.get_replacements_core.open_document_with_retry",
        lambda **_kwargs: doc,
    )
    monkeypatch.setattr(
        "backend.nodes.common_word_nodes.get_replacements_core.unprotect_document",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "backend.nodes.common_word_nodes.get_replacements_core.close_word_application",
        lambda **_kwargs: None,
    )

    state = {
        "prepared_doc_path": str(doc_path),
        "project_content": "医用核磁共振系统维保\t叁年（项目预算：人民币210万元）",
        "project_name": "医用核磁共振系统维保",
    }
    extractors = [
        ExtractorSpec(
            name="project_content_v2",
            enabled_if=lambda _state: True,
            extract_callable=lambda *_args: "内窥镜手术控制系统维保服务",
        ),
        ExtractorSpec(
            name="project_name",
            enabled_if=lambda _state: True,
            extract_callable=lambda *_args: "内窥镜手术控制系统维保服务",
        ),
    ]
    replacement_fields = [
        ReplacementFieldSpec(
            field_name="project_content_v2",
            fallback_fields=["project_content"],
            new_value_formatter=lambda _value: "医用核磁共振系统维保\t叁年",
        ),
        ReplacementFieldSpec(field_name="project_name"),
    ]

    result = run_get_replacements(
        state=state,
        config=None,
        extractors=extractors,
        replacement_fields=replacement_fields,
    )

    assert result["replacements"] == [
        ("内窥镜手术控制系统维保服务", "医用核磁共振系统维保")
    ]
    assert result["replacement_fields"] == ["project_name"]
    assert "保留优先级更高的 'project_name'" in result["replacement_log"]
