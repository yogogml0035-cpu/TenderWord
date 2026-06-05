from __future__ import annotations

from dataclasses import dataclass

from backend.config.tender_config import get_protected_field_profile
from backend.helper.word_helper.protected_fields import (
    collect_protected_fields,
    collect_profile_protected_fields,
    insert_prefix_before_keyword,
    match_protected_field_line,
    normalize_protected_field_paragraphs,
    normalize_protected_field_text,
    refind_protected_paragraph,
    refresh_profile_protected_fields,
    refresh_protected_fields,
    update_protected_field,
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

    @Text.setter
    def Text(self, value: str) -> None:
        self._record.text = str(value)

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


class _FakeFont:
    def __init__(self):
        self.Name = "旧字体"
        self.Size = 9
        self.Bold = True
        self.Italic = True
        self.Underline = 1
        self.StrikeThrough = True
        self.Color = 255

    def __setattr__(self, name: str, value):
        if name == "HighlightColorIndex":
            raise AttributeError("Font has no HighlightColorIndex in this fake")
        object.__setattr__(self, name, value)


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
        self.Font = _FakeFont()
        self.HighlightColorIndex = 7

    @property
    def Paragraphs(self) -> _FakeParagraphCollection:
        if int(self.Start) == int(self.End):
            paragraph = self._doc.paragraph_for_pos(int(self.Start))
            return _FakeParagraphCollection([paragraph] if paragraph else [])
        records = list(self._doc.iter_paragraph_records(int(self.Start), int(self.End)))
        if (
            len(records) == 1
            and int(self.Start) > int(records[0].start)
            and int(self.End) < int(records[0].end)
        ):
            return _FakeParagraphCollection([_FakeParagraphRangeBackedParagraph(self)])
        return _FakeParagraphCollection([_FakeParagraph(record) for record in records])

    @property
    def Text(self) -> str:
        return self._doc.slice_text(int(self.Start), int(self.End))

    @Text.setter
    def Text(self, value: str) -> None:
        self._doc.replace_slice(int(self.Start), int(self.End), str(value))
        self.End = int(self.Start) + len(str(value))

    def InsertBefore(self, value: str) -> None:
        self._doc.replace_slice(int(self.Start), int(self.Start), str(value))
        self.End = int(self.Start) + len(str(value))

    def Collapse(self, direction: int) -> None:
        if direction == wdCollapseEnd:
            self.Start = int(self.End)


class _FakeDoc:
    def __init__(self, lines: list[tuple[str, bool]]):
        self._records = [_ParagraphRecord(text=text, in_table=in_table) for text, in_table in lines]
        self._reindex()
        self.Content = type("_FakeContent", (), {"End": self._content_end()})()
        self.created_ranges: list[_FakeRangeView] = []

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
        records = list(self.iter_paragraph_records(int(start), int(end)))
        if len(records) > 1:
            pieces: list[str] = []
            for record in records:
                rel_start = max(0, int(start) - int(record.start))
                rel_end = min(len(record.text), max(rel_start, int(end) - int(record.start)))
                pieces.append(record.text[rel_start:rel_end])
            return "\r".join(pieces)
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
        range_view = _FakeRangeView(self, start, end)
        self.created_ranges.append(range_view)
        return range_view

    def iter_paragraph_records(self, start: int, end: int):
        start_i = int(start)
        end_i = int(end)
        if end_i <= start_i:
            record = self.record_for_pos(start_i)
            if record is not None:
                yield record
            return
        for record in self._records:
            p_start = int(record.start)
            p_end = int(record.end)
            if p_end < start_i:
                continue
            if p_start > end_i:
                continue
            yield record

    def record_for_pos(self, pos: int) -> _ParagraphRecord | None:
        for record in self._records:
            if int(record.start) <= int(pos) < int(record.end):
                return record
        return None

    def paragraph_for_pos(self, pos: int) -> _FakeParagraph | None:
        record = self.record_for_pos(pos)
        if record is None:
            return None
        return _FakeParagraph(record)


class _FakeParagraphRangeBackedParagraph:
    def __init__(self, range_view: _FakeRangeView):
        self.Range = range_view


def _assert_clean_generated_format(range_view: _FakeRangeView) -> None:
    font = range_view.Font
    assert font.Name == "宋体"
    assert font.Size == 12
    assert font.Bold is False
    assert font.Italic is False
    assert font.Underline == 0
    assert font.StrikeThrough is False
    assert font.Color == 0
    assert range_view.HighlightColorIndex == 0


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
    assert (
        match_protected_field_line(
            "付款方式：设备安装验收合格后的三个月内付清全款。\r三、技术规格要求：",
            PAYMENT_METHOD_MARKER,
        )
        is None
    )


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


def test_update_protected_field_resets_generated_value_font_only() -> None:
    doc = _FakeDoc([("付款方式：旧值", False)])
    protected_fields = {PAYMENT_METHOD_MARKER: doc.Range(0, doc.Content.End)}

    assert update_protected_field(
        doc,
        PAYMENT_METHOD_MARKER,
        "按季度结算",
        protected_fields,
    )

    assert doc._records[0].text == "付款方式：按季度结算"
    _assert_clean_generated_format(doc.created_ranges[-1])


def test_update_protected_field_accepts_word_manual_line_break_tail() -> None:
    doc = _FakeDoc([("3、付款方式：旧值\v二、总体需求\v1．适配设备", False)])
    protected_fields = {PAYMENT_METHOD_MARKER: doc.Range(0, doc.Content.End)}

    assert update_protected_field(
        doc,
        PAYMENT_METHOD_MARKER,
        "设备安装验收合格后的三个月内付清全款。",
        protected_fields,
    )

    assert doc._records[0].text == "3、付款方式：设备安装验收合格后的三个月内付清全款。"
    _assert_clean_generated_format(doc.created_ranges[-1])


def test_update_protected_field_appends_suffix_when_word_truncates_value_writeback() -> None:
    class _TruncatingRangeView(_FakeRangeView):
        @property
        def Text(self) -> str:
            return self._doc.slice_text(int(self.Start), int(self.End))

        @Text.setter
        def Text(self, value: str) -> None:
            value_text = str(value)
            if value_text == "合同签订后30天内交货":
                value_text = "合同签订"
            self._doc.replace_slice(int(self.Start), int(self.End), value_text)
            self.End = int(self.Start) + len(value_text)

    class _TruncatingDoc(_FakeDoc):
        def Range(self, start: int, end: int) -> _FakeRangeView:
            range_view = _TruncatingRangeView(self, start, end)
            self.created_ranges.append(range_view)
            return range_view

    doc = _TruncatingDoc([("交付日期：旧值", False)])
    protected_fields = {DELIVERY_DATE_MARKER: doc.Range(0, doc.Content.End)}
    log_parts: list[str] = []

    assert update_protected_field(
        doc,
        DELIVERY_DATE_MARKER,
        "合同签订后30天内交货",
        protected_fields,
        log_parts=log_parts,
    )

    assert doc._records[0].text == "交付日期：合同签订后30天内交货"
    assert any("检测到截断" in line for line in log_parts)


def test_insert_prefix_before_keyword_resets_generated_prefix_font_only() -> None:
    doc = _FakeDoc([("交付日期：旧值", False)])
    protected_fields = {DELIVERY_DATE_MARKER: doc.Range(0, doc.Content.End)}

    assert insert_prefix_before_keyword(
        doc,
        DELIVERY_DATE_MARKER,
        "2、",
        protected_fields,
    )

    assert doc._records[0].text == "2、交付日期：旧值"
    _assert_clean_generated_format(doc.created_ranges[-1])


def test_insert_prefix_before_keyword_replaces_existing_number_prefix() -> None:
    doc = _FakeDoc([("3、付款方式：旧值", False)])
    protected_fields = {PAYMENT_METHOD_MARKER: doc.Range(0, doc.Content.End)}

    assert insert_prefix_before_keyword(
        doc,
        PAYMENT_METHOD_MARKER,
        "2、",
        protected_fields,
    )

    assert doc._records[0].text == "2、付款方式：旧值"
    _assert_clean_generated_format(doc.created_ranges[-1])


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


def test_collect_protected_fields_expands_split_field_chunk_to_logical_line() -> None:
    doc = _FakeDoc(
        [
            ("1、设备名称及数量：射频治疗仪/壹套", False),
            ("2、交付日期：第1包：射频治疗仪采购", False),
            ("3、交付地点：采购人指定地点", False),
            ("4、付款方式：设备验收合格后采购人支付合同金额的100%", False),
        ]
    )
    delivery = doc._records[1]
    payment = doc._records[3]
    delivery_chunk_start = delivery.start + len("2、")
    payment_chunk_start = payment.start + len("4、")

    original_range = doc.Range

    def _range_with_split_chunks(start: int, end: int):
        if int(start) == 0 and int(end) == 10_000:
            return type(
                "_SplitScanRange",
                (),
                {
                    "Paragraphs": _FakeParagraphCollection(
                        [
                            _FakeParagraphRangeBackedParagraph(
                                original_range(delivery_chunk_start, delivery.end - 1)
                            ),
                            _FakeParagraphRangeBackedParagraph(
                                original_range(payment_chunk_start, payment.end - 1)
                            ),
                        ]
                    )
                },
            )()
        return original_range(start, end)

    doc.Range = _range_with_split_chunks  # type: ignore[method-assign]

    protected_fields = collect_protected_fields(
        doc=doc,
        markers=[DELIVERY_DATE_MARKER, PAYMENT_METHOD_MARKER],
        target_range=(0, 10_000),
        fallback_range=None,
    )

    assert protected_fields[DELIVERY_DATE_MARKER].Start == delivery.start
    assert protected_fields[DELIVERY_DATE_MARKER].Text == "2、交付日期：第1包：射频治疗仪采购"
    assert protected_fields[PAYMENT_METHOD_MARKER].Start == payment.start
    assert (
        protected_fields[PAYMENT_METHOD_MARKER].Text
        == "4、付款方式：设备验收合格后采购人支付合同金额的100%"
    )


def test_refresh_profile_protected_fields_rejects_stale_cross_paragraph_existing_range() -> None:
    doc = _FakeDoc(
        [
            ("2、交付日期：合同签订后30天", False),
            ("三、技术规格要求：", False),
        ]
    )
    stale_payment_range = type(
        "_StalePaymentRange",
        (),
        {
            "Start": 20,
            "End": 80,
            "Text": "付款方式：设备安装验收合格后的三个月内付清全款。\r三、技术规格要求：",
        },
    )()

    try:
        refresh_profile_protected_fields(
            doc=doc,
            profile=COMMON_TWO_FIELD_PROFILE,
            range_start=0,
            range_end=10_000,
            existing_fields={PAYMENT_METHOD_MARKER: stale_payment_range},
        )
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected stale cross-paragraph range to be rejected")

    assert "缺少关键受保护字段: 付款方式：" in message


def test_refresh_profile_protected_fields_keeps_manual_line_break_field_range() -> None:
    doc = _FakeDoc(
        [
            ("2、交付日期：合同签订后30天", False),
            ("3、付款方式：旧值\v二、总体需求\v1．适配设备", False),
        ]
    )

    refreshed = refresh_profile_protected_fields(
        doc=doc,
        profile=COMMON_TWO_FIELD_PROFILE,
        range_start=0,
        range_end=10_000,
        existing_fields={},
    )

    assert set(refreshed.keys()) == {DELIVERY_DATE_MARKER, PAYMENT_METHOD_MARKER}
    assert refreshed[PAYMENT_METHOD_MARKER].Text == "3、付款方式：旧值\v二、总体需求\v1．适配设备"


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


def test_refind_protected_paragraph_expands_split_field_chunk_to_logical_line() -> None:
    doc = _FakeDoc(
        [
            ("2、交付日期：第1包：射频治疗仪采购", False),
            ("3、交付地点：采购人指定地点", False),
        ]
    )
    delivery = doc._records[0]
    delivery_chunk_start = delivery.start + len("2、")

    class _SplitFind(_FakeFind):
        def Execute(self) -> bool:
            if self._range_view.Start > delivery_chunk_start:
                return False
            self._range_view.Start = delivery_chunk_start
            self._range_view.End = delivery.end - 1
            return True

    class _SplitSearchRange(_FakeRangeView):
        def __init__(self, doc: _FakeDoc, start: int, end: int):
            super().__init__(doc, start, end)
            self.Find = _SplitFind(self)

    original_range = doc.Range

    def _range_with_split_find(start: int, end: int):
        if int(start) == 0 and int(end) == 10_000:
            return _SplitSearchRange(doc, start, end)
        return original_range(start, end)

    doc.Range = _range_with_split_find  # type: ignore[method-assign]

    para = refind_protected_paragraph(
        doc=doc,
        marker=DELIVERY_DATE_MARKER,
        bound_start=0,
        bound_end=10_000,
    )

    assert para is not None
    assert para.Start == delivery.start
    assert para.Text == "2、交付日期：第1包：射频治疗仪采购"
