from __future__ import annotations

from pathlib import Path

from backend.nodes.skills_nodes import rewrite_nodes


class _FakeDoc:
    def Range(self, start: int, end: int) -> tuple[int, int]:
        return (start, end)


class _FakeInspector:
    def analyze_document(self, range_start: int, range_end: int) -> dict:
        return {"range_start": range_start, "range_end": range_end}


def test_resolve_uploaded_rewrite_target_enables_verbose_style_flags(tmp_path: Path) -> None:
    doc_path = tmp_path / "origin.docx"
    doc_path.write_bytes(b"origin")

    result = rewrite_nodes.resolve_rewrite_target(
        {
            "conversation_id": "conv-1",
            "rewrite_user_prompt": "请修改正文",
            "rewrite_source": "uploaded_file",
            "source_document_path": str(doc_path),
        },
        config=None,
    )

    assert result["verbose_style_progress_logs"] is True
    assert result["suppress_comment_progress_logs"] is True
    assert result["prepared_doc_path"].endswith(".docx")
    assert result["prepared_doc_path"] != str(doc_path)


def test_extract_uploaded_rewrite_context_injects_inline_style_fragments(monkeypatch, tmp_path: Path) -> None:
    doc_path = tmp_path / "rewrite-source.docx"
    doc_path.write_bytes(b"docx")
    progress_messages: list[str] = []

    monkeypatch.setattr(
        rewrite_nodes,
        "create_word_application",
        lambda **kwargs: ("word", False),
    )
    monkeypatch.setattr(
        rewrite_nodes,
        "open_document_with_retry",
        lambda **kwargs: _FakeDoc(),
    )
    monkeypatch.setattr(rewrite_nodes, "unprotect_document", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        rewrite_nodes,
        "find_anchor_range",
        lambda **kwargs: ({"start": 10, "end": 20}, {"start": 90, "end": 100}),
    )
    monkeypatch.setattr(
        rewrite_nodes,
        "resolve_anchor_content_range",
        lambda **kwargs: {
            "range_start": 20,
            "range_end": 80,
            "start_page": 2,
            "end_page": 4,
        },
    )
    monkeypatch.setattr(rewrite_nodes, "extract_content_with_tables", lambda rng: "原始正文")
    monkeypatch.setattr(rewrite_nodes, "WordDocumentInspector", lambda **kwargs: _FakeInspector())
    monkeypatch.setattr(
        rewrite_nodes,
        "result_to_polished_comments",
        lambda result: [{"reference_text": "原始正文", "comment_text": "保留批注"}],
    )
    monkeypatch.setattr(
        rewrite_nodes,
        "extract_inline_style_fragments",
        lambda **kwargs: [
            {
                "source_text": "红字",
                "container_type": "paragraph",
                "container_locator": {"paragraph_index": 1},
                "style_flags": {
                    "strikethrough": False,
                    "underline": False,
                    "bold": True,
                    "italic": False,
                },
                "source_span_kind": "partial_span",
            }
        ],
    )
    monkeypatch.setattr(rewrite_nodes, "close_word_application", lambda **kwargs: None)
    monkeypatch.setattr(
        rewrite_nodes.progress_log,
        "info",
        lambda message, *args: progress_messages.append(
            message % args if args else str(message)
        ),
    )

    result = rewrite_nodes.extract_rewrite_context(
        {
            "prepared_doc_path": str(doc_path),
            "tender_type": "xjcg",
            "insertion_before_text": "第三章 采购需求",
            "insertion_after_text": "第四章 响应文件有关格式",
            "verbose_style_progress_logs": True,
            "suppress_comment_progress_logs": True,
        },
        config=None,
    )

    assert result["source_section_text"] == "原始正文"
    assert result["polished_comments"] == [
        {"reference_text": "原始正文", "comment_text": "保留批注"}
    ]
    assert result["inline_style_fragments"] == [
        {
            "source_text": "红字",
            "container_type": "paragraph",
            "container_locator": {"paragraph_index": 1},
            "style_flags": {
                "strikethrough": False,
                "underline": False,
                "bold": True,
                "italic": False,
            },
            "source_span_kind": "partial_span",
        }
    ]
    assert result["verbose_style_progress_logs"] is True
    assert result["suppress_comment_progress_logs"] is True
    assert any("已提取重写正文、批注和样式: comments=1, styles=1, pages=2-4" in msg for msg in progress_messages)
    assert any(
        "样式提取[1/1]" in msg and "样式=加粗" in msg and '源文本="红字"' in msg
        for msg in progress_messages
    )
