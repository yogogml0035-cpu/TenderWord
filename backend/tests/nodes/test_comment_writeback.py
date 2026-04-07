from __future__ import annotations

import importlib
from types import SimpleNamespace

from backend.nodes.common_word_nodes.comment_writeback import write_polished_comments

gjgk_update_word_module = importlib.import_module(
    "backend.nodes.gjgk_word_nodes.gjgk_update_word"
)


class _FakeFind:
    def __init__(self, target_range: "_FakeRange") -> None:
        self._target_range = target_range
        self.Text = ""
        self.Forward = True
        self.Wrap = None
        self.MatchCase = False
        self.MatchWholeWord = False

    def ClearFormatting(self) -> None:
        return None

    def Execute(self) -> bool:
        document_text = self._target_range.doc.text[: int(self._target_range.End)]
        index = document_text.find(str(self.Text), int(self._target_range.Start))
        if index < 0:
            return False

        self._target_range.Start = index
        self._target_range.End = index + len(str(self.Text))
        return True


class _FakeRange:
    def __init__(self, doc: "_FakeDocument", start: int, end: int) -> None:
        self.doc = doc
        self.Start = int(start)
        self.End = int(end)
        self.Find = _FakeFind(self)

    @property
    def Duplicate(self) -> "_FakeRange":
        return _FakeRange(self.doc, self.Start, self.End)

    def SetRange(self, start: int, end: int) -> None:
        self.Start = int(start)
        self.End = int(end)

    def Collapse(self, *_args) -> None:
        self.End = self.Start


class _FakeComment:
    def __init__(self, doc: "_FakeDocument", start: int, end: int, text: str) -> None:
        self.Scope = _FakeRange(doc, start, end)
        self.Reference = self.Scope
        self.Range = self.Scope
        self.Text = text


class _FakeCommentsCollection:
    def __init__(self, doc: "_FakeDocument") -> None:
        self._doc = doc
        self._items: list[_FakeComment] = []
        self.fail_ranges: set[tuple[int, int]] = set()

    @property
    def Count(self) -> int:
        return len(self._items)

    def __call__(self, index: int) -> _FakeComment:
        return self._items[index - 1]

    def Add(self, Range, Text: str) -> None:
        match_range = (int(Range.Start), int(Range.End))
        if match_range in self.fail_ranges:
            raise RuntimeError("simulated add failure")
        self._items.append(
            _FakeComment(
                self._doc,
                int(Range.Start),
                int(Range.End),
                str(Text),
            )
        )


class _FakeDocument:
    def __init__(self, text: str) -> None:
        self.text = text
        self.Comments = _FakeCommentsCollection(self)
        self.Content = SimpleNamespace(End=len(text))

    def Range(self, start: int, end: int) -> _FakeRange:
        return _FakeRange(self, start, end)


def test_write_polished_comments_skips_overlapping_ranges_and_uses_later_match() -> None:
    doc = _FakeDocument("Alpha middle Alpha")
    doc.Comments._items.append(_FakeComment(doc, 0, 5, "existing"))
    log_parts: list[str] = []

    result = write_polished_comments(
        doc=doc,
        polished_comments=[
            {"reference_text": "Alpha", "comment_text": "new comment"},
        ],
        bound_start=0,
        bound_end=len(doc.text),
        log_parts=log_parts,
    )

    assert result["added"] == 1
    assert result["failed"] == 0
    assert result["skipped"] == 0
    assert doc.Comments.Count == 2
    assert doc.Comments(2).Range.Start == doc.text.rfind("Alpha")
    assert any("位置已存在批注" in part for part in log_parts)


def test_write_polished_comments_supports_newline_matching_and_partial_failures() -> None:
    doc = _FakeDocument("Line1\rLine2 and Next")
    doc.Comments.fail_ranges.add((0, len("Line1\rLine2")))
    log_parts: list[str] = []

    result = write_polished_comments(
        doc=doc,
        polished_comments=[
            {"reference_text": "Line1\nLine2", "comment_text": "first comment"},
            {"reference_text": "Next", "comment_text": "second comment"},
        ],
        bound_start=0,
        bound_end=len(doc.text),
        log_parts=log_parts,
    )

    assert result["added"] == 1
    assert result["failed"] == 1
    assert result["skipped"] == 0
    assert doc.Comments.Count == 1
    assert doc.Comments(1).Range.Start == doc.text.find("Next")
    assert any("comment_add_failed=1" in part for part in log_parts)


def test_write_polished_comments_reports_empty_and_unmatched_references() -> None:
    doc = _FakeDocument("Only visible text")
    log_parts: list[str] = []

    result = write_polished_comments(
        doc=doc,
        polished_comments=[
            {"reference_text": "", "comment_text": "missing ref"},
            {"reference_text": "Missing", "comment_text": "not found"},
        ],
        bound_start=0,
        bound_end=len(doc.text),
        log_parts=log_parts,
    )

    assert result["added"] == 0
    assert result["failed"] == 1
    assert result["skipped"] == 1
    assert {issue["reason"] for issue in result["issues"]} == {
        "missing_reference_or_comment_text",
        "reference_text_not_found",
    }
    assert any("missing_reference_or_comment_text=1" in part for part in log_parts)
    assert any("reference_text_not_found=1" in part for part in log_parts)


def test_gjgk_update_word_writes_comments_before_save(monkeypatch) -> None:
    events: list[object] = []
    fake_doc = _FakeDocument("x" * 120)

    monkeypatch.setattr(
        gjgk_update_word_module,
        "_build_insert_items",
        lambda _text: [{"type": "text", "line": "新的正文"}],
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "create_word_application",
        lambda **_kwargs: ("fake-word", True),
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "open_document_with_retry",
        lambda **_kwargs: fake_doc,
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "unprotect_document",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "find_anchor_range",
        lambda *_args, **_kwargs: (
            {"start": 10, "end": 15, "page": 1},
            {"start": 40, "end": 45, "page": 1},
        ),
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_resolve_gjgk_content_range",
        lambda **_kwargs: {
            "range_start": 20,
            "range_end": 30,
            "start_page": 1,
            "end_page": 1,
        },
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_delete_original_content",
        lambda *_args, **_kwargs: events.append("delete"),
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_trim_leading_layout_controls",
        lambda *_args, **_kwargs: 20,
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_find_first_insert_position_on_anchor_page",
        lambda *_args, **_kwargs: 20,
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_describe_range_state",
        lambda *_args, **_kwargs: "range-state",
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_set_collapsed_range",
        lambda insert_range, position: insert_range.SetRange(position, position),
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_ensure_insert_range",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_insert_text_line",
        lambda _doc, insert_range, line, **_kwargs: insert_range.SetRange(
            int(insert_range.Start) + len(line),
            int(insert_range.Start) + len(line),
        ),
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_reposition_insert_range_if_locked",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_cleanup_blank_paragraphs",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_visible_log",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "write_polished_comments",
        lambda **kwargs: (
            events.append(
                (
                    "write_comments",
                    tuple(kwargs["polished_comments"]),
                    kwargs["bound_start"],
                    kwargs["bound_end"],
                )
            )
            or {
                "total": 1,
                "attempted": 1,
                "added": 1,
                "failed": 0,
                "skipped": 0,
                "issues": [],
            }
        ),
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "save_document_with_retry",
        lambda _doc, **_kwargs: events.append("save"),
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "close_word_application",
        lambda **_kwargs: None,
    )

    result = gjgk_update_word_module.gjgk_update_word(
        {
            "prepared_doc_path": "fake.docx",
            "polished_text": "新的正文",
            "polished_comments": [
                {"reference_text": "新的正文", "comment_text": "保留旧批注"},
            ],
            "insertion_before_text": "前锚点",
            "insertion_after_text": "后锚点",
        },
        config=None,
    )

    assert events[0] == "delete"
    assert events[1][0] == "write_comments"
    assert events[2] == "save"
    assert "共解析插入项 1 条" in result["insertion_log"]
    assert "文档已保存" in result["insertion_log"]
