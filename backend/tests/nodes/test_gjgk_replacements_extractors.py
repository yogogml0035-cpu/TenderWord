from __future__ import annotations

from backend.nodes.common_word_nodes.get_replacements_shared import (
    extract_public_tender_bzj_rule,
    extract_public_tender_contact_fields,
)
from backend.nodes.gjgk_word_nodes.gjgk_get_replacements import (
    extract_gjgk_project_content,
)


def test_extract_public_tender_contact_fields_supports_mailbox_label_for_pinyin() -> None:
    doc_content = """
采购代理机构名称：上海东松医疗科技股份有限公司
邮编：200002
邮箱：liu@dongsong-cn.com
""".strip()
    log_parts: list[str] = []

    _, _, zbr_pinyin = extract_public_tender_contact_fields(
        doc_content,
        {"zbr_pinyin": "xuxudong"},
        log_parts,
    )

    assert zbr_pinyin == "liu"


def test_extract_public_tender_bzj_rule_supports_inline_sentence_pattern() -> None:
    doc_content = """
★15.1
投标保证金金额：项目预算的1.5%。
投标保证金有效期应当与投标有效期一致。
""".strip()
    log_parts: list[str] = []

    extracted = extract_public_tender_bzj_rule(
        doc_content,
        {"bzj_rule": "项目预算的2%"},
        log_parts,
    )

    assert extracted == "项目预算的1.5%"


def test_extract_public_tender_bzj_rule_prefers_original_marker_range() -> None:
    doc_content = """
投标保证金数额：项目预算的2%。
户名：上海东松医疗科技股份有限公司
""".strip()
    log_parts: list[str] = []

    extracted = extract_public_tender_bzj_rule(
        doc_content,
        {"bzj_rule": "项目预算的3%"},
        log_parts,
    )

    assert extracted == "项目预算的2%"


def test_extract_gjgk_project_content_until_technical_requirement_section() -> None:
    doc_content = """
1、本项目所需资金的来源均已落实。
2、招标内容
（1）设备名称及数量：
ERCP专用X线透视摄影系统等设备壹套
（项目预算：人民币210万元，可以采购进口产品）
（2）技术要求：见本招标文件第八章“货物需求一览表及技术规格”
3、合格投标人资格条件
""".strip()
    log_parts: list[str] = []

    extracted = extract_gjgk_project_content(
        doc_content,
        {"project_content": "new project content"},
        log_parts,
    )

    assert extracted is not None
    assert "ERCP专用X线透视摄影系统等设备壹套" in extracted
    assert "（项目预算：人民币210万元，可以采购进口产品）" in extracted
    assert "（2）技术要求" not in extracted
