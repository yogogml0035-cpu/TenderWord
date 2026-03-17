from __future__ import annotations

import os
import re
import time
from typing import Dict, List, Optional, Tuple
import pathlib
import sys

# 添加项目根目录到 sys.path
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.states import XjcgTenderGraphState
from backend.nodes.common_word_nodes.get_replacements_core import (
    run_get_replacements,
    ExtractorSpec,
    ReplacementFieldSpec,
)
from backend.util.word_util import wdFindStop


# 提取函数：每个字段的查找逻辑
def extract_project_number(
    doc_content: str,
    first_page_header: str,
    state: XjcgTenderGraphState,
    log_parts: List[str],
) -> Optional[str]:
    """从页眉中提取 project_number"""
    if not first_page_header or not state.get("project_number"):
        return None

    project_number_pattern = r"项目编号[:：]\s*([^；;]+)"
    match = re.search(project_number_pattern, first_page_header)
    if match:
        number_text = match.group(1).strip()
        number_match = re.search(r"(\d+)$", number_text)
        if number_match:
            extracted_number = number_match.group(1)
            log_parts.append(
                f"从页眉中提取项目编号: {extracted_number} (来源: {number_text})"
            )
            return extracted_number
        else:
            log_parts.append(f"无法从项目编号文本中提取数字: {number_text}")
    else:
        log_parts.append("在页眉中未找到 '项目编号' 模式")
    return None


def extract_project_name(
    doc_content: str,
    first_page_header: str,
    state: XjcgTenderGraphState,
    log_parts: List[str],
) -> Optional[str]:
    """从页眉中提取 project_name"""
    if not first_page_header or not state.get("project_name"):
        return None

    project_name_pattern = r"项目名称[:：]\s*([^；;]+)"
    match = re.search(project_name_pattern, first_page_header)
    if match:
        extracted_name = match.group(1).strip()
        extracted_name = re.sub(r"采购$", "", extracted_name).strip()
        log_parts.append(f"从页眉中提取项目名称: {extracted_name}")
        return extracted_name
    else:
        log_parts.append("在页眉中未找到 '项目名称' 模式")
    return None


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
    else:
        buyer_name_pattern2 = r"采购人[:：]\s*([^采购]+?)(?=\s*采购代理机构)"
        match2 = re.search(buyer_name_pattern2, first_page_content, re.DOTALL)
        if match2:
            extracted_buyer_name = match2.group(1).strip()
            log_parts.append(f"提取采购人名称 (备用模式): {extracted_buyer_name}")
            return extracted_buyer_name
        else:
            log_parts.append(f"在首页内容中未找到 '采购人' 模式")
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
        log_parts.append(f"在标记1之后未找到起始标记2模式")
        return None

    front_end_pos = search_after_marker1 + match.end()
    end_marker1 = "3、合格供应商资格条件"
    end_pos1 = doc_content.find(end_marker1, front_end_pos)

    if end_pos1 == -1:
        log_parts.append(f"未找到结束标记1 '{end_marker1}'")
        return None

    log_parts.append(f"在位置 {end_pos1} 找到结束标记1 '{end_marker1}'")

    # 定义所有可能的结束标记
    end_markers = [
        "交付地点",
        "交付日期",
        "供应商",
        "项目交付地点",
        "项目交付日期",
        "3、合格供应商资格条件",
    ]

    # 在 front_end_pos 和 end_pos1 之间查找所有结束标记
    found_positions = []
    for marker in end_markers:
        pos = doc_content.find(marker, front_end_pos, end_pos1 + len(end_marker1))
        if pos != -1:
            found_positions.append((pos, marker))
            log_parts.append(f"在位置 {pos} 找到结束标记 '{marker}'")

    if not found_positions:
        log_parts.append(f"在 front_end 和 end_marker1 之间未找到任何结束标记")
        return None

    # 找到最早出现的结束标记
    earliest_pos, earliest_marker = min(found_positions, key=lambda x: x[0])
    log_parts.append(
        f"使用最早出现的结束标记 '{earliest_marker}' (位置: {earliest_pos})"
    )

    # 找到该标记所在行的起始位置
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
        # 排除包含任何结束标记的行
        if line_stripped and not any(marker in line_stripped for marker in end_markers):
            cleaned_lines.append(line_stripped)

    extracted_content = "\n".join(cleaned_lines)

    if extracted_content:
        log_parts.append(f"成功提取项目内容")
        return extracted_content
    else:
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
    else:
        bzj_pattern2 = r"18\.1\s*保证金金额[:：]\s*([^。\n]+?)(?:[。]\n\s*户名|$)"
        match2 = re.search(bzj_pattern2, search_range, re.DOTALL)
        if match2:
            extracted_bzj = match2.group(1).strip()
            log_parts.append(f"提取保证金规则 (备用模式): {extracted_bzj}")
            return extracted_bzj
        else:
            log_parts.append(
                f"在 '{section_marker}' 之后未找到 '18.1保证金金额：' 模式"
            )
    return None


def extract_shell_dates(
    doc_content: str, state: XjcgTenderGraphState, log_parts: List[str]
) -> Tuple[Optional[str], Optional[str]]:
    if not doc_content or (
        not state.get("shell_start_date") and not state.get("shell_end_date")
    ):
        return None, None

    start_marker = "4、获取询价通知书方式"
    end_marker = "（1）关注微信公众号"

    start_pos = doc_content.find(start_marker)

    if start_pos == -1:
        log_parts.append("未找到起始标记 '4、获取询价通知书方式'")
        return None, None

    log_parts.append(f"在位置 {start_pos} 找到起始标记 '{start_marker}'")

    search_after = start_pos + len(start_marker)
    end_pos = doc_content.find(end_marker, search_after)

    if end_pos == -1:
        log_parts.append(f"未找到结束标记 '{end_marker}'")
        return None, None

    log_parts.append(f"在位置 {end_pos} 找到结束标记 '{end_marker}'")

    search_range = doc_content[search_after:end_pos]
    log_parts.append(f"找到售标时间说明范围，长度: {len(search_range)} 个字符")

    shell_start_date = None
    shell_end_date = None

    if state.get("shell_start_date"):
        time_patterns_start = [
            r"(\d{4}年\d{1,2}月\d{1,2}日\s*起)",
            r"(\d{4}年\s*月\s*日\s*起)",
            r"(\s*年\s*月\s*日\s*起)",
        ]
        for time_pattern in time_patterns_start:
            match = re.search(time_pattern, search_range, re.DOTALL)
            if match:
                shell_start_date = match.group(1).strip()
                log_parts.append(f"提取售标开始时间: {shell_start_date}")
                break
        if shell_start_date is None:
            log_parts.append("在售标时间说明范围内未找到售标开始时间模式")

    if state.get("shell_end_date"):
        time_patterns_end = [
            r"(\d{4}年\d{1,2}月\d{1,2}日\s*止)",
            r"(\d{4}年\s*月\s*日\s*止)",
            r"(\s*年\s*月\s*日\s*止)",
        ]
        for time_pattern in time_patterns_end:
            match = re.search(time_pattern, search_range, re.DOTALL)
            if match:
                shell_end_date = match.group(1).strip()
                log_parts.append(f"提取售标结束时间: {shell_end_date}")
                break
        if shell_end_date is None:
            log_parts.append("在售标时间说明范围内未找到售标结束时间模式")

    return shell_start_date, shell_end_date


def extract_submit_date(
    doc_content: str, state: XjcgTenderGraphState, log_parts: List[str]
) -> Optional[str]:
    """从正文中提取 submit_date (递交文件时间)"""
    if not doc_content or not state.get("submit_date"):
        return None

    start_marker = "截止时间："
    end_marker = "地点："

    start_pos = doc_content.find(start_marker)

    if start_pos == -1:
        log_parts.append("未找到起始标记 '截止时间：'")
        return None

    log_parts.append(f"在位置 {start_pos} 找到起始标记 '{start_marker}'")

    search_after = start_pos + len(start_marker)
    end_pos = doc_content.find(end_marker, search_after)

    if end_pos == -1:
        log_parts.append("未找到结束标记 '地点：'")
        return None

    log_parts.append(f"在位置 {end_pos} 找到结束标记 '{end_marker}'")

    search_range = doc_content[search_after:end_pos]
    log_parts.append(
        f"在 '截止时间：' 和 '地点：' 之间搜索递交文件时间，范围长度: {len(search_range)} 个字符"
    )

    time_patterns = [
        r"(\d{4}年\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{2})",
        r"(\d{4}年\s*月\s*日\s*\d{1,2}:\d{2})",
        r"(\s*年\s*月\s*日\s*\d{1,2}:\d{2})",
    ]
    extracted_date = None
    for time_pattern in time_patterns:
        match = re.search(time_pattern, search_range, re.DOTALL)
        if match:
            extracted_date = match.group(1).strip()
            break

    if extracted_date:
        log_parts.append(f"提取递交文件时间: {extracted_date}")
        return extracted_date
    else:
        log_parts.append("在 '截止时间：' 和 '地点：' 范围内未找到递交文件时间模式")
    return None


def extract_platform(
    doc_content: str, state: XjcgTenderGraphState, log_parts: List[str]
) -> Optional[str]:
    """从正文中提取 platform (发布平台)"""
    if not doc_content or not state.get("platform"):
        return None

    start_marker = "采购人、采购代理机构均将通过"
    end_marker = "公开发布"

    start_pos = doc_content.find(start_marker)
    if start_pos == -1:
        log_parts.append("未找到起始标记 '采购人、采购代理机构均将通过'")
        return None

    log_parts.append(f"在位置 {start_pos} 找到起始标记 '{start_marker}'")

    search_after = start_pos + len(start_marker)
    end_pos = doc_content.find(end_marker, search_after)

    if end_pos == -1:
        log_parts.append("未找到结束标记 '公开发布'")
        return None

    log_parts.append(f"在位置 {end_pos} 找到结束标记 '{end_marker}'")

    search_range = doc_content[search_after:end_pos]
    log_parts.append(
        f"在 '采购人、采购代理机构均将通过' 和 '公开发布' 之间搜索发布平台，范围长度: {len(search_range)} 个字符"
    )

    platform_pattern = r"\s*([^（(]+)\s*[（(]([^）)]+)[）)]"
    match = re.search(platform_pattern, search_range, re.DOTALL)

    if match:
        platform_name = match.group(1).strip()
        platform_url = match.group(2).strip()
        extracted_platform = f"{platform_name}（{platform_url}）"
        log_parts.append(f"提取发布平台: {extracted_platform}")
        return extracted_platform
    else:
        log_parts.append("在文档中未找到发布平台模式")
    return None


def extract_service_fee(
    doc_content: str, state: XjcgTenderGraphState, log_parts: List[str]
) -> Optional[str]:
    """从正文中提取 service_fee (服务费)"""
    if not doc_content or not state.get("service_fee"):
        return None

    # 先找到服务费说明的范围
    start_marker = "标准和规定交纳代理服务费"
    end_marker = "成交供应商在接受成交通知书的同时需向采购代理机构一次性付清代理服务费"

    start_pos = doc_content.find(start_marker)
    end_pos = doc_content.find(end_marker)

    if start_pos == -1:
        log_parts.append("未找到起始标记 '标准和规定交纳代理服务费'")
        return None

    if end_pos == -1:
        log_parts.append(
            "未找到结束标记 '成交供应商在接受成交通知书的同时需向采购代理机构一次性付清代理服务费'"
        )
        return None

    # 提取范围内的内容
    search_range = doc_content[start_pos:end_pos]
    log_parts.append(f"找到服务费说明范围，位置: {start_pos}-{end_pos}")

    # 在范围内查找服务费相关模式
    fee_pattern = r"百分之([\u4e00-\u9fa5]+\s*\([^)]+\))"
    match = re.search(fee_pattern, search_range)

    if match:
        extracted_fee = "百分之" + match.group(1)
        log_parts.append(f"提取服务费: {extracted_fee}")
        return extracted_fee
    else:
        # 尝试其他模式
        fee_pattern2 = r"服务费为成交金额的\s*([^。]+)"
        match2 = re.search(fee_pattern2, search_range)
        if match2:
            extracted_fee = match2.group(1).strip()
            log_parts.append(f"提取服务费 (备用模式): {extracted_fee}")
            return extracted_fee
        else:
            log_parts.append("在服务费说明范围内未找到服务费模式")
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
        log_parts.append(f"在文档中未找到 '采购代理机构名称：' 标记")
        return None, None, None

    log_parts.append(f"在位置 {agency_pos} 找到 '采购代理机构名称：' 标记")

    zipcode_marker = "邮编："
    zipcode_pos = doc_content.find(zipcode_marker, agency_pos)

    if zipcode_pos == -1:
        log_parts.append(f"在 '采购代理机构名称：' 之后未找到 '邮编：' 标记")
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


# =============================================================================
# Extractor 配置列表
# =============================================================================

XJCG_EXTRACTORS: List[ExtractorSpec] = [
    ExtractorSpec(
        name="project_content",
        enabled_if=lambda state: state.get("project_content") is not None,
        extract_callable=extract_project_content,
    ),
    ExtractorSpec(
        name="project_number",
        enabled_if=lambda state: state.get("project_number") is not None,
        extract_callable=extract_project_number,
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
        extract_callable=extract_platform,
    ),
    ExtractorSpec(
        name="service_fee",
        enabled_if=lambda state: state.get("service_fee") is not None,
        extract_callable=extract_service_fee,
    ),
]


# =============================================================================
# Replacement Fields 配置列表
# =============================================================================

XJCG_REPLACEMENT_FIELDS: List[ReplacementFieldSpec] = [
    ReplacementFieldSpec(field_name="project_content"),
    ReplacementFieldSpec(field_name="project_number"),
    ReplacementFieldSpec(field_name="project_name"),
    ReplacementFieldSpec(field_name="bzj_rule"),
    ReplacementFieldSpec(field_name="buyer_name"),
    ReplacementFieldSpec(field_name="project_zbr_xbr"),
    ReplacementFieldSpec(field_name="zbr_xbr_tel"),
    ReplacementFieldSpec(field_name="zbr_pinyin"),
    ReplacementFieldSpec(field_name="shell_start_date"),
    ReplacementFieldSpec(field_name="shell_end_date"),
    ReplacementFieldSpec(field_name="submit_date"),
    ReplacementFieldSpec(field_name="platform"),
    ReplacementFieldSpec(field_name="service_fee"),
]


# =============================================================================
# 主函数（薄封装）
# =============================================================================


def get_replacements(state: XjcgTenderGraphState, config) -> XjcgTenderGraphState:
    """
    在 Word 文档中查找需要替换的占位符，并根据 state 中的字段建立映射关系。

    这个节点会：
    1. 打开 prepared_doc_path 的 Word 文档
    2. 读取文档内容，查找所有可能的占位符
    3. 根据 state 中的字段查找对应的占位符
    4. 将找到的占位符信息保存到 state 中，并生成替换列表

    这是一个薄封装，实际逻辑由 run_get_replacements 处理。
    """
    return run_get_replacements(
        state=state,
        config=config,
        extractors=XJCG_EXTRACTORS,
        replacement_fields=XJCG_REPLACEMENT_FIELDS,
    )


if __name__ == "__main__":
    """
    测试模块：测试从指定文档中提取占位符的功能
    """
    import pathlib
    import sys

    # 添加项目根目录到路径，以便导入模块
    ROOT = pathlib.Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    # 重新导入必要的模块（从项目根目录直接导入）
    from backend.states import XjcgTenderGraphState

    # 测试文档路径列表
    test_doc_paths = ["test_doc\五官科综合治疗台2502979-询价通知书-发售稿.doc"]

    # 循环测试每个文件
    for doc_idx, test_doc_path_str in enumerate(test_doc_paths, 1):
        # 基于项目根目录解析路径
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

        # 创建测试状态
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
            # 调用 get_replacements 函数
            result_state = get_replacements(test_state, config=None)

            placeholder_mapping = result_state.get("placeholder_mapping", {})
            if placeholder_mapping:
                print(f"\n找到 {len(placeholder_mapping)} 个占位符:\n")
                for field_name, placeholder_value in placeholder_mapping.items():
                    # 显示占位符内容，如果包含换行符则保持原格式
                    print(f"{field_name}: {repr(placeholder_value)}")
                    print()
            else:
                print("\n未找到任何占位符")

            # 打印日志
            # replacement_log = result_state.get("replacement_log", "")
            # if replacement_log:
            #     print("\n" + "=" * 80)
            #     print("处理日志")
            #     print("=" * 80)
            #     print(replacement_log)

        except Exception as e:
            print(f"\n错误: {e}")
            import traceback

            traceback.print_exc()
            print(f"\n继续测试下一个文件...")
            print()
            continue
