from __future__ import annotations

import re
from typing import Any, Callable, List, Optional, Sequence, Tuple

from backend.nodes.common_word_nodes.get_replacements_core import (
    ExtractorSpec,
    ReplacementFieldSpec,
)
from backend.util.common_util.tender_number import (
    extract_numeric_tail_project_number,
)

ProjectNumberValueParser = Callable[[str], Optional[str]]


def make_project_number_extractor(
    number_label: str,
    value_parser: ProjectNumberValueParser | None = None,
) -> Callable[[str, str, Any, List[str]], Optional[str]]:
    """Build a header-based project number extractor for one label variant."""

    parser = value_parser or extract_numeric_tail_project_number

    def extract_project_number(
        doc_content: str,
        first_page_header: str,
        state: Any,
        log_parts: List[str],
    ) -> Optional[str]:
        del doc_content
        if not first_page_header or not state.get("project_number"):
            return None

        project_number_pattern = rf"{re.escape(number_label)}[:：]\s*([^；;]+)"
        match = re.search(project_number_pattern, first_page_header)
        if match:
            number_text = match.group(1).strip()
            extracted_number = parser(number_text)
            if extracted_number:
                log_parts.append(
                    f"从页眉中提取项目编号: {extracted_number} (来源: {number_text})"
                )
                return extracted_number

            log_parts.append(f"无法从项目编号文本中提取有效编号: {number_text}")
        else:
            log_parts.append(f"在页眉中未找到 '{number_label}' 模式")
        return None

    extract_project_number.__name__ = f"extract_project_number_from_{number_label}"
    return extract_project_number


def make_platform_extractor(
    start_markers: Sequence[str],
) -> Callable[[str, Any, List[str]], Optional[str]]:
    """Build a platform extractor that supports one or more start markers."""

    start_markers_tuple = tuple(start_markers)

    def extract_platform(
        doc_content: str, state: Any, log_parts: List[str]
    ) -> Optional[str]:
        if not doc_content or not state.get("platform"):
            return None

        end_marker = "公开发布"
        start_pos = -1
        matched_marker: Optional[str] = None
        for marker in start_markers_tuple:
            pos = doc_content.find(marker)
            if pos != -1:
                start_pos = pos
                matched_marker = marker
                break

        if start_pos == -1 or matched_marker is None:
            joined_markers = " 或 ".join(f"'{marker}'" for marker in start_markers_tuple)
            log_parts.append(f"未找到起始标记 {joined_markers}")
            return None

        log_parts.append(f"在位置 {start_pos} 找到起始标记 '{matched_marker}'")

        search_after = start_pos + len(matched_marker)
        end_pos = doc_content.find(end_marker, search_after)
        if end_pos == -1:
            log_parts.append(f"未找到结束标记 '{end_marker}'")
            return None

        log_parts.append(f"在位置 {end_pos} 找到结束标记 '{end_marker}'")

        search_range = doc_content[search_after:end_pos]
        log_parts.append(
            f"在 '{matched_marker}' 和 '{end_marker}' 之间搜索发布平台，范围长度: "
            f"{len(search_range)} 个字符"
        )

        platform_pattern = r"\s*([^（(]+)\s*[（(]([^）)]+)[）)]"
        match = re.search(platform_pattern, search_range, re.DOTALL)
        if match:
            platform_name = match.group(1).strip()
            platform_url = match.group(2).strip()
            extracted_platform = f"{platform_name}（{platform_url}）"
            log_parts.append(f"提取发布平台: {extracted_platform}")
            return extracted_platform

        log_parts.append("在文档中未找到发布平台模式")
        return None

    extract_platform.__name__ = "extract_platform"
    return extract_platform


extract_project_number_from_project_header = make_project_number_extractor("项目编号")
extract_project_number_from_bid_header = make_project_number_extractor("招标编号")
extract_procurement_platform = make_platform_extractor(
    ("采购人、采购代理机构均将通过",)
)
extract_public_tender_platform = make_platform_extractor(
    ("招标人、招标代理机构均将通过", "采购人、采购代理机构均将通过")
)


def extract_project_name(
    doc_content: str,
    first_page_header: str,
    state: Any,
    log_parts: List[str],
) -> Optional[str]:
    """Extract project_name from the first page header."""
    del doc_content
    if not first_page_header or not state.get("project_name"):
        return None

    project_name_pattern = r"项目名称[:：]\s*([^；;]+)"
    match = re.search(project_name_pattern, first_page_header)
    if match:
        extracted_name = match.group(1).strip()
        extracted_name = re.sub(r"采购$", "", extracted_name).strip()
        log_parts.append(f"从页眉中提取项目名称: {extracted_name}")
        return extracted_name

    log_parts.append("在页眉中未找到 '项目名称' 模式")
    return None


def extract_shell_dates(
    doc_content: str, state: Any, log_parts: List[str]
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
    doc_content: str, state: Any, log_parts: List[str]
) -> Optional[str]:
    """Extract submit_date from the body content."""
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
        f"在 '{start_marker}' 和 '{end_marker}' 之间搜索递交文件时间，范围长度: "
        f"{len(search_range)} 个字符"
    )

    time_patterns = [
        r"(\d{4}年\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{2})",
        r"(\d{4}年\s*月\s*日\s*\d{1,2}:\d{2})",
        r"(\s*年\s*月\s*日\s*\d{1,2}:\d{2})",
    ]
    for time_pattern in time_patterns:
        match = re.search(time_pattern, search_range, re.DOTALL)
        if match:
            extracted_date = match.group(1).strip()
            log_parts.append(f"提取递交文件时间: {extracted_date}")
            return extracted_date

    log_parts.append("在 '截止时间：' 和 '地点：' 范围内未找到递交文件时间模式")
    return None


def extract_service_fee(
    doc_content: str, state: Any, log_parts: List[str]
) -> Optional[str]:
    """Extract service_fee from the body content."""
    if not doc_content or not state.get("service_fee"):
        return None

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

    search_range = doc_content[start_pos:end_pos]
    log_parts.append(f"找到服务费说明范围，位置: {start_pos}-{end_pos}")

    fee_pattern = r"百分之([\u4e00-\u9fa5]+\s*\([^)]+\))"
    match = re.search(fee_pattern, search_range)
    if match:
        extracted_fee = "百分之" + match.group(1)
        log_parts.append(f"提取服务费: {extracted_fee}")
        return extracted_fee

    fee_pattern2 = r"服务费为成交金额的\s*([^。]+)"
    match2 = re.search(fee_pattern2, search_range)
    if match2:
        extracted_fee = match2.group(1).strip()
        log_parts.append(f"提取服务费 (备用模式): {extracted_fee}")
        return extracted_fee

    log_parts.append("在服务费说明范围内未找到服务费模式")
    return None


def extract_public_tender_buyer_name(
    doc_content: str, state: Any, log_parts: List[str]
) -> Optional[str]:
    """Extract buyer_name for the public tender family."""
    if not doc_content or not state.get("buyer_name"):
        return None

    first_page_content = doc_content[:5000] if len(doc_content) > 5000 else doc_content
    buyer_pos = doc_content.find("招标人")
    if buyer_pos != -1:
        search_start = max(0, buyer_pos - 100)
        search_end = min(len(doc_content), buyer_pos + 2000)
        first_page_content = doc_content[search_start:search_end]
        log_parts.append(
            f"在位置 {buyer_pos} 找到 '招标人'，在范围 [{search_start}, {search_end}] 中搜索"
        )
    else:
        log_parts.append("在文档中未找到 '招标人'，在前 5000 个字符中搜索")

    buyer_name_pattern = (
        r"招标人[:：]\s*([^\n\r]+?)(?:\s*\n\s*招标代理机构|招标代理机构)"
    )
    match = re.search(buyer_name_pattern, first_page_content, re.DOTALL)
    if match:
        extracted_buyer_name = match.group(1).strip()
        log_parts.append(f"从首页提取招标人名称: {extracted_buyer_name}")
        return extracted_buyer_name

    buyer_name_pattern2 = r"招标人[:：]\s*([^招标]+?)(?=\s*招标代理机构)"
    match2 = re.search(buyer_name_pattern2, first_page_content, re.DOTALL)
    if match2:
        extracted_buyer_name = match2.group(1).strip()
        log_parts.append(f"提取招标人名称 (备用模式): {extracted_buyer_name}")
        return extracted_buyer_name

    log_parts.append("在首页内容中未找到 '招标人' 模式")
    return None


def extract_public_tender_project_content(
    doc_content: str, state: Any, log_parts: List[str]
) -> Optional[str]:
    """Extract project_content for the public tender family."""
    if not doc_content or not state.get("project_content"):
        return None

    start_marker1 = "2、项目基本信息"
    start_pos1 = doc_content.find(start_marker1)
    if start_pos1 == -1:
        log_parts.append("未找到起始标记 '2、项目基本信息'")
        return None

    log_parts.append(f"在位置 {start_pos1} 找到起始标记1 '{start_marker1}'")

    start_marker2_pattern = r"邀请合格的投标人就下列货物或服务前来投标[。.]"
    search_after_marker1 = start_pos1 + len(start_marker1)
    match = re.search(
        start_marker2_pattern, doc_content[search_after_marker1:], re.DOTALL
    )
    if not match:
        log_parts.append("在标记1之后未找到起始标记2模式")
        return None

    front_end_pos = search_after_marker1 + match.end()
    end_marker1 = "3、合格投标人资格条件"
    end_pos1 = doc_content.find(end_marker1, front_end_pos)
    if end_pos1 == -1:
        log_parts.append(f"未找到结束标记1 '{end_marker1}'")
        return None

    log_parts.append(f"在位置 {end_pos1} 找到结束标记1 '{end_marker1}'")

    end_markers = [
        "项目预算",
        "最高投标限价",
        "交付地点",
        "交付日期",
        "供应商",
        "项目交付地点",
        "项目交付日期",
    ]

    found_positions = []
    for marker in end_markers:
        pos = doc_content.find(marker, front_end_pos, end_pos1)
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


def extract_public_tender_bzj_rule(
    doc_content: str, state: Any, log_parts: List[str]
) -> Optional[str]:
    """Extract bzj_rule for the public tender family."""
    if not doc_content or not state.get("bzj_rule"):
        return None

    start_marker = "投标保证金数额："
    end_marker = "户名："

    start_pos = doc_content.find(start_marker)
    if start_pos == -1:
        log_parts.append(f"未找到起始标记 '{start_marker}'")
        return None

    log_parts.append(f"在位置 {start_pos} 找到起始标记 '{start_marker}'")

    search_after = start_pos + len(start_marker)
    end_pos = doc_content.find(end_marker, search_after)
    if end_pos == -1:
        log_parts.append(f"未找到结束标记 '{end_marker}'")
        return None

    log_parts.append(f"在位置 {end_pos} 找到结束标记 '{end_marker}'")

    search_range = doc_content[search_after:end_pos]
    log_parts.append(
        f"在 '{start_marker}' 和 '{end_marker}' 之间搜索保证金规则，范围长度: "
        f"{len(search_range)} 个字符"
    )

    extracted_bzj = search_range.strip().rstrip("。").strip()
    if extracted_bzj:
        log_parts.append(f"提取保证金规则: {extracted_bzj}")
        return extracted_bzj

    log_parts.append("在指定范围内未提取到保证金规则")
    return None


def extract_public_tender_contact_fields(
    doc_content: str, state: Any, log_parts: List[str]
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract contact fields for the public tender family."""
    if not doc_content:
        return None, None, None

    agency_marker = "采购代理机构名称："
    agency_pos = doc_content.find(agency_marker)

    if agency_pos == -1:
        log_parts.append(
            "在文档中未找到 '采购代理机构名称：' 标记，尝试在全文中按锚点提取联系字段"
        )
        search_start = 0
        search_end = len(doc_content)
    else:
        log_parts.append(f"在位置 {agency_pos} 找到 '采购代理机构名称：' 标记")
        search_start = agency_pos
        search_end = min(len(doc_content), agency_pos + 4000)

    anchor_range = doc_content[search_start:search_end]

    zipcode_marker = "邮编："
    zipcode_pos = doc_content.find(zipcode_marker, search_start)

    if zipcode_pos == -1:
        log_parts.append("在 '采购代理机构名称：' 之后未找到 '邮编：' 标记")
        if agency_pos != -1:
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

    def _strip_wrappers(value: str) -> str:
        cleaned = value.strip()
        wrapper_pairs = [
            ("[", "]"),
            ("［", "］"),
            ("【", "】"),
            ("(", ")"),
            ("（", "）"),
        ]
        for left, right in wrapper_pairs:
            if (
                cleaned.startswith(left)
                and cleaned.endswith(right)
                and len(cleaned) >= 2
            ):
                cleaned = cleaned[1:-1].strip()
        return re.sub(r"[ \t\r\n]+", " ", cleaned).strip()

    def _extract_with_pattern(pattern: str, text: str, flags: int = 0) -> Optional[str]:
        match = re.search(pattern, text, flags)
        if not match:
            return None
        if match.lastindex:
            return match.group(1)
        if "value" in match.groupdict():
            return match.group("value")
        return None

    if state.get("project_zbr_xbr"):
        anchor_pattern = r"邮编[:：]\s*200002\s*(?:\r?\n\s*)*联系人[:：]\s*(.*?)\s*电话[:：]\s*021-63230480\s*转"
        extracted = _extract_with_pattern(anchor_pattern, anchor_range, re.DOTALL)
        if extracted:
            project_zbr_xbr = _strip_wrappers(extracted)
            log_parts.append(f"按锚点提取项目负责人/项目经办人: {project_zbr_xbr}")
        else:
            contact_pattern = r"联系人[:：]\s*([^\n\r]+)"
            extracted = _extract_with_pattern(contact_pattern, search_range)
            if extracted:
                project_zbr_xbr = _strip_wrappers(extracted)
                log_parts.append(f"提取项目负责人/项目经办人: {project_zbr_xbr}")
            else:
                log_parts.append("未找到项目负责人/项目经办人可提取内容")

    if state.get("zbr_xbr_tel"):
        anchor_pattern = r"电话[:：]\s*021-63230480\s*转\s*(.*?)\s*传真[:：]"
        extracted = _extract_with_pattern(anchor_pattern, anchor_range, re.DOTALL)
        if extracted:
            zbr_xbr_tel = _strip_wrappers(re.sub(r"\s+", "", extracted))
            log_parts.append(f"按锚点提取负责人/经办人电话: {zbr_xbr_tel}")
        else:
            tel_pattern = r"电话[:：]\s*[^\n\r]*转\s*([^\n\r]+)"
            extracted = _extract_with_pattern(tel_pattern, search_range)
            if extracted:
                zbr_xbr_tel = _strip_wrappers(re.sub(r"\s+", "", extracted))
                log_parts.append(f"提取负责人/经办人电话: {zbr_xbr_tel}")
            else:
                log_parts.append("未找到负责人/经办人电话可提取内容")

    if state.get("zbr_pinyin"):
        anchor_pattern = r"电子邮箱[:：]\s*([^\s@\n\r]+)\s*@dongsong-cn\.com"
        extracted = _extract_with_pattern(anchor_pattern, anchor_range, re.IGNORECASE)
        if extracted:
            zbr_pinyin = _strip_wrappers(extracted)
            log_parts.append(f"按锚点提取负责人拼音: {zbr_pinyin}")
        else:
            email_pattern = r"电子邮箱[:：]\s*([^@\n\r]+)@"
            extracted = _extract_with_pattern(email_pattern, search_range)
            if extracted:
                zbr_pinyin = _strip_wrappers(extracted)
                log_parts.append(f"提取负责人拼音: {zbr_pinyin}")
            else:
                log_parts.append("未找到负责人拼音可提取内容")

    return project_zbr_xbr, zbr_xbr_tel, zbr_pinyin


COMMON_REPLACEMENT_FIELD_NAMES = (
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
)


def build_common_replacement_fields() -> List[ReplacementFieldSpec]:
    """Build a fresh copy of the shared replacement field specs."""
    return [
        ReplacementFieldSpec(field_name=field_name)
        for field_name in COMMON_REPLACEMENT_FIELD_NAMES
    ]


__all__ = [
    "COMMON_REPLACEMENT_FIELD_NAMES",
    "ExtractorSpec",
    "ReplacementFieldSpec",
    "build_common_replacement_fields",
    "extract_public_tender_buyer_name",
    "extract_public_tender_bzj_rule",
    "extract_public_tender_contact_fields",
    "extract_public_tender_project_content",
    "extract_procurement_platform",
    "extract_project_name",
    "extract_project_number_from_bid_header",
    "extract_project_number_from_project_header",
    "extract_public_tender_platform",
    "extract_service_fee",
    "extract_shell_dates",
    "extract_submit_date",
    "make_platform_extractor",
    "make_project_number_extractor",
]
