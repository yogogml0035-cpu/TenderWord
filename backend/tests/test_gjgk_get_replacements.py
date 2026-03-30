from backend.nodes.gjgk_word_nodes.gjgk_get_replacements import (
    extract_delivery_location,
    extract_fund_source_lx,
    extract_tender_invitation,
)
from backend.states import GjgkTenderGraphState


def test_extract_fund_source_lx_reads_business_value():
    log_parts: list[str] = []
    state = GjgkTenderGraphState(fund_source_lx="1")

    result = extract_fund_source_lx(
        "资金来源：财政资金\r\n其他内容",
        state,
        log_parts,
    )

    assert result == "财政资金"
    assert any("fund_source_lx" in item for item in log_parts)


def test_extract_tender_invitation_reads_full_line():
    log_parts: list[str] = []
    state = GjgkTenderGraphState(
        tender_invitation="项目名称：国际项目，招标编号：GJ-001"
    )

    result = extract_tender_invitation(
        "项目名称：历史项目，招标编号：OLD-001\r\n第二行",
        state,
        log_parts,
    )

    assert result == "项目名称：历史项目，招标编号：OLD-001"


def test_extract_delivery_location_supports_multiple_labels():
    log_parts: list[str] = []

    result = extract_delivery_location(
        "项目现场：上海市浦东新区金科路 1 号\r\n其他内容",
        GjgkTenderGraphState(),
        log_parts,
    )

    assert result == "上海市浦东新区金科路 1 号"
