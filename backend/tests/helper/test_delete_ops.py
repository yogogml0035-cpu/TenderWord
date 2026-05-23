from __future__ import annotations

import importlib
from types import SimpleNamespace


delete_ops = importlib.import_module("backend.helper.word_helper.delete_ops")


class _FakeCollection:
    def __init__(self, items):
        self._items = list(items)
        self.Count = len(self._items)

    def __call__(self, index: int):
        return self._items[index - 1]

    def __iter__(self):
        return iter(self._items)


class _FakeRange:
    def __init__(self, doc: "_FakeDoc", start: int, end: int) -> None:
        self.doc = doc
        self.Start = int(start)
        self.End = int(end)

    @property
    def Tables(self):
        return _FakeCollection([])

    @property
    def Paragraphs(self):
        return _FakeCollection(self.doc.paragraphs)

    def Delete(self) -> None:
        self.doc.deleted_ranges.append((int(self.Start), int(self.End)))


class _FakeParagraph:
    def __init__(self, doc: "_FakeDoc", start: int, end: int) -> None:
        self.Range = _FakeRange(doc, start, end)


class _FakeDoc:
    def __init__(self) -> None:
        self.Content = SimpleNamespace(End=100)
        self.deleted_ranges: list[tuple[int, int]] = []
        self.paragraphs = [
            _FakeParagraph(self, 20, 30),
            _FakeParagraph(self, 30, 40),
            _FakeParagraph(self, 40, 80),
        ]

    def Range(self, start: int, end: int) -> _FakeRange:
        return _FakeRange(self, start, end)


def test_delete_range_content_preserving_locked_blocks_skips_locked_paragraph(
    monkeypatch,
) -> None:
    doc = _FakeDoc()
    log_parts: list[str] = []

    def fake_is_range_locked(_doc, rng) -> bool:
        return (int(rng.Start), int(rng.End)) in {(20, 80), (30, 40)}

    monkeypatch.setattr(delete_ops, "is_range_locked", fake_is_range_locked)

    stats = delete_ops.delete_range_content_preserving_locked_blocks(
        doc,
        range_start=20,
        get_bound_end=lambda: 80,
        log_parts=log_parts,
    )

    assert stats == {
        "deleted_tables": 0,
        "skipped_tables": 0,
        "deleted_paragraphs": 2,
        "skipped_paragraphs": 1,
        "used_fallback_delete": False,
    }
    assert doc.deleted_ranges == [(40, 80), (20, 30)]
    assert log_parts == [
        "删除原内容: 表格 0 个，段落 2 个，跳过锁定表格 0 个，跳过锁定段落 1 个，整段兜底=False"
    ]


class _FakeTrimRange:
    def __init__(self, doc: "_FakeTrimDoc", start: int, end: int) -> None:
        self.doc = doc
        self.Start = int(start)
        self.End = int(end)
        self.Text = doc.text_by_range.get((int(start), int(end)), "")

    def Delete(self) -> None:
        self.doc.deleted_ranges.append((int(self.Start), int(self.End)))


class _FakeTrimDoc:
    def __init__(self) -> None:
        self.Content = SimpleNamespace(End=30)
        self.text_by_range = {(20, 21): "\r"}
        self.deleted_ranges: list[tuple[int, int]] = []

    def Range(self, start: int, end: int) -> _FakeTrimRange:
        return _FakeTrimRange(self, start, end)


def test_trim_leading_layout_controls_skips_locked_control_char(
    monkeypatch,
) -> None:
    doc = _FakeTrimDoc()
    log_parts: list[str] = []

    def fake_is_range_locked(_doc, rng) -> bool:
        return (int(rng.Start), int(rng.End)) == (20, 21)

    monkeypatch.setattr(delete_ops, "is_range_locked", fake_is_range_locked)

    cursor = delete_ops.trim_leading_layout_controls_preserving_locked_blocks(
        doc,
        range_start=20,
        get_bound_end=lambda: 21,
        log_parts=log_parts,
    )

    assert cursor == 20
    assert doc.deleted_ranges == []
    assert log_parts == ["跳过锁定起点控制符 1 个"]
