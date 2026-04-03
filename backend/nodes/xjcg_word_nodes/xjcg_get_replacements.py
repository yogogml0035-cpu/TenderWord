from __future__ import annotations

import pathlib
import re
import sys
from typing import List, Optional, Tuple

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.nodes.common_word_nodes.get_replacements_core import (
    ExtractorSpec,
    ReplacementFieldSpec,
    run_get_replacements,
)
from backend.nodes.common_word_nodes.get_replacements_shared import (
    build_common_replacement_fields,
    extract_procurement_platform,
    extract_project_name,
    extract_project_number_from_project_header,
    extract_service_fee,
    extract_shell_dates,
    extract_submit_date,
)
from backend.states import XjcgTenderGraphState


def extract_buyer_name(
    doc_content: str, state: XjcgTenderGraphState, log_parts: List[str]
) -> Optional[str]:
    """从首页正文中提取 buyer_name"""
    if not doc_content or not state.get("buyer_name"):
        return None

    first_page_content = doc_content[:5000] if len(doc_content) > 5000 else doc_content
    buyer_pos = doc_content.find("采购人")
    if buyer_pos != -1:
        search_start = max(0, buyer_pos - 100)
        search_end = min(len(doc_content), buyer_pos + 2000)
        first_page_content = doc_content[search_start:search_end]
        log_parts.append(
            f"在位置 {buyer_pos} 找到 '采购人'，在范围 [{search_start}, {search_end}] 中搜索"
        )
    else:
        log_parts.append("在文档中未找到 '采购人'，在前 5000 个字符中搜索")

    buyer_name_pattern = (
        r"采购人[:：]\s*([^\n\r]+?)(?:\s*\n\s*采购代理机构|采购代理机构)"
    )
    match = re.search(buyer_name_pattern, first_page_content, re.DOTALL)
    if match:
        extracted_buyer_name = match.group(1).strip()
        log_parts.append(f"从首页提取采购人名称: {extracted_buyer_name}")
        return extracted_buyer_name

    buyer_name_pattern2 = r"采购人[:：]\s*([^采购]+?)(?=\s*采购代理机构)"
    match2 = re.search(buyer_name_pattern2, first_page_content, re.DOTALL)
    if match2:
        extracted_buyer_name = match2.group(1).strip()
        log_parts.append(f"提取采购人名称 (备用模式): {extracted_buyer_name}")
        return extracted_buyer_name

    log_parts.append("在首页内容中未找到 '采购人' 模式")
    return None


def extract_project_content(
    doc_content: str, state: XjcgTenderGraphState, log_parts: List[str]
) -> Optional[str]:
    """从正文中提取 project_content"""
    if not doc_content or not state.get("project_content"):
        return None

    start_marker1 = "2、项目基本信息"
    start_pos1 = doc_content.find(start_marker1)

    if start_pos1 == -1:
        log_parts.append("未找到起始标记 '2、项目基本信息'")
        return None

    log_parts.append(f"在位置 {start_pos1} 找到起始标记1 '{start_marker1}'")

    start_marker2_pattern = (
        r"的委托[，,]\s*现以询价采购的方式就下列\s*货物和相关服务进行采购[。.]"
    )
    search_after_marker1 = start_pos1 + len(start_marker1)
    match = re.search(
        start_marker2_pattern, doc_content[search_after_marker1:], re.DOTALL
    )

    if not match:
        log_parts.append("在标记1之后未找到起始标记2模式")
        return None

    front_end_pos = search_after_marker1 + match.end()
    end_marker1 = "3、合格供应商资格条件"
    end_pos1 = doc_content.find(end_marker1, front_end_pos)

    if end_pos1 == -1:
        log_parts.append(f"未找到结束标记1 '{end_marker1}'")
        return None

    log_parts.append(f"在位置 {end_pos1} 找到结束标记1 '{end_marker1}'")

    end_markers = [
        "交付地点",
        "交付日期",
        "供应商",
        "项目交付地点",
        "项目交付日期",
        "3、合格供应商资格条件",
    ]

    found_positions = []
    for marker in end_markers:
        pos = doc_content.find(marker, front_end_pos, end_pos1 + len(end_marker1))
        if pos != -1:
            found_positions.append((pos, marker))
            log_parts.append(f"在位置 {pos} 找到结束标记 '{marker}'")

    if not found_positions:
        log_parts.append("在 front_end 和 end_marker1 之间未找到任何结束标记")
        return None

    earliest_pos, earliest_marker = min(found_positions, key=lambda item: item[0])
    log_parts.append(
        f"使用最早出现的结束标记 '{earliest_marker}' (位置: {earliest_pos})"
    )

    marker_line_start = earliest_pos
    while marker_line_start > front_end_pos and doc_content[
        marker_line_start - 1
    ] not in ["\n", "\r"]:
        marker_line_start -= 1

    log_parts.append(f"结束标记行起始位置: {marker_line_start}")

    content_start = front_end_pos
    while content_start < len(doc_content) and doc_content[content_start] in [
        "\n",
        "\r",
        " ",
        "\t",
    ]:
        content_start += 1

    log_parts.append(f"内容起始位置: {content_start}")

    raw_extracted = doc_content[content_start:marker_line_start]
    log_parts.append(f"原始提取长度: {len(raw_extracted)} 个字符")

    lines = raw_extracted.split("\n")
    cleaned_lines = []
    for line in lines:
        line_stripped = line.strip("\r")
        if line_stripped and not any(marker in line_stripped for marker in end_markers):
            cleaned_lines.append(line_stripped)

    extracted_content = "\n".join(cleaned_lines)

    if extracted_content:
        log_parts.append("成功提取项目内容")
        return extracted_content

    log_parts.append("清理后提取的内容为空")
    return None


def extract_bzj_rule(
    doc_content: str, state: XjcgTenderGraphState, log_parts: List[str]
) -> Optional[str]:
    """从正文中提取 bzj_rule"""
    if not doc_content or not state.get("bzj_rule"):
        return None

    section_marker = "18、保证金"
    section_pos = doc_content.find(section_marker)

    if section_pos == -1:
        log_parts.append(f"未找到节标记 '{section_marker}'")
        return None

    log_parts.append(f"在位置 {section_pos} 找到节标记 '{section_marker}'")

    search_start = section_pos + len(section_marker)
    search_end = min(len(doc_content), section_pos + 2000)
    search_range = doc_content[search_start:search_end]

    bzj_pattern = r"18\.1\s*保证金金额[:：]\s*([^。]+?)(?:[。]|$)"
    match = re.search(bzj_pattern, search_range, re.DOTALL)

    if match:
        extracted_bzj = match.group(1).strip()
        log_parts.append(f"提取保证金规则: {extracted_bzj}")
        return extracted_bzj

    bzj_pattern2 = r"18\.1\s*保证金金额[:：]\s*([^。\n]+?)(?:[。]\n\s*户名|$)"
    match2 = re.search(bzj_pattern2, search_range, re.DOTALL)
    if match2:
        extracted_bzj = match2.group(1).strip()
        log_parts.append(f"提取保证金规则 (备用模式): {extracted_bzj}")
        return extracted_bzj

    log_parts.append(f"在 '{section_marker}' 之后未找到 '18.1保证金金额：' 模式")
    return None


def extract_contact_fields(
    doc_content: str, state: XjcgTenderGraphState, log_parts: List[str]
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """从正文中提取 project_zbr_xbr, zbr_xbr_tel, zbr_pinyin"""
    if not doc_content:
        return None, None, None

    agency_marker = "采购代理机构名称："
    agency_pos = doc_content.find(agency_marker)

    if agency_pos == -1:
        log_parts.append("在文档中未找到 '采购代理机构名称：' 标记")
        return None, None, None

    log_parts.append(f"在位置 {agency_pos} 找到 '采购代理机构名称：' 标记")

    zipcode_marker = "邮编："
    zipcode_pos = doc_content.find(zipcode_marker, agency_pos)

    if zipcode_pos == -1:
        log_parts.append("在 '采购代理机构名称：' 之后未找到 '邮编：' 标记")
        search_start = agency_pos + len(agency_marker)
        search_end = min(len(doc_content), agency_pos + 2000)
    else:
        log_parts.append(f"在位置 {zipcode_pos} 找到 '邮编：' 标记")
        zipcode_line_end = zipcode_pos
        while zipcode_line_end < len(doc_content) and doc_content[
            zipcode_line_end
        ] not in ["\n", "\r"]:
            zipcode_line_end += 1
        while zipcode_line_end < len(doc_content) and doc_content[zipcode_line_end] in [
            "\n",
            "\r",
        ]:
            zipcode_line_end += 1
        search_start = zipcode_line_end
        search_end = min(len(doc_content), search_start + 2000)

    search_range = doc_content[search_start:search_end]
    log_parts.append(
        f"在范围 [{search_start}, {search_end}] 中搜索，内容长度: {len(search_range)}"
    )

    project_zbr_xbr = None
    zbr_xbr_tel = None
    zbr_pinyin = None

    if state.get("project_zbr_xbr"):
        contact_pattern = r"联系人[:：]\s*([^\n\r]+)"
        match = re.search(contact_pattern, search_range)
        if match:
            project_zbr_xbr = match.group(1).strip()
            log_parts.append(f"提取项目负责人/项目经办人: {project_zbr_xbr}")
        else:
            log_parts.append("在 '采购代理机构名称：' 部分之后未找到 '联系人' 模式")

    if state.get("zbr_xbr_tel"):
        tel_pattern = r"电话[:：]\s*[^\n\r]*转\s*([^\n\r]+)"
        match = re.search(tel_pattern, search_range)
        if match:
            zbr_xbr_tel = match.group(1).strip()
            log_parts.append(f"提取负责人/经办人电话: {zbr_xbr_tel}")
        else:
            log_parts.append("在 '采购代理机构名称：' 部分之后未找到 '电话...转' 模式")

    if state.get("zbr_pinyin"):
        email_pattern = r"电子邮箱[:：]\s*([^@\n\r]+)@"
        match = re.search(email_pattern, search_range)
        if match:
            zbr_pinyin = match.group(1).strip()
            log_parts.append(f"提取负责人拼音: {zbr_pinyin}")
        else:
            log_parts.append("在 '采购代理机构名称：' 部分之后未找到 '电子邮箱' 模式")

    return project_zbr_xbr, zbr_xbr_tel, zbr_pinyin


XJCG_EXTRACTORS: List[ExtractorSpec] = [
    ExtractorSpec(
        name="project_content",
        enabled_if=lambda state: state.get("project_content") is not None,
        extract_callable=extract_project_content,
    ),
    ExtractorSpec(
        name="project_number",
        enabled_if=lambda state: state.get("project_number") is not None,
        extract_callable=extract_project_number_from_project_header,
    ),
    ExtractorSpec(
        name="project_name",
        enabled_if=lambda state: state.get("project_name") is not None,
        extract_callable=extract_project_name,
    ),
    ExtractorSpec(
        name="bzj_rule",
        enabled_if=lambda state: state.get("bzj_rule") is not None,
        extract_callable=extract_bzj_rule,
    ),
    ExtractorSpec(
        name="buyer_name",
        enabled_if=lambda state: state.get("buyer_name") is not None,
        extract_callable=extract_buyer_name,
    ),
    ExtractorSpec(
        name="contact_fields",
        enabled_if=lambda state: any(
            [
                state.get("project_zbr_xbr"),
                state.get("zbr_xbr_tel"),
                state.get("zbr_pinyin"),
            ]
        ),
        extract_callable=extract_contact_fields,
        output_field_names=["project_zbr_xbr", "zbr_xbr_tel", "zbr_pinyin"],
    ),
    ExtractorSpec(
        name="shell_dates",
        enabled_if=lambda state: state.get("shell_start_date") is not None
        or state.get("shell_end_date") is not None,
        extract_callable=extract_shell_dates,
        output_field_names=["shell_start_date", "shell_end_date"],
    ),
    ExtractorSpec(
        name="submit_date",
        enabled_if=lambda state: state.get("submit_date") is not None,
        extract_callable=extract_submit_date,
    ),
    ExtractorSpec(
        name="platform",
        enabled_if=lambda state: state.get("platform") is not None,
        extract_callable=extract_procurement_platform,
    ),
    ExtractorSpec(
        name="service_fee",
        enabled_if=lambda state: state.get("service_fee") is not None,
        extract_callable=extract_service_fee,
    ),
]


XJCG_REPLACEMENT_FIELDS: List[ReplacementFieldSpec] = build_common_replacement_fields()


def xjcg_get_replacements(
    state: XjcgTenderGraphState, config
) -> XjcgTenderGraphState:
    """Thin wrapper around the shared get_replacements core."""
    return run_get_replacements(
        state=state,
        config=config,
        extractors=XJCG_EXTRACTORS,
        replacement_fields=XJCG_REPLACEMENT_FIELDS,
    )


if __name__ == "__main__":
    import pathlib
    import sys

    ROOT = pathlib.Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from backend.states import XjcgTenderGraphState

    test_doc_paths = ["test_doc\\五官科综合治疗台2502979-询价通知书-发售稿.doc"]

    for doc_idx, test_doc_path_str in enumerate(test_doc_paths, 1):
        test_doc_path = (ROOT / test_doc_path_str).resolve()

        print("\n" + "=" * 80)
        print(f"测试 {doc_idx}/{len(test_doc_paths)}: get_replacements 节点")
        print("=" * 80)
        print(f"测试文档路径: {test_doc_path}")
        print(f"文档是否存在: {test_doc_path.exists()}")
        print()

        if not test_doc_path.exists():
            print(f"警告: 文档不存在: {test_doc_path}，跳过此文件")
            print()
            continue

        test_state: XjcgTenderGraphState = {
            "prepared_doc_path": str(test_doc_path),
            "project_number": "253505",
            "project_name": "细胞电转仪",
            "project_content": "项目名称及数量：细胞电转仪   壹套",
            "bzj_rule": "项目预算的2%",
            "buyer_name": "复旦大学附属中山医院",
            "project_zbr_xbr": "徐旭东、任彧晟",
            "zbr_xbr_tel": "8605、8625",
            "zbr_pinyin": "xuxudong",
            "shell_start_date": "2025年12月12日",
            "shell_end_date": "2025年12月15日",
            "submit_date": "2025年12月12日11:00",
            "platform": "中国采购与招标网（https://www.chinabidding.cn/）",
            "service_fee": "百分之壹伍（1.5%）",
        }

        try:
            result_state = xjcg_get_replacements(test_state, config=None)

            placeholder_mapping = result_state.get("placeholder_mapping", {})
            if placeholder_mapping:
                print(f"\n找到 {len(placeholder_mapping)} 个占位符:\n")
                for field_name, placeholder_value in placeholder_mapping.items():
                    print(f"{field_name}: {repr(placeholder_value)}")
                    print()
            else:
                print("\n未找到任何占位符")

        except Exception as e:
            print(f"\n错误: {e}")
            import traceback

            traceback.print_exc()
            print("\n继续测试下一个文件...\n")
            continue
