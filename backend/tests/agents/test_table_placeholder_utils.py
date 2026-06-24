from __future__ import annotations

from backend.agents.generation.table_placeholder_utils import (
    extract_table_placeholders,
    find_missing_table_placeholders,
    find_required_table_placeholders,
)


def test_extract_table_placeholders_dedupes_in_first_occurrence_order() -> None:
    text = "前文 [[TABLE:TP1_1]]\n中间 [[TABLE:TP1_2]]\n重复 [[TABLE:TP1_1]]\n"

    assert extract_table_placeholders(text) == ["TP1_1", "TP1_2"]


def test_extract_table_placeholders_matches_inline_and_standalone_lines() -> None:
    text = (
        "| 序号 | 参数 |\n"
        "| --- | --- |\n"
        "| 1 | A |\n"
        "[[TABLE:TP1]]\n"
        "结尾另含 [[TABLE:TP2]] 占位符。"
    )

    assert extract_table_placeholders(text) == ["TP1", "TP2"]


def test_extract_table_placeholders_returns_empty_when_no_match() -> None:
    assert extract_table_placeholders("普通正文，没有占位符。") == []


def test_extract_table_placeholders_handles_none_and_non_string() -> None:
    assert extract_table_placeholders(None) == []
    assert extract_table_placeholders({"x": 1}) == []


def test_find_missing_table_placeholders_reports_absent_ids_in_param_order() -> None:
    tender_params = (
        "技术参数：\n"
        "| 序号 | 参数 |\n"
        "[[TABLE:TP1_1]]\n"
        "[[TABLE:TP1_2]]\n"
    )
    current_text = (
        "技术参数：\n"
        "| 序号 | 参数 |\n"
        "| 1 | A |\n"
        "[[TABLE:TP1_2]]\n"
    )

    assert find_missing_table_placeholders(tender_params, current_text) == ["TP1_1"]


def test_find_missing_table_placeholders_returns_empty_when_all_present() -> None:
    tender_params = "[[TABLE:TP1_1]]\n[[TABLE:TP1_2]]"
    current_text = "正文\n[[TABLE:TP1_2]]\n[[TABLE:TP1_1]]"

    assert find_missing_table_placeholders(tender_params, current_text) == []


def test_find_missing_table_placeholders_returns_empty_when_params_have_none() -> None:
    assert find_missing_table_placeholders(None, "正文") == []


def test_find_required_table_placeholders_only_keeps_context_still_present() -> None:
    tender_params = (
        "附件三：保洁耗材明细清单\n"
        "序号 / 名称 / 费用\n"
        "[[TABLE:TP1_5]]\n"
        "附件四：保洁设备明细清单\n"
        "序号 / 设备名称 / 数量\n"
        "[[TABLE:TP1_6]]\n"
    )
    current_text = (
        "三、附件表单\n"
        "附件三：保洁耗材明细清单\n"
        "序号 / 名称 / 费用\n"
        "其余章节已删除\n"
    )

    assert find_required_table_placeholders(tender_params, current_text) == ["TP1_5"]


def test_find_required_table_placeholders_ignores_deleted_bid_format_duplicate_tables() -> None:
    tender_params = (
        "1、附件一：《外包服务报价明细》\n"
        "院区启用前开荒、精保洁服务报价 / 序号 / 类别 / 费用（金额/元/月） / 备注\n"
        "1 / 开荒、精保洁服务\n"
        "[[TABLE:TP1_3]]\n"
        "3、开标一览表格式\n"
        "4、报价明细\n"
        "（1）外包服务报价明细\n"
        "院区启用前开荒、精保洁服务报价 / 序号 / 类别 / 费用（金额） / 备注\n"
        "1 / 开荒、精保洁服务\n"
        "小计（元，期限按3个月计算）\n"
        "[[TABLE:TP1_10]]\n"
    )
    current_text = (
        "38、附件表单：\n"
        "1、附件一：《外包服务报价明细》\n"
        "院区启用前开荒、精保洁服务报价 / 序号 / 类别 / 费用（金额/元/月） / 备注\n"
        "1 / 开荒、精保洁服务\n"
        "[[TABLE:TP1_3]]\n"
    )

    assert find_required_table_placeholders(tender_params, current_text) == ["TP1_3"]
