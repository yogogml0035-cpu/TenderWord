from __future__ import annotations

import pytest

from backend.nodes.gngk_word_nodes.gngk_fw_zc_update_word import (
    _require_all_protected_fields,
    split_polished_text_into_blocks,
)


def test_split_polished_text_into_blocks_splits_service_three_field_flow() -> None:
    polished_text = "\n".join(
        [
            "一、服务概述",
            "服务地点：上海院区",
            "1. 驻场时间覆盖工作日",
            "服务期限: 12个月",
            "| 序号 | 内容 |",
            "| --- | --- |",
            "| 1 | 巡检 |",
            "付款方式：按季度结算",
            "七、其他补充要求",
        ]
    )

    result = split_polished_text_into_blocks(polished_text)

    assert result["service_location_value"] == "上海院区"
    assert result["service_term_value"] == "12个月"
    assert result["payment_value"] == "按季度结算"
    assert result["block1"] == ["一、服务概述"]
    assert result["block2"] == ["1. 驻场时间覆盖工作日"]
    assert result["block3"] == [
        "| 序号 | 内容 |",
        "| --- | --- |",
        "| 1 | 巡检 |",
    ]
    assert result["block4"] == ["七、其他补充要求"]


def test_split_polished_text_into_blocks_rejects_missing_or_out_of_order_fields() -> None:
    with pytest.raises(ValueError, match="缺少关键字段: 服务期限"):
        split_polished_text_into_blocks(
            "\n".join(
                [
                    "服务地点：上海院区",
                    "付款方式：按季度结算",
                ]
            )
        )

    with pytest.raises(ValueError, match="顺序必须为 服务地点 -> 服务期限 -> 付款方式"):
        split_polished_text_into_blocks(
            "\n".join(
                [
                    "服务期限：12个月",
                    "服务地点：上海院区",
                    "付款方式：按季度结算",
                ]
            )
        )


def test_require_all_protected_fields_raises_when_service_field_missing() -> None:
    with pytest.raises(ValueError, match="缺少关键受保护字段: 服务期限"):
        _require_all_protected_fields(
            {
                "服务地点": object(),
                "付款方式": object(),
            }
        )
