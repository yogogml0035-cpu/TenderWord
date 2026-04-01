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


class _GapRange:
    def __init__(self, doc, start, end):
        self._doc = doc
        self.Start = int(start)
        self.End = int(end)

    def InsertBefore(self, text):
        if self.Start in self._doc.fail_positions:
            raise RuntimeError("locked")
        self._doc.insert_before_calls.append((self.Start, text))


class _GapDocument:
    def __init__(self, fail_positions=None):
        self.fail_positions = set(fail_positions or [])
        self.insert_before_calls = []

    def Range(self, start, end):
        return _GapRange(self, start, end)


class _FormatFont:
    def __init__(self):
        self.Name = None
        self.Size = None
        self.Bold = None


class _FormatParagraph:
    def __init__(self):
        self.LineSpacingRule = None
        self.LeftIndent = None
        self.FirstLineIndent = None
        self.OutlineLevel = None
        self.SpaceBeforeAuto = True
        self.SpaceAfterAuto = True
        self.SpaceBefore = 12
        self.SpaceAfter = 12


class _FormatRange:
    def __init__(self):
        self.Font = _FormatFont()
        self.ParagraphFormat = _FormatParagraph()


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


def test_build_direct_replace_items_preserves_text_table_order_and_newlines():
    items = update_word_module._build_direct_replace_items(
        "一、设备名称及数量：内镜主机/贰套\n"
        "四、主要技术规格及系统概述：\n"
        "| 1 | 设备用途 |\n"
        "| --- | --- |\n"
        "| 1.1 | 用于消化道检查与治疗 |\n"
        "五、补充说明：保持原顺序"
    )

    assert [item["type"] for item in items] == ["text_block", "table", "text_block"]
    assert items[0]["text"].endswith("四、主要技术规格及系统概述：\n")
    assert items[1]["rows"] == [["1", "设备用途"], ["1.1", "用于消化道检查与治疗"]]
    assert items[2]["text"] == "五、补充说明：保持原顺序"


def test_build_direct_replace_items_keeps_gjgk_keywords_as_plain_text():
    sample = (
        "二、交货日期：\n"
        "1、中华人民共和国关境外交付的货物：信用证开立后30天内\n"
        "三、交货地点：上海市第六人民医院临港院区\n"
    )

    items = update_word_module._build_direct_replace_items(sample)

    assert items == [{"type": "text_block", "text": sample}]


def test_advance_direct_insert_bound_uses_inserted_end_when_anchor_marker_static():
    advanced = update_word_module._advance_direct_insert_bound(
        2250,
        marker_start=2250,
        inserted_end=2388,
    )

    assert advanced == 2388


def test_advance_direct_insert_bound_prefers_moved_anchor_marker():
    advanced = update_word_module._advance_direct_insert_bound(
        2250,
        marker_start=2400,
        inserted_end=2388,
    )

    assert advanced == 2400


def test_apply_standard_insert_format_resets_paragraph_spacing():
    rng = _FormatRange()

    update_word_module._apply_standard_insert_format(
        rng,
        font_name="宋体",
        font_size=12,
    )

    assert rng.Font.Name == "宋体"
    assert rng.Font.Size == 12
    assert rng.Font.Bold is False
    assert rng.ParagraphFormat.LineSpacingRule == update_word_module.wdLineSpace1pt5
    assert rng.ParagraphFormat.LeftIndent == 0
    assert rng.ParagraphFormat.FirstLineIndent == 0
    assert (
        rng.ParagraphFormat.OutlineLevel
        == update_word_module.wdOutlineLevelBodyText
    )
    assert rng.ParagraphFormat.SpaceBeforeAuto is False
    assert rng.ParagraphFormat.SpaceAfterAuto is False
    assert rng.ParagraphFormat.SpaceBefore == 0
    assert rng.ParagraphFormat.SpaceAfter == 0


def test_resolve_table_host_range_uses_blank_paragraph_when_requested():
    host_range = update_word_module._resolve_table_host_range(
        2250,
        doc_end=3000,
        prefer_paragraph_host=True,
    )

    assert host_range == (2249, 2250)


def test_resolve_table_host_range_stays_collapsed_without_host_request():
    host_range = update_word_module._resolve_table_host_range(
        2250,
        doc_end=3000,
        prefer_paragraph_host=False,
    )

    assert host_range == (2250, 2250)


def test_resolve_post_table_cursor_prefers_explicit_gap_position():
    cursor = update_word_module._resolve_post_table_cursor(
        2250,
        gap_pos=2250,
    )

    assert cursor == 2250


def test_resolve_post_table_cursor_advances_past_table_row_end_after_append():
    cursor = update_word_module._resolve_post_table_cursor(
        2250,
        appended_paragraph=True,
    )

    assert cursor == 2251


def test_inject_local_gap_before_anchor_prefers_current_cursor():
    doc = _GapDocument()

    inserted_pos = update_word_module._inject_local_gap_before_anchor(
        doc,
        cursor_pos=2250,
        bound_start=2250,
        bound_end=2250,
    )

    assert inserted_pos == 2250
    assert doc.insert_before_calls == [(2250, "\r")]


def test_inject_local_gap_before_anchor_falls_back_to_after_anchor_boundary():
    doc = _GapDocument(fail_positions={2248})

    inserted_pos = update_word_module._inject_local_gap_before_anchor(
        doc,
        cursor_pos=2248,
        bound_start=2240,
        bound_end=2250,
    )

    assert inserted_pos == 2250
    assert doc.insert_before_calls == [(2250, "\r")]


def test_update_word_source_retries_gjgk_direct_replace_with_local_gap():
    source = inspect.getsource(update_word_module.update_word)

    assert "_inject_local_gap_before_anchor(" in source
    assert "_resolve_post_table_cursor(" in source
    assert "gjgk 插入点受阻" in source
    assert "gjgk 表格插入前已在位置" in source
    assert "gjgk 表格后续写" in source
    assert "_resolve_table_host_range(" in source
    assert "跳过 legacy 块3 路径" in source


def test_update_word_source_uses_direct_replace_items_and_skips_legacy_cleanup():
    source = inspect.getsource(update_word_module.update_word)
    module_source = inspect.getsource(update_word_module)

    assert "_apply_standard_insert_format(" in module_source
    assert "_build_direct_replace_items(polished_text)" in module_source
    assert "direct_replace_items" in source
    assert "跳过 legacy 空段/换行清理" in source
    assert "content_list if use_direct_replace else block1" not in source


def test_update_word_module_exposes_manual_debug_main():
    source = inspect.getsource(update_word_module)

    assert "def main() -> None:" in source
    assert "254DSITC2512-招标文件-发售稿-财政模板.doc" in source
    assert "delete_tender_param(test_state, config=None)" in source
    assert 'cleared_state["polished_text"] = polished_text' in source


def test_update_word_module_runs_main_when_executed_as_script():
    source = inspect.getsource(update_word_module)

    assert 'if __name__ == "__main__":' in source
    assert "main()" in source
