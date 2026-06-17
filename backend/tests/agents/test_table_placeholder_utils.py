from __future__ import annotations

from backend.agents.generation.table_placeholder_utils import (
    build_missing_table_placeholder_findings,
    extract_table_placeholders,
    find_missing_table_placeholders,
    find_required_table_placeholders,
    restore_missing_table_placeholders,
    raise_if_table_placeholders_missing,
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


def test_build_missing_table_placeholder_findings_emits_one_per_missing_id() -> None:
    findings = build_missing_table_placeholder_findings(["TP1_1", "TP1_2"])

    assert len(findings) == 2
    assert findings[0].evidence == (
        "技术参数包含结构化表占位符 [[TABLE:TP1_1]]，"
        "但待审核正文缺失该占位符。结构化表必须以占位符原样保留，"
        "不得改写为 Markdown/手绘表格或省略。"
    )
    assert findings[0].fix_hint == (
        "在对应位置补回占位符 [[TABLE:TP1_1]]，"
        "保持技术参数中该表的原始位置与上下文；不要手工重绘表格。"
    )
    assert findings[1].evidence == (
        "技术参数包含结构化表占位符 [[TABLE:TP1_2]]，"
        "但待审核正文缺失该占位符。结构化表必须以占位符原样保留，"
        "不得改写为 Markdown/手绘表格或省略。"
    )


def test_build_missing_table_placeholder_findings_drops_empty_ids() -> None:
    findings = build_missing_table_placeholder_findings(["", "TP1_1"])

    assert len(findings) == 1
    assert "TP1_1" in findings[0].evidence


def test_build_missing_table_placeholder_findings_returns_empty_for_empty_input() -> None:
    assert build_missing_table_placeholder_findings([]) == []


def test_raise_if_table_placeholders_missing_lists_all_ids() -> None:
    try:
        raise_if_table_placeholders_missing(
            "附件三：保洁耗材\n序号 / 名称 / 费用\n[[TABLE:TP1_1]]\n附件四：保洁设备\n序号 / 设备名称 / 数量\n[[TABLE:TP1_2]]",
            "附件三：保洁耗材\n序号 / 名称 / 费用\n[[TABLE:TP1_1]]\n附件四：保洁设备\n序号 / 设备名称 / 数量\n普通文本",
            error_prefix="结构化表占位符缺失",
        )
    except ValueError as exc:
        message = str(exc)
        assert "TP1_2" in message
        assert "TP1_1" not in message
        assert "禁止写回普通表格" in message
    else:
        raise AssertionError("expected ValueError")


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


def test_restore_missing_table_placeholders_skips_scoring_table() -> None:
    tender_params = (
        "28、人员要求\n"
        "序号 / 楼宇 / 楼层 / 科室 / 岗位 / 岗位数 / 人数 / 工作时间\n"
        "1 / 医疗综合楼 / B2 / 放疗科 / 保洁 / 3 / 3 / 6：00-17：00\n"
        "[[TABLE:TP1_1]]\n"
        "投标评分细则（100分）tbpfxz\n"
        "序号 / 评分要素 / 分值 / 评分标准\n"
        "1 / 报价得分 / 0-20 / 报价分＝价格分值×（评标基准价/评审价）\n"
        "[[TABLE:TP1_8]]\n"
    )
    current_text = (
        "28、人员要求\n"
        "| 序号 | 楼宇 | 楼层 | 科室 | 岗位 | 岗位数 | 人数 | 工作时间 |\n"
        "| 1 | 医疗综合楼 | B2 | 放疗科 | 保洁 | 3 | 3 | 6：00-17：00 |\n"
    )

    restored = restore_missing_table_placeholders(tender_params, current_text)

    assert "[[TABLE:TP1_1]]" in restored
    assert "[[TABLE:TP1_8]]" not in restored


def test_raise_if_table_placeholders_missing_ignores_removed_table_sections() -> None:
    tender_params = (
        "附件三：保洁耗材明细清单\n"
        "序号 / 名称 / 费用\n"
        "[[TABLE:TP1_5]]\n"
        "附件四：保洁设备明细清单\n"
        "序号 / 设备名称 / 数量\n"
        "[[TABLE:TP1_6]]\n"
    )

    raise_if_table_placeholders_missing(
        tender_params,
        "正文只保留别的段落，没有附件三和附件四上下文",
        error_prefix="结构化表占位符缺失",
    )
