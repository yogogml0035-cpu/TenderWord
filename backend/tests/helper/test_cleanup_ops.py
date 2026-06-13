from __future__ import annotations

from backend.helper.word_helper.cleanup_ops import cleanup_blank_paragraphs
from backend.util.word_util import wdWithInTable


class _FakeParagraphRange:
    def __init__(self, doc: "_FakeDoc", start: int, end: int, text: str):
        self.doc = doc
        self.Start = int(start)
        self.End = int(end)
        self.Text = str(text)
        self.deleted = False

    def Information(self, code: int) -> int:
        if code == wdWithInTable:
            return -1 if self.doc.range_is_in_table(self.Start, self.End) else 0
        return 0

    def Delete(self) -> None:
        self.deleted = True
        self.doc.deleted_ranges.append((self.Start, self.End))


class _FakeParagraph:
    def __init__(self, range_obj: _FakeParagraphRange):
        self.Range = range_obj


class _FakeParagraphCollection:
    def __init__(self, paragraphs: list[_FakeParagraph]):
        self._paragraphs = paragraphs

    def __iter__(self):
        return iter(self._paragraphs)


class _FakeRangeView:
    def __init__(self, doc: "_FakeDoc", start: int, end: int):
        self.doc = doc
        self.Start = int(start)
        self.End = int(end)

    def Information(self, code: int) -> int:
        if code == wdWithInTable:
            return -1 if self.doc.range_is_in_table(self.Start, self.End) else 0
        return 0

    @property
    def Paragraphs(self) -> _FakeParagraphCollection:
        paragraphs: list[_FakeParagraph] = []
        for paragraph in self.doc.paragraphs:
            paragraph_start = int(paragraph.Range.Start)
            paragraph_end = int(paragraph.Range.End)
            if paragraph_end <= self.Start:
                continue
            if paragraph_start >= self.End:
                continue
            paragraphs.append(paragraph)
        return _FakeParagraphCollection(paragraphs)


class _FakeDoc:
    def __init__(
        self,
        *,
        table_spans: list[tuple[int, int]],
        paragraphs: list[tuple[int, int, str]],
    ):
        self.table_spans = [(int(start), int(end)) for start, end in table_spans]
        self.deleted_ranges: list[tuple[int, int]] = []
        self.paragraphs = [
            _FakeParagraph(_FakeParagraphRange(self, start, end, text))
            for start, end, text in paragraphs
        ]

    def range_is_in_table(self, start: int, end: int) -> bool:
        start_i = int(start)
        end_i = int(end)
        for table_start, table_end in self.table_spans:
            if start_i == end_i:
                if table_start <= start_i < table_end:
                    return True
            elif start_i < table_end and end_i > table_start:
                return True
        return False

    def Range(self, start: int, end: int) -> _FakeRangeView:
        return _FakeRangeView(self, start, end)


def test_cleanup_blank_paragraphs_keeps_blank_paragraph_between_tables() -> None:
    doc = _FakeDoc(
        table_spans=[(0, 10), (11, 20)],
        paragraphs=[(10, 11, "\r")],
    )

    deleted = cleanup_blank_paragraphs(doc, range_start=0, range_end=30)

    assert deleted == 0
    assert doc.deleted_ranges == []


def test_cleanup_blank_paragraphs_deletes_plain_blank_paragraph() -> None:
    doc = _FakeDoc(
        table_spans=[],
        paragraphs=[(5, 6, "\r")],
    )

    deleted = cleanup_blank_paragraphs(doc, range_start=0, range_end=30)

    assert deleted == 1
    assert doc.deleted_ranges == [(5, 6)]


def test_cleanup_blank_paragraphs_deletes_trailing_blank_after_last_table() -> None:
    doc = _FakeDoc(
        table_spans=[(0, 10)],
        paragraphs=[(10, 11, "\r")],
    )

    deleted = cleanup_blank_paragraphs(doc, range_start=0, range_end=30)

    assert deleted == 1
    assert doc.deleted_ranges == [(10, 11)]
