from __future__ import annotations

import importlib


delete_module = importlib.import_module(
    "backend.nodes.gngk_word_nodes.gngk_fw_zc_delete_tender_param"
)


class _FakeContent:
    def __init__(self, doc: "_FakeDoc") -> None:
        self._doc = doc

    @property
    def End(self) -> int:
        return len(self._doc.text)


class _FakeRange:
    def __init__(self, doc: "_FakeDoc", start: int, end: int) -> None:
        self._doc = doc
        self.Start = start
        self.End = end

    @property
    def Text(self) -> str:
        return self._doc.text[self.Start : self.End]

    def InsertBefore(self, value: str) -> None:
        self._doc.text = (
            self._doc.text[: self.Start] + value + self._doc.text[self.Start :]
        )
        self.End += len(value)

    def InsertParagraphAfter(self) -> None:
        self._doc.text = self._doc.text[: self.End] + "\r" + self._doc.text[self.End :]

    def Delete(self) -> None:
        self._doc.text = self._doc.text[: self.Start] + self._doc.text[self.End :]


class _FakeParagraph:
    def __init__(self, doc: "_FakeDoc", start: int, end: int) -> None:
        self.Range = _FakeRange(doc, start, end)


class _FakeDoc:
    def __init__(self, text: str) -> None:
        self.text = text
        self.Content = _FakeContent(self)

    def Range(self, start: int, end: int) -> _FakeRange:
        return _FakeRange(self, start, end)

    @property
    def Paragraphs(self) -> list[_FakeParagraph]:
        paragraphs: list[_FakeParagraph] = []
        start = 0
        while start < len(self.text):
            next_break = self.text.find("\r", start)
            if next_break >= 0:
                end = next_break + 1
            else:
                end = len(self.text)
            paragraphs.append(_FakeParagraph(self, start, end))
            start = end
        return paragraphs


def _first_candidate_position(_doc, candidate_positions, **_kwargs):
    for position in candidate_positions:
        return int(position)
    return None


def test_restore_protected_field_paragraph_boundaries_separates_each_service_field(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        delete_module._common_delete_tender_param,
        "_find_safe_insert_position",
        _first_candidate_position,
    )

    doc = _FakeDoc("前文服务地点：上海服务期限：12个月付款方式：月结")

    delete_module._restore_protected_field_paragraph_boundaries(
        doc=doc,
        before_text="第三章 招标内容及要求",
        before_end_pos=2,
        tender_type="gngk_fw_zc",
        log=None,
    )

    assert doc.text == "前文\r服务地点：上海\r服务期限：12个月\r付款方式：月结\r"


def test_insert_paragraph_break_before_field_skips_when_no_safe_position(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        delete_module._common_delete_tender_param,
        "_find_safe_insert_position",
        lambda *_args, **_kwargs: None,
    )

    doc = _FakeDoc("服务地点：上海服务期限：12个月")
    original_text = doc.text

    inserted = delete_module._insert_paragraph_break_before_field(
        doc=doc,
        field_name="服务期限",
        markers=("服务期限：", "服务期限:"),
        field_para_rng=doc.Paragraphs[0].Range,
        fallback_pos=None,
        tender_type="gngk_fw_zc",
        log=None,
    )

    assert inserted is False
    assert doc.text == original_text


def test_cleanup_service_field_residual_paragraphs_removes_non_field_paragraphs() -> None:
    doc = _FakeDoc(
        "前文\r服务地点：上海\r旧条款段落\r服务期限：12个月\r\x0c\r付款方式：月结\r"
    )

    deleted_count = delete_module._cleanup_service_field_residual_paragraphs(
        doc,
        cleanup_start=2,
        cleanup_end=doc.Content.End,
        log=None,
    )

    assert deleted_count == 2
    assert doc.text == "前文\r服务地点：上海\r服务期限：12个月\r付款方式：月结\r"
