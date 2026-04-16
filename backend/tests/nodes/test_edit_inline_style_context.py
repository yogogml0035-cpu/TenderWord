from __future__ import annotations

from pathlib import Path

from backend.nodes.skills_nodes import edit_nodes


class _FakeDoc:
    def Range(self, start: int, end: int) -> tuple[int, int]:
        return (start, end)


class _FakeInspector:
    def analyze_document(self, range_start: int, range_end: int) -> dict:
        return {"range_start": range_start, "range_end": range_end}


def test_extract_edit_context_injects_inline_style_fragments(monkeypatch, tmp_path: Path) -> None:
    doc_path = tmp_path / "edit-source.docx"
    doc_path.write_bytes(b"docx")

    monkeypatch.setattr(
        edit_nodes,
        "create_word_application",
        lambda **kwargs: ("word", False),
    )
    monkeypatch.setattr(
        edit_nodes,
        "open_document_with_retry",
        lambda **kwargs: _FakeDoc(),
    )
    monkeypatch.setattr(edit_nodes, "unprotect_document", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        edit_nodes,
        "find_anchor_range",
        lambda **kwargs: ({"start": 10, "end": 20}, {"start": 90, "end": 100}),
    )
    monkeypatch.setattr(
        edit_nodes,
        "resolve_anchor_content_range",
        lambda **kwargs: {
            "range_start": 20,
            "range_end": 80,
            "start_page": 2,
            "end_page": 4,
        },
    )
    monkeypatch.setattr(edit_nodes, "extract_content_with_tables", lambda rng: "原始正文")
    monkeypatch.setattr(edit_nodes, "WordDocumentInspector", lambda **kwargs: _FakeInspector())
    monkeypatch.setattr(
        edit_nodes,
        "result_to_polished_comments",
        lambda result: [{"reference_text": "原始正文", "comment_text": "保留批注"}],
    )
    monkeypatch.setattr(
        edit_nodes,
        "extract_inline_style_fragments",
        lambda **kwargs: [{"source_text": "红字", "container_type": "paragraph"}],
    )
    monkeypatch.setattr(edit_nodes, "close_word_application", lambda **kwargs: None)

    result = edit_nodes.extract_edit_context(
        {
            "prepared_doc_path": str(doc_path),
            "tender_type": "xjcg",
            "insertion_before_text": "第三章 采购需求",
            "insertion_after_text": "第四章 响应文件有关格式",
        },
        config=None,
    )

    assert result["origin_tender_params"] == "原始正文"
    assert result["polished_comments"] == [
        {"reference_text": "原始正文", "comment_text": "保留批注"}
    ]
    assert result["inline_style_fragments"] == [
        {"source_text": "红字", "container_type": "paragraph"}
    ]
