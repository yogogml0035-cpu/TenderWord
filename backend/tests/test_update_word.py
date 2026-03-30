import importlib
import inspect

import pytest

update_word_module = importlib.import_module("backend.nodes.common_word_nodes.update_word")


class _FakeParagraphCollection:
    def __init__(self, paragraphs):
        self._paragraphs = list(paragraphs)
        self.Count = len(self._paragraphs)

    def __iter__(self):
        return iter(self._paragraphs)

    def __call__(self, index):
        return self._paragraphs[index - 1]


class _FakeRange:
    def __init__(self, doc, start, end, text=""):
        self._doc = doc
        self.Start = start
        self.End = end
        self.Text = text

    @property
    def Paragraphs(self):
        return _FakeParagraphCollection(
            [
                para
                for para in self._doc._paragraphs
                if para.Range.Start < self.End and para.Range.End > self.Start
            ]
        )


class _FakeParagraph:
    def __init__(self, doc, start, end, text):
        self.Range = _FakeRange(doc, start, end, text)


class _FakeDocument:
    def __init__(self, paragraphs):
        self._paragraphs = []
        for start, end, text in paragraphs:
            self._paragraphs.append(_FakeParagraph(self, start, end, text))
        self.Content = type("Content", (), {"End": 20000})()
        self.saved = False

    @property
    def Paragraphs(self):
        return _FakeParagraphCollection(self._paragraphs)

    def Range(self, start, end):
        text = "".join(
            para.Range.Text
            for para in self._paragraphs
            if para.Range.Start < end and para.Range.End > start
        )
        return _FakeRange(self, start, end, text)

    def Save(self):
        self.saved = True


class _FakeSelection:
    def __init__(self, page_starts):
        self._page_starts = page_starts
        self._page = 1
        self.Start = page_starts[1]
        self.Range = _FakeRange(None, self.Start, self.Start, "")

    def GoTo(self, _what, _which, page):
        self._page = page
        self.Start = self._page_starts.get(page, self._page_starts[max(self._page_starts)])
        self.Range = _FakeRange(None, self.Start, self.Start, "")

    def Information(self, _kind):
        return self._page


class _FakeWord:
    def __init__(self):
        self.Selection = _FakeSelection({1: 0, 20: 11000, 21: 11200, 22: 11800, 23: 12400})


def test_collect_protected_fields_recovers_keywords_within_anchor_range():
    doc = _FakeDocument(
        [
            (11190, 11230, "2、交付日期：签订后 90 天\r"),
            (11300, 11350, "一、项目概述\r"),
            (11700, 11770, "4、付款方式：验收后 90 日付款\r"),
        ]
    )

    fields = update_word_module._collect_protected_fields(
        doc=doc,
        keywords=["交付日期", "付款方式"],
        target_range=(11250, 11800),
        fallback_range=(11200, 11800),
    )

    assert set(fields.keys()) == {"交付日期", "付款方式"}
    assert fields["交付日期"].Text.startswith("2、交付日期")
    assert fields["付款方式"].Text.startswith("4、付款方式")


def test_refresh_protected_fields_rebinds_positions_after_cleanup():
    doc = _FakeDocument(
        [
            (11210, 11250, "2、交付日期：签订后 90 天\r"),
            (11720, 11790, "4、付款方式：验收后 90 日付款\r"),
        ]
    )
    stale_fields = {
        "交付日期": _FakeRange(doc, 100, 140, "旧交付日期\r"),
        "付款方式": _FakeRange(doc, 200, 250, "旧付款方式\r"),
    }

    refreshed = update_word_module._refresh_protected_fields(
        doc=doc,
        keywords=["交付日期", "付款方式"],
        range_start=11200,
        range_end=11800,
        existing_fields=stale_fields,
    )

    assert refreshed["交付日期"].Start == 11210
    assert refreshed["付款方式"].Start == 11720


def test_validate_required_protected_fields_raises_for_missing_keyword():
    with pytest.raises(ValueError, match="缺少关键受保护字段: 交付日期"):
        update_word_module._validate_required_protected_fields(
            {"付款方式": object()},
            required_keywords=("交付日期", "付款方式"),
        )


def test_resolve_block_flow_with_only_delivery_field():
    flow = update_word_module._resolve_block_flow({"交付日期": object()})

    assert flow["has_delivery"] is True
    assert flow["has_payment"] is False
    assert flow["block2_mode"] == "after_delivery"
    assert flow["block3_anchor"] == "before_after_anchor"


def test_resolve_block_flow_with_both_protected_fields():
    flow = update_word_module._resolve_block_flow(
        {"交付日期": object(), "付款方式": object()}
    )

    assert flow["has_delivery"] is True
    assert flow["has_payment"] is True
    assert flow["block2_mode"] == "between_delivery_payment"
    assert flow["block3_anchor"] == "after_payment"


def test_resolve_block_flow_when_payment_missing():
    flow = update_word_module._resolve_block_flow({})

    assert flow["has_delivery"] is False
    assert flow["has_payment"] is False
    assert flow["block2_mode"] == "skip"
    assert flow["block3_anchor"] == "before_after_anchor"


def test_update_word_main_flow_no_longer_calls_required_field_gate():
    source = inspect.getsource(update_word_module.update_word)

    assert "_validate_required_protected_fields(" not in source
    assert "付款方式字段位置超出插入边界" in source


def test_update_word_gjgk_uses_direct_replace_mode():
    assert update_word_module.get_content_update_mode("gjgk") == "direct_replace"


def test_update_word_source_contains_gjgk_direct_replace_anchor_start():
    source = inspect.getsource(update_word_module.update_word)

    assert "content_update_mode == CONTENT_UPDATE_MODE_DIRECT_REPLACE" in source
    assert "direct_replace 从锚点后位置开始插入" in source


def test_update_word_source_allows_empty_anchor_insert_range():
    source = inspect.getsource(update_word_module.update_word)

    assert "allow_empty=True" in source
