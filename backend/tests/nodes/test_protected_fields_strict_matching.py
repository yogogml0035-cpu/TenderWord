from __future__ import annotations

from dataclasses import dataclass

from backend.config.tender_config import get_protected_field_profile
from backend.helper.word_helper.protected_fields import (
    collect_protected_fields,
    collect_profile_protected_fields,
    match_protected_field_line,
    normalize_protected_field_paragraphs,
    normalize_protected_field_text,
    refind_protected_paragraph,
    refresh_protected_fields,
)
from backend.util.word_util import wdCollapseEnd, wdWithInTable

DELIVERY_DATE_MARKER = "交付日期："
PAYMENT_METHOD_MARKER = "付款方式："
SERVICE_TERM_MARKER = "服务期限："
COMMON_TWO_FIELD_PROFILE = get_protected_field_profile("xjcg")


@dataclass
class _ParagraphRecord:
    text: str
    in_table: bool
    start: int = 0
    end: int = 0


class _FakeParagraphRange:
    def __init__(self, record: _ParagraphRecord):
        self._record = record

    @property
    def Start(self) -> int:
        return int(self._record.start)

    @property
    def End(self) -> int:
        return int(self._record.end)

    @property
    def Text(self) -> str:
        return self._record.text

    def Information(self, code: int) -> int:
        if code == wdWithInTable:
            return -1 if self._record.in_table else 0
        return 0


class _FakeParagraph:
    def __init__(self, record: _ParagraphRecord):
        self._record = record
        self.Range = _FakeParagraphRange(record)


class _FakeParagraphCollection:
    def __init__(self, paragraphs: list[_FakeParagraph]):
        self._paragraphs = paragraphs

    def __iter__(self):
        return iter(self._paragraphs)

    def __call__(self, index: int) -> _FakeParagraph:
        return self._paragraphs[index - 1]


class _FakeFind:
    def __init__(self, range_view: "_FakeRangeView"):
        self._range_view = range_view
        self.Text = ""
        self.Forward = True
        self.Wrap = 0
        self.MatchCase = False
        self.MatchWholeWord = False

    def ClearFormatting(self) -> None:
        return None

    def Execute(self) -> bool:
        start = int(self._range_view.Start)
        end = int(self._range_view.End)
        for paragraph in self._range_view._doc.iter_paragraphs(start, end):
            text = str(paragraph.Range.Text or "")
            if self.Text and self.Text not in text:
                continue
            self._range_view.Start = int(paragraph.Range.Start)
            self._range_view.End = int(paragraph.Range.End)
            return True
        return False


class _FakeRangeView:
    def __init__(self, doc: "_FakeDoc", start: int, end: int):
        self._doc = doc
        self.Start = int(start)
        self.End = int(end)
        self.Find = _FakeFind(self)

    @property
    def Paragraphs(self) -> _FakeParagraphCollection:
        return _FakeParagraphCollection(
            list(self._doc.iter_paragraphs(int(self.Start), int(self.End)))
        )

    @property
    def Text(self) -> str:
        return self._doc.slice_text(int(self.Start), int(self.End))

    @Text.setter
    def Text(self, value: str) -> None:
        self._doc.replace_slice(int(self.Start), int(self.End), str(value))
        self.End = int(self.Start) + len(str(value))

    def Collapse(self, direction: int) -> None:
        if direction == wdCollapseEnd:
            self.Start = int(self.End)


class _FakeDoc:
    def __init__(self, lines: list[tuple[str, bool]]):
        self._records = [_ParagraphRecord(text=text, in_table=in_table) for text, in_table in lines]
        self._reindex()
        self.Content = type("_FakeContent", (), {"End": self._content_end()})()

    def _content_end(self) -> int:
        if not self._records:
            return 0
        return int(self._records[-1].end) + 1

    def _reindex(self) -> None:
        cursor = 0
        for record in self._records:
            record.start = cursor
            record.end = cursor + max(len(record.text), 1) + 1
            cursor = record.end

    def slice_text(self, start: int, end: int) -> str:
        for record in self._records:
            if int(record.start) <= int(start) <= int(record.end):
                rel_start = max(0, int(start) - int(record.start))
                rel_end = max(rel_start, min(len(record.text), int(end) - int(record.start)))
                return record.text[rel_start:rel_end]
        return ""

    def replace_slice(self, start: int, end: int, value: str) -> None:
        for index, record in enumerate(self._records):
            if int(record.start) <= int(start) <= int(record.end):
                rel_start = max(0, int(start) - int(record.start))
                rel_end = max(rel_start, min(len(record.text), int(end) - int(record.start)))
                record.text = f"{record.text[:rel_start]}{value}{record.text[rel_end:]}"
                self._records[index] = record
                self._reindex()
                self.Content.End = self._content_end()
                return

    def iter_paragraphs(self, start: int, end: int):
        start_i = int(start)
        end_i = int(end)
        if end_i <= start_i:
            for record in self._records:
                if int(record.start) <= start_i < int(record.end):
                    yield _FakeParagraph(record)
            return
        for record in self._records:
            p_start = int(record.start)
            p_end = int(record.end)
            if p_end < start_i:
                continue
            if p_start > end_i:
                continue
            yield _FakeParagraph(record)

    def Range(self, start: int, end: int) -> _FakeRangeView:
        return _FakeRangeView(self, start, end)


def test_match_protected_field_line_accepts_canonical_marker_and_tracks_source_marker() -> None:
    matched = match_protected_field_line("服务期限: 12个月", SERVICE_TERM_MARKER)

    assert matched is not None
    assert matched["canonical_marker"] == SERVICE_TERM_MARKER
    assert matched["source_marker"] == "服务期限:"
    assert matched["normalized_line"] == "服务期限：12个月"
    assert matched["value"] == "12个月"


def test_match_protected_field_line_rejects_table_and_prose_hits() -> None:
    assert (
        match_protected_field_line("| 序号 | 产品名称 | 数量 | 交付日期 |", DELIVERY_DATE_MARKER)
        is None
    )
    assert match_protected_field_line("本项目交付日期：合同签订后30天", DELIVERY_DATE_MARKER) is None


def test_normalize_protected_field_text_only_rewrites_legal_field_lines() -> None:
    normalized = normalize_protected_field_text(
        "\n".join(
            [
                "服务期限: 12个月",
                "| 序号 | 服务期限 |",
                "本项目服务期限: 12个月",
                "付款方式：按季度结算",
            ]
        ),
        (SERVICE_TERM_MARKER, PAYMENT_METHOD_MARKER),
    )

    assert normalized.split("\n") == [
        "服务期限：12个月",
        "| 序号 | 服务期限 |",
        "本项目服务期限: 12个月",
        "付款方式：按季度结算",
    ]


def test_normalize_protected_field_paragraphs_and_collect_refresh_use_canonical_markers() -> None:
    doc = _FakeDoc(
        [
            ("2、交付日期:合同签订后30天", False),
            ("付款方式：按季度结算", False),
        ]
    )

    normalized_count = normalize_protected_field_paragraphs(
        doc,
        (DELIVERY_DATE_MARKER, PAYMENT_METHOD_MARKER),
        0,
        10_000,
    )
    assert normalized_count == 1

    protected_fields = collect_protected_fields(
        doc=doc,
        markers=[DELIVERY_DATE_MARKER, PAYMENT_METHOD_MARKER],
        target_range=(0, 10_000),
        fallback_range=None,
    )
    assert set(protected_fields.keys()) == {DELIVERY_DATE_MARKER, PAYMENT_METHOD_MARKER}
    assert protected_fields[DELIVERY_DATE_MARKER].Text == "2、交付日期：合同签订后30天"

    refreshed = refresh_protected_fields(
        doc=doc,
        markers=[DELIVERY_DATE_MARKER, PAYMENT_METHOD_MARKER],
        range_start=0,
        range_end=10_000,
        existing_fields={},
    )
    assert set(refreshed.keys()) == {DELIVERY_DATE_MARKER, PAYMENT_METHOD_MARKER}
    assert refreshed[PAYMENT_METHOD_MARKER].Text == "付款方式：按季度结算"


def test_collect_profile_protected_fields_fails_fast_with_suspicious_hits() -> None:
    doc = _FakeDoc(
        [
            ("本项目交付日期：合同签订后30天", False),
            ("付款方式：按季度结算", False),
        ]
    )

    try:
        collect_profile_protected_fields(
            doc=doc,
            profile=COMMON_TWO_FIELD_PROFILE,
            target_range=(0, 10_000),
            fallback_range=None,
        )
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected collect_profile_protected_fields to fail fast")

    assert "缺少关键受保护字段: 交付日期：" in message
    assert "可疑命中: 交付日期： -> 本项目交付日期：合同签订后30天" in message


def test_refind_protected_paragraph_skips_table_hits_and_returns_strict_line() -> None:
    doc = _FakeDoc(
        [
            ("交付日期：仅为表格单元格", True),
            ("| 序号 | 产品名称 | 数量 | 交付日期 |", False),
            ("2、交付日期：合同签订后30天", False),
        ]
    )

    para = refind_protected_paragraph(
        doc=doc,
        marker=DELIVERY_DATE_MARKER,
        bound_start=0,
        bound_end=10_000,
    )
    assert para is not None
    assert para.Text == "2、交付日期：合同签订后30天"
