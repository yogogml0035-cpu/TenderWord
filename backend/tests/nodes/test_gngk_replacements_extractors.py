from __future__ import annotations

import importlib
import inspect

import pytest

hw_zc_module = importlib.import_module(
    "backend.nodes.gngk_word_nodes.gngk_hw_zc_get_replacements"
)

from backend.nodes.common_word_nodes.get_replacements_shared import (
    extract_public_tender_buyer_name,
    extract_public_tender_bzj_rule,
    extract_public_tender_contact_fields,
    extract_public_tender_investment,
    extract_public_tender_platform,
    format_public_tender_investment_value,
)
from backend.nodes.gngk_word_nodes.gngk_fw_zc_get_replacements import (
    GNGK_FW_ZC_EXTRACTORS,
    GNGK_FW_ZC_REPLACEMENT_FIELDS,
    extract_gngk_fw_zc_project_content,
)
from backend.nodes.gngk_word_nodes.gngk_get_replacements import (
    extract_gngk_project_name,
    extract_gngk_project_number,
)
from backend.nodes.gngk_word_nodes.gngk_hw_zc_get_replacements import (
    GNGK_HW_ZC_EXTRACTORS,
    GNGK_HW_ZC_REPLACEMENT_FIELDS,
)


SCREENSHOT_SHAPED_DOC = """
中华人民共和国
上海东松医疗科技股份有限公司

信息系统开发运维服务
国内公开招标采购
招标文件

招标编号： 0811-DSITC253677
招标人：上海市皮肤病医院
招标代理机构：上海东松医疗科技股份有限公司

1、上海市皮肤病医院已落实一笔资金，用于支付信息系统开发运维服务采购的费用。

2、项目基本信息
上海东松医疗科技股份有限公司受上海市皮肤病医院的委托，现以公开招标方式邀请合格的投标人就下列所提供的服务前来投标。

项目名称：信息系统开发运维服务          壹套（项目预算：人民币50万元）
项目实施地点：采购人指定地点
服务期限：合同签订后12个月内完成系统上线。

3、合格投标人资格条件

招标代理机构：上海东松医疗科技股份有限公司
地址：上海市宁波路1号申华金融大厦11楼
邮编：200002
联系人：史倩倩、陈雯婷
电话：021-63230480 转8607、8619
传真：021-63299235
电子邮箱：shiqianqian@dongsong-cn.com

投标保证金数额：
项目预算的2%。
户名：
上海东松医疗科技股份有限公司

招标人、招标代理机构均将通过“中国采购与招标网”（https://www.chinabidding.cn/）公开发布。
""".strip()


def test_extract_gngk_project_name_falls_back_to_cover_body() -> None:
    log_parts: list[str] = []

    extracted = extract_gngk_project_name(
        SCREENSHOT_SHAPED_DOC,
        "",
        {"project_name": "新项目名称"},
        log_parts,
    )

    assert extracted == "信息系统开发运维服务"


def test_extract_gngk_project_number_falls_back_to_body_bid_number() -> None:
    log_parts: list[str] = []

    extracted = extract_gngk_project_number(
        SCREENSHOT_SHAPED_DOC,
        "",
        {"project_number": "253000"},
        log_parts,
    )

    assert extracted == "253677"


def test_extract_gngk_project_name_keeps_header_priority() -> None:
    log_parts: list[str] = []

    extracted = extract_gngk_project_name(
        SCREENSHOT_SHAPED_DOC,
        "项目名称：页眉项目采购；招标编号：0811-DSITC000001",
        {"project_name": "新项目名称"},
        log_parts,
    )

    assert extracted == "页眉项目"


def test_extract_gngk_fw_zc_project_content_keeps_service_line_with_budget() -> None:
    log_parts: list[str] = []

    extracted = extract_gngk_fw_zc_project_content(
        SCREENSHOT_SHAPED_DOC,
        {"project_content": "新项目内容"},
        log_parts,
    )

    assert extracted == "项目名称：信息系统开发运维服务          壹套（项目预算：人民币50万元）"


def test_extract_public_tender_buyer_name_matches_service_template() -> None:
    log_parts: list[str] = []

    extracted = extract_public_tender_buyer_name(
        SCREENSHOT_SHAPED_DOC,
        {"buyer_name": "新采购人"},
        log_parts,
    )

    assert extracted == "上海市皮肤病医院"


def test_extract_public_tender_buyer_name_supports_procurement_label() -> None:
    log_parts: list[str] = []

    extracted = extract_public_tender_buyer_name(
        "采购人：复旦大学附属中山医院\n采购代理机构：上海东松医疗科技股份有限公司",
        {"buyer_name": "新采购人"},
        log_parts,
    )

    assert extracted == "复旦大学附属中山医院"


def test_extract_public_tender_buyer_name_supports_bidder_label() -> None:
    log_parts: list[str] = []

    extracted = extract_public_tender_buyer_name(
        "招标人：复旦大学附属中山医院\n招标代理机构：上海东松医疗科技股份有限公司",
        {"buyer_name": "新采购人"},
        log_parts,
    )

    assert extracted == "复旦大学附属中山医院"


def test_extract_public_tender_investment_reads_budget_amount_only() -> None:
    log_parts: list[str] = []

    extracted = extract_public_tender_investment(
        "预算金额：450 万元（人民币）\n最高限价：450 万元",
        {"investment": "140.0"},
        log_parts,
    )

    assert extracted == "450"


def test_extract_public_tender_investment_ignores_ceiling_amount() -> None:
    log_parts: list[str] = []

    extracted = extract_public_tender_investment(
        "最高限价：450 万元",
        {"investment": "140.0"},
        log_parts,
    )

    assert extracted is None


def test_format_public_tender_investment_value_strips_only_invalid_trailing_zeroes() -> None:
    assert format_public_tender_investment_value("140.0") == "140"
    assert format_public_tender_investment_value("140.5") == "140.5"
    assert format_public_tender_investment_value("140.05") == "140.05"


def test_extract_public_tender_contact_fields_matches_service_template() -> None:
    log_parts: list[str] = []

    extracted = extract_public_tender_contact_fields(
        SCREENSHOT_SHAPED_DOC,
        {
            "project_zbr_xbr": "新主办协办",
            "zbr_xbr_tel": "新电话",
            "zbr_pinyin": "newpinyin",
        },
        log_parts,
    )

    assert extracted == ("史倩倩、陈雯婷", "8607、8619", "shiqianqian")


@pytest.mark.parametrize(
    "stop_fragment",
    [
        "电话：021-63230480 转8607、8619",
        "电 话：021-63230480 转8607、8619",
        "传真：021-63299235",
        "邮箱：shiqianqian@dongsong-cn.com",
        "电子邮箱：shiqianqian@dongsong-cn.com",
    ],
)
def test_extract_public_tender_project_contact_stops_before_contact_labels(
    stop_fragment: str,
) -> None:
    doc_content = f"""
招标代理机构：上海东松医疗科技股份有限公司
地址：上海市宁波路1号申华金融大厦11楼
邮编：200002
项目联系人：史倩倩、刘宇昂 {stop_fragment}
""".strip()
    log_parts: list[str] = []

    project_zbr_xbr, _, _ = extract_public_tender_contact_fields(
        doc_content,
        {"project_zbr_xbr": "新主办协办"},
        log_parts,
    )

    assert project_zbr_xbr == "史倩倩、刘宇昂"


def test_extract_public_tender_contact_fields_supports_generic_contact_before_spaced_phone() -> None:
    doc_content = """
招标代理机构：上海东松医疗科技股份有限公司
地址：上海市宁波路1号申华金融大厦11楼
邮编：200002
联系人：史倩倩、刘宇昂
电 话：021-63230480 转8607、8619
传真：021-63299235
电子邮箱：shiqianqian@dongsong-cn.com
""".strip()
    log_parts: list[str] = []

    extracted = extract_public_tender_contact_fields(
        doc_content,
        {
            "project_zbr_xbr": "新主办协办",
            "zbr_xbr_tel": "新电话",
            "zbr_pinyin": "newpinyin",
        },
        log_parts,
    )

    assert extracted == ("史倩倩、刘宇昂", "8607、8619", "shiqianqian")


def test_extract_public_tender_bzj_rule_matches_service_template() -> None:
    log_parts: list[str] = []

    extracted = extract_public_tender_bzj_rule(
        SCREENSHOT_SHAPED_DOC,
        {"bzj_rule": "新保证金规则"},
        log_parts,
    )

    assert extracted == "项目预算的2%"


def test_extract_public_tender_platform_matches_service_template() -> None:
    log_parts: list[str] = []

    extracted = extract_public_tender_platform(
        SCREENSHOT_SHAPED_DOC,
        {"platform": "新平台"},
        log_parts,
    )

    assert extracted == "“中国采购与招标网”（https://www.chinabidding.cn/）"


def test_gngk_hw_and_fw_zc_replacement_fields_keep_type_boundary() -> None:
    hw_field_names = [spec.field_name for spec in GNGK_HW_ZC_REPLACEMENT_FIELDS]
    fw_field_names = [spec.field_name for spec in GNGK_FW_ZC_REPLACEMENT_FIELDS]
    hw_extractor_names = [spec.name for spec in GNGK_HW_ZC_EXTRACTORS]
    fw_extractor_names = [spec.name for spec in GNGK_FW_ZC_EXTRACTORS]

    assert "project_content" in hw_field_names
    assert "project_content" in hw_extractor_names
    assert "investment" in hw_field_names
    assert "investment" in hw_extractor_names
    assert "project_content_v1" not in hw_field_names
    assert "similar_project_performance_date" not in hw_field_names
    assert "project_content_v1" not in fw_field_names
    assert "similar_project_performance_date" not in fw_field_names
    assert "project_content_v1" not in hw_extractor_names
    assert "similar_project_performance_date" not in hw_extractor_names
    assert "project_content_v1" not in fw_extractor_names
    assert "similar_project_performance_date" not in fw_extractor_names


def _call_mock_extractor(extract_callable, doc_content: str, state, log_parts):
    params = [
        parameter
        for parameter in inspect.signature(extract_callable).parameters.values()
        if parameter.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    ]
    if len(params) >= 4:
        return extract_callable(doc_content, "", state, log_parts)
    return extract_callable(doc_content, state, log_parts)


def test_gngk_hw_zc_mock_replacement_run_omits_removed_special_fields(
    monkeypatch,
) -> None:
    doc_content = """
国内公开招标采购
招标人：复旦大学附属中山医院
招标代理机构：上海东松医疗科技股份有限公司

2、项目基本信息
上海东松医疗科技股份有限公司受复旦大学附属中山医院的委托，现以公开招标方式邀请合格的投标人就下列货物或服务前来投标。
设备名称及数量：旧设备/壹套
项目预算：人民币450万元
预算金额：450 万元（人民币）

3、合格投标人资格条件

招标代理机构：上海东松医疗科技股份有限公司
地址：上海市宁波路1号申华金融大厦11楼
邮编：200002
项目联系人：史倩倩、刘宇昂
电话：021-63230480 转8607、8619
传真：021-63299235
电子邮箱：shiqianqian@dongsong-cn.com
""".strip()

    def fake_run_get_replacements(
        state,
        config,
        extractors,
        replacement_fields,
    ):
        del config
        placeholder_mapping = {}
        log_parts: list[str] = []

        for spec in extractors:
            if not spec.enabled_if(state):
                continue
            result = _call_mock_extractor(
                spec.extract_callable,
                doc_content,
                state,
                log_parts,
            )
            if spec.output_field_names is not None and isinstance(result, tuple):
                for field_name, value in zip(spec.output_field_names, result):
                    if value:
                        placeholder_mapping[field_name] = value
            elif result:
                placeholder_mapping[spec.name] = (
                    result[0] if isinstance(result, tuple) else result
                )

        replacements = []
        for field_spec in replacement_fields:
            old_value = placeholder_mapping.get(field_spec.field_name)
            if not old_value:
                continue

            new_value = state.get(field_spec.field_name)
            if not new_value and field_spec.fallback_fields:
                for fallback_field in field_spec.fallback_fields:
                    new_value = state.get(fallback_field)
                    if new_value:
                        break
            if not new_value:
                continue

            if field_spec.new_value_formatter is not None:
                new_value = field_spec.new_value_formatter(new_value)
                if not new_value:
                    continue
            if field_spec.skip_if_equal and old_value == new_value:
                continue
            replacements.append((old_value, new_value))

        return {
            "placeholder_mapping": placeholder_mapping,
            "replacements": replacements,
            "replacement_log": "; ".join(log_parts),
        }

    monkeypatch.setattr(
        hw_zc_module,
        "run_get_replacements",
        fake_run_get_replacements,
    )

    result = hw_zc_module.gngk_hw_zc_get_replacements(
        {
            "prepared_doc_path": "mock.doc",
            "project_content": "设备名称及数量：新设备/壹套",
            "buyer_name": "上海交通大学医学院附属瑞金医院",
            "investment": "140.0",
            "project_zbr_xbr": "新联系人",
            "project_content_v1": "不应参与替换",
            "similar_project_performance_date": "不应参与替换",
        },
        config=None,
    )

    placeholder_mapping = result["placeholder_mapping"]
    replacements = result["replacements"]

    assert placeholder_mapping["project_content"] == "设备名称及数量：旧设备/壹套"
    assert placeholder_mapping["buyer_name"] == "复旦大学附属中山医院"
    assert placeholder_mapping["investment"] == "450"
    assert placeholder_mapping["project_zbr_xbr"] == "史倩倩、刘宇昂"
    assert "project_content_v1" not in placeholder_mapping
    assert "similar_project_performance_date" not in placeholder_mapping
    assert ("设备名称及数量：旧设备/壹套", "设备名称及数量：新设备/壹套") in replacements
    assert ("复旦大学附属中山医院", "上海交通大学医学院附属瑞金医院") in replacements
    assert ("450", "140") in replacements
    assert ("史倩倩、刘宇昂", "新联系人") in replacements
    assert all("不应参与替换" not in value for pair in replacements for value in pair)
