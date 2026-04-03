from backend.nodes.common_word_nodes.get_replacements_shared import (
    build_common_replacement_fields,
    extract_public_tender_buyer_name,
    extract_public_tender_contact_fields,
    make_platform_extractor,
    make_project_number_extractor,
)
from backend.states import GngkTenderGraphState
from backend.util.common_util.tender_number import normalize_gjgk_project_number


def test_make_project_number_extractor_supports_custom_label():
    extractor = make_project_number_extractor("招标编号")
    log_parts: list[str] = []

    result = extractor(
        "",
        "招标编号：ABC-2025-007",
        {"project_number": "007"},
        log_parts,
    )

    assert result == "007"
    assert any("项目编号" in item for item in log_parts)


def test_make_project_number_extractor_accepts_custom_value_parser():
    extractor = make_project_number_extractor(
        "招标编号",
        value_parser=normalize_gjgk_project_number,
    )
    log_parts: list[str] = []

    result = extractor(
        "",
        "招标编号：0811-254DSITC2512",
        {"project_number": "264DSITC0639"},
        log_parts,
    )

    assert result == "254DSITC2512"
    assert any("254DSITC2512" in item for item in log_parts)


def test_make_platform_extractor_supports_multiple_start_markers():
    extractor = make_platform_extractor(
        ("招标人、招标代理机构均将通过", "采购人、采购代理机构均将通过")
    )
    log_parts: list[str] = []
    state = {"platform": "中国采购与招标网（https://example.com）"}

    result = extractor(
        "招标人、招标代理机构均将通过中国采购与招标网（https://example.com）公开发布",
        state,
        log_parts,
    )

    assert result == "中国采购与招标网（https://example.com）"
    assert any("发布平台" in item for item in log_parts)


def test_build_common_replacement_fields_returns_fresh_base_specs():
    first = build_common_replacement_fields()
    second = build_common_replacement_fields()

    assert [spec.field_name for spec in first] == [
        "project_content",
        "project_number",
        "project_name",
        "bzj_rule",
        "buyer_name",
        "project_zbr_xbr",
        "zbr_xbr_tel",
        "zbr_pinyin",
        "shell_start_date",
        "shell_end_date",
        "submit_date",
        "platform",
        "service_fee",
    ]
    assert first is not second
    assert first[0] is not second[0]


def test_extract_public_tender_buyer_name_reads_first_page_section():
    log_parts: list[str] = []
    state = GngkTenderGraphState(buyer_name="现值")

    result = extract_public_tender_buyer_name(
        "招标人：上海市第一人民医院\n招标代理机构：上海东松医疗科技股份有限公司",
        state,
        log_parts,
    )

    assert result == "上海市第一人民医院"
    assert any("招标人名称" in item for item in log_parts)


def test_extract_public_tender_contact_fields_prefers_anchor_pattern():
    log_parts: list[str] = []
    state = GngkTenderGraphState(
        project_zbr_xbr="目标联系人",
        zbr_xbr_tel="8605",
        zbr_pinyin="xuxudong",
    )

    result = extract_public_tender_contact_fields(
        (
            "采购代理机构名称：上海东松医疗科技股份有限公司\n"
            "邮编：200002\n"
            "联系人：[徐旭东]\n"
            "电话：021-63230480 转 8605\n"
            "传真：021-62411170\n"
            "电子邮箱：xuxudong@dongsong-cn.com"
        ),
        state,
        log_parts,
    )

    assert result == ("徐旭东", "8605", "xuxudong")
    assert any("按锚点提取负责人拼音" in item for item in log_parts)
