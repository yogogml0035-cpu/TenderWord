from __future__ import annotations

import pytest

from backend.nodes.common_word_nodes.update_word import split_polished_text_into_blocks


def test_split_polished_text_into_blocks_ignores_table_header_keyword_hits() -> None:
    polished_text = "\n".join(
        [
            "| 序号 | 产品名称 | 数量 | 交付日期 |",
            "| --- | --- | --- | --- |",
            "| 1 | 温控柜 | 2台 | 合同签订后30天 |",
            "一、补充说明",
            "2、交付日期: 合同签订后30天",
            "付款方式: 按季度结算",
            "二、售后服务要求",
        ]
    )

    result = split_polished_text_into_blocks(polished_text)

    assert result["delivery_date_line"] == "2、交付日期：合同签订后30天"
    assert result["payment_method_line"] == "付款方式：按季度结算"
    assert result["delivery_value"] == "合同签订后30天"
    assert result["payment_value"] == "按季度结算"
    assert result["block1"] == [
        "| 序号 | 产品名称 | 数量 | 交付日期 |",
        "| --- | --- | --- | --- |",
        "| 1 | 温控柜 | 2台 | 合同签订后30天 |",
        "一、补充说明",
    ]
    assert result["block2"] == []
    assert result["block3"] == ["二、售后服务要求"]


def test_split_polished_text_into_blocks_fails_when_only_table_or_prose_contains_keyword() -> None:
    polished_text = "\n".join(
        [
            "| 序号 | 产品名称 | 数量 | 交付日期 |",
            "本项目交付日期：合同签订后30天",
            "付款方式：按季度结算",
        ]
    )

    with pytest.raises(ValueError, match="缺少关键字段: 交付日期："):
        split_polished_text_into_blocks(polished_text)
