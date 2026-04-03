from backend.nodes.gjgk_word_nodes.gjgk_replace_content import (
    build_gjgk_special_replacements,
    extract_delivery_location_from_polished_text,
)
from backend.states import TenderGraphStateBase


def test_extract_delivery_location_from_polished_text_supports_supported_prefixes():
    assert (
        extract_delivery_location_from_polished_text("交货地点：上海市浦东新区")
        == "上海市浦东新区"
    )
    assert (
        extract_delivery_location_from_polished_text("项目现场: 北京市海淀区")
        == "北京市海淀区"
    )


def test_build_gjgk_special_replacements_distinguishes_comment_sources():
    entries, derived_updates, log_parts = build_gjgk_special_replacements(
        TenderGraphStateBase(
            fund_source_lx="1",
            tender_invitation="项目名称：国际项目，招标编号：GJ-001",
            polished_text="第一段\n交付地点：上海市浦东新区金科路 1 号",
            placeholder_mapping={
                "fund_source_lx": "自筹资金",
                "tender_invitation": "项目名称：历史项目，招标编号：OLD-001",
                "delivery_location": "北京市海淀区",
            },
        )
    )

    assert derived_updates["delivery_location"] == "上海市浦东新区金科路 1 号"
    assert [(entry.search_text, entry.replace_text, entry.comment_label) for entry in entries] == [
        ("自筹资金", "财政资金", "ERP数据"),
        ("项目名称：历史项目，招标编号：OLD-001", "项目名称：国际项目，招标编号：GJ-001", "ERP数据"),
        ("北京市海淀区", "上海市浦东新区金科路 1 号", "技术参数数据"),
    ]
    assert log_parts == []


def test_build_gjgk_special_replacements_keeps_template_delivery_when_not_extracted():
    entries, derived_updates, log_parts = build_gjgk_special_replacements(
        TenderGraphStateBase(
            fund_source_lx="9",
            tender_invitation="项目名称：国际项目，招标编号：GJ-001",
            polished_text="没有交货地点",
            placeholder_mapping={
                "delivery_location": "原模板地点",
            },
        )
    )

    assert entries == []
    assert derived_updates["delivery_location"] == "原模板地点"
    assert any("保留模板原值" in item for item in log_parts)
