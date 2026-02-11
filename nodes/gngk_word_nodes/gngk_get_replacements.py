from __future__ import annotations

import os
import re
import time
from typing import Dict, List, Optional, Tuple
import pathlib
import sys

# 添加项目根目录到 sys.path
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from states import GngkTenderGraphState
from util.word_application_util import (
    create_word_application,
    close_word_application,
    open_document_with_retry,
    unprotect_document,
)
from util.word_constants import wdFindStop


# 提取函数：每个字段的查找逻辑
def extract_project_number(doc_content: str, first_page_header: str, state: GngkTenderGraphState, log_parts: List[str]) -> Optional[str]:
    """从页眉中提取 project_number"""
    if not first_page_header or not state.get("project_number"):
        return None
    
    project_number_pattern = r'招标编号[:：]\s*([^；;]+)'
    match = re.search(project_number_pattern, first_page_header)
    if match:
        number_text = match.group(1).strip()
        number_match = re.search(r'(\d+)$', number_text)
        if number_match:
            extracted_number = number_match.group(1)
            log_parts.append(f"从页眉中提取项目编号: {extracted_number} (来源: {number_text})")
            return extracted_number
        else:
            log_parts.append(f"无法从项目编号文本中提取数字: {number_text}")
    else:
        log_parts.append("在页眉中未找到 '项目编号' 模式")
    return None


def extract_project_name(doc_content: str, first_page_header: str, state: GngkTenderGraphState, log_parts: List[str]) -> Optional[str]:
    """从页眉中提取 project_name"""
    if not first_page_header or not state.get("project_name"):
        return None
    
    project_name_pattern = r'项目名称[:：]\s*([^；;]+)'
    match = re.search(project_name_pattern, first_page_header)
    if match:
        extracted_name = match.group(1).strip()
        extracted_name = re.sub(r'采购$', '', extracted_name).strip()
        log_parts.append(f"从页眉中提取项目名称: {extracted_name}")
        return extracted_name
    else:
        log_parts.append("在页眉中未找到 '项目名称' 模式")
    return None


def extract_buyer_name(doc_content: str, state: GngkTenderGraphState, log_parts: List[str]) -> Optional[str]:
    """从首页正文中提取 buyer_name"""
    if not doc_content or not state.get("buyer_name"):
        return None
    
    first_page_content = doc_content[:5000] if len(doc_content) > 5000 else doc_content
    buyer_pos = doc_content.find("招标人")
    if buyer_pos != -1:
        search_start = max(0, buyer_pos - 100)
        search_end = min(len(doc_content), buyer_pos + 2000)
        first_page_content = doc_content[search_start:search_end]
        log_parts.append(f"在位置 {buyer_pos} 找到 '招标人'，在范围 [{search_start}, {search_end}] 中搜索")
    else:
        log_parts.append("在文档中未找到 'vv'，在前 5000 个字符中搜索")
    
    buyer_name_pattern = r'招标人[:：]\s*([^\n\r]+?)(?:\s*\n\s*招标代理机构|招标代理机构)'
    match = re.search(buyer_name_pattern, first_page_content, re.DOTALL)
    if match:
        extracted_buyer_name = match.group(1).strip()
        log_parts.append(f"从首页提取招标人名称: {extracted_buyer_name}")
        return extracted_buyer_name
    else:
        buyer_name_pattern2 = r'招标人[:：]\s*([^招标]+?)(?=\s*招标代理机构)'
        match2 = re.search(buyer_name_pattern2, first_page_content, re.DOTALL)
        if match2:
            extracted_buyer_name = match2.group(1).strip()
            log_parts.append(f"提取招标人名称 (备用模式): {extracted_buyer_name}")
            return extracted_buyer_name
        else:
            log_parts.append(f"在首页内容中未找到 '招标人' 模式")
    return None


def extract_project_content(doc_content: str, state: GngkTenderGraphState, log_parts: List[str]) -> Optional[str]:
    """从正文中提取 project_content"""
    if not doc_content or not state.get("project_content"):
        return None
    
    start_marker1 = "2、项目基本信息"
    start_pos1 = doc_content.find(start_marker1)
    
    if start_pos1 == -1:
        log_parts.append("未找到起始标记 '2、项目基本信息'")
        return None
    
    log_parts.append(f"在位置 {start_pos1} 找到起始标记1 '{start_marker1}'")
    
    start_marker2_pattern = r'的委托[，,]\s*现以公开招标方式邀请合格的投标人就下列货物或服务前来投标[。.]'
    search_after_marker1 = start_pos1 + len(start_marker1)
    match = re.search(start_marker2_pattern, doc_content[search_after_marker1:], re.DOTALL)
    
    if not match:
        log_parts.append(f"在标记1之后未找到起始标记2模式")
        return None
    
    front_end_pos = search_after_marker1 + match.end()
    end_marker1 = "3、合格投标人资格条件"
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
        "项目交付日期"
    ]
    
    # 在 front_end_pos 和 end_pos1 之间查找所有结束标记
    found_positions = []
    for marker in end_markers:
        pos = doc_content.find(marker, front_end_pos, end_pos1)
        if pos != -1:
            found_positions.append((pos, marker))
            log_parts.append(f"在位置 {pos} 找到结束标记 '{marker}'")
    
    if not found_positions:
        log_parts.append(f"在 front_end 和 end_marker1 之间未找到任何结束标记")
        return None
    
    # 找到最早出现的结束标记
    earliest_pos, earliest_marker = min(found_positions, key=lambda x: x[0])
    log_parts.append(f"使用最早出现的结束标记 '{earliest_marker}' (位置: {earliest_pos})")
    
    # 找到该标记所在行的起始位置
    marker_line_start = earliest_pos
    while marker_line_start > front_end_pos and doc_content[marker_line_start - 1] not in ['\n', '\r']:
        marker_line_start -= 1
    
    log_parts.append(f"结束标记行起始位置: {marker_line_start}")
    
    content_start = front_end_pos
    while content_start < len(doc_content) and doc_content[content_start] in ['\n', '\r', ' ', '\t']:
        content_start += 1
    
    log_parts.append(f"内容起始位置: {content_start}")
    
    raw_extracted = doc_content[content_start:marker_line_start]
    log_parts.append(f"原始提取长度: {len(raw_extracted)} 个字符")
    
    lines = raw_extracted.split('\n')
    cleaned_lines = []
    for line in lines:
        line_stripped = line.strip('\r')
        # 排除包含任何结束标记的行
        if line_stripped and not any(marker in line_stripped for marker in end_markers):
            cleaned_lines.append(line_stripped)
    
    extracted_content = '\n'.join(cleaned_lines)
    
    if extracted_content:
        log_parts.append(f"成功提取项目内容")
        return extracted_content
    else:
        log_parts.append("清理后提取的内容为空")
    return None


def extract_project_content_v1(doc_content: str, state: GngkTenderGraphState, log_parts: List[str]) -> Optional[str]:
    """从正文中提取 project_content（v1）：起始标记为「第二章 投标人须知」，
    内容从「项目名称：」所在段落的下一段开始，到「招标人：」所在行之前结束。
    例如提取「设备名称及数量：电子支气管镜系统/壹套」等。"""
    if not doc_content:
        return None
    if not state.get("project_content") and not state.get("project_content_v1"):
        return None

    chapter_match = re.search(r"第二章\s*投标人须知", doc_content)
    if not chapter_match:
        log_parts.append("未找到起始章节标记「第二章 投标人须知」")
        return None
    chapter_pos = chapter_match.start()
    log_parts.append(f"在位置 {chapter_pos} 找到章节标记「第二章 投标人须知」")

    search_after_chapter = chapter_match.end()
    # 支持全角、半角冒号
    project_name_marker = re.compile(r"项目名称\s*[：:]")
    match_pn = project_name_marker.search(doc_content[search_after_chapter:])
    if not match_pn:
        log_parts.append("在章节之后未找到「项目名称：」")
        return None

    pn_pos = search_after_chapter + match_pn.start()
    log_parts.append(f"在位置 {pn_pos} 找到「项目名称：」")

    # 「项目名称：」所在段落：从该行行首到行尾（含换行）
    pn_line_start = pn_pos
    while pn_line_start > 0 and doc_content[pn_line_start - 1] not in ("\n", "\r"):
        pn_line_start -= 1
    pn_line_end = pn_pos
    while pn_line_end < len(doc_content) and doc_content[pn_line_end] not in ("\n", "\r"):
        pn_line_end += 1
    while pn_line_end < len(doc_content) and doc_content[pn_line_end] in ("\n", "\r"):
        pn_line_end += 1
    content_start = pn_line_end
    log_parts.append(f"「项目名称：」下一段起始位置: {content_start}")

    device_marker = re.compile(r"设备名称及数量\s*[：:]")
    match_device = device_marker.search(doc_content[content_start:])
    if not match_device:
        log_parts.append("在内容起始之后未找到「设备名称及数量：」")
        return None

    device_pos = content_start + match_device.start()
    log_parts.append(f"在位置 {device_pos} 找到「设备名称及数量：」")

    candidates = []
    for ch in ("\x07", "\r", "\n"):
        idx = doc_content.find(ch, device_pos)
        if idx != -1:
            candidates.append(idx)
    end_pos = min(candidates) if candidates else len(doc_content)

    raw_extracted = doc_content[device_pos:end_pos]
    extracted_content = raw_extracted.replace("\x07", "").strip()

    if extracted_content:
        log_parts.append(f"成功提取 project_content_v1，长度: {len(extracted_content)} 字符")
        log_parts.append(f"提取内容: {repr(extracted_content)}")
        return extracted_content
    log_parts.append("提取区间为空")
    return None


def extract_bzj_rule(doc_content: str, state: GngkTenderGraphState, log_parts: List[str]) -> Optional[str]:
    """从正文中提取 bzj_rule"""
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
    log_parts.append(f"在 '投标保证金数额：' 和 '户名：' 之间搜索保证金规则，范围长度: {len(search_range)} 个字符")

    extracted_bzj = search_range.strip()
    # 有些模板中金额后面带有句号（例如“人民币29,000.00元整。”），
    # 为了避免 Find.Execute 替换时跨越受保护边界，这里去掉末尾的中文句号。
    extracted_bzj = extracted_bzj.rstrip("。").strip()

    if extracted_bzj:
        log_parts.append(f"提取保证金规则: {extracted_bzj}")
        return extracted_bzj
    else:
        log_parts.append("在指定范围内未提取到保证金规则")
        return None


def extract_shell_dates(doc_content: str, state: GngkTenderGraphState, log_parts: List[str]) -> Tuple[Optional[str], Optional[str]]:
    if not doc_content or (not state.get("shell_start_date") and not state.get("shell_end_date")):
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
            r'(\d{4}年\d{1,2}月\d{1,2}日\s*起)',
            r'(\d{4}年\s*月\s*日\s*起)',
            r'(\s*年\s*月\s*日\s*起)'
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
            r'(\d{4}年\d{1,2}月\d{1,2}日\s*止)',
            r'(\d{4}年\s*月\s*日\s*止)',
            r'(\s*年\s*月\s*日\s*止)'
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




def extract_submit_date(doc_content: str, state: GngkTenderGraphState, log_parts: List[str]) -> Optional[str]:
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
    log_parts.append(f"在 '截止时间：' 和 '地点：' 之间搜索递交文件时间，范围长度: {len(search_range)} 个字符")
    
    time_patterns = [
        r'(\d{4}年\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{2})',
        r'(\d{4}年\s*月\s*日\s*\d{1,2}:\d{2})',
        r'(\s*年\s*月\s*日\s*\d{1,2}:\d{2})'
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


def extract_platform(doc_content: str, state: GngkTenderGraphState, log_parts: List[str]) -> Optional[str]:
    """从正文中提取 platform (发布平台)"""
    if not doc_content or not state.get("platform"):
        return None
    
    start_markers = [
        "招标人、招标代理机构均将通过",
        "采购人、采购代理机构均将通过",
    ]
    end_marker = "公开发布"
    
    start_pos = -1
    start_marker = None
    for marker in start_markers:
        pos = doc_content.find(marker)
        if pos != -1:
            start_pos = pos
            start_marker = marker
            break

    if start_pos == -1 or not start_marker:
        log_parts.append("未找到起始标记 '招标人、招标代理机构均将通过' 或 '采购人、采购代理机构均将通过'")
        return None
    
    log_parts.append(f"在位置 {start_pos} 找到起始标记 '{start_marker}'")
    
    search_after = start_pos + len(start_marker)
    end_pos = doc_content.find(end_marker, search_after)
    
    if end_pos == -1:
        log_parts.append("未找到结束标记 '公开发布'")
        return None
    
    log_parts.append(f"在位置 {end_pos} 找到结束标记 '{end_marker}'")
    
    search_range = doc_content[search_after:end_pos]
    log_parts.append(f"在 '{start_marker}' 和 '公开发布' 之间搜索发布平台，范围长度: {len(search_range)} 个字符")
    
    platform_pattern = r'\s*([^（(]+)\s*[（(]([^）)]+)[）)]'
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


def extract_service_fee(doc_content: str, state: GngkTenderGraphState, log_parts: List[str]) -> Optional[str]:
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
        log_parts.append("未找到结束标记 '成交供应商在接受成交通知书的同时需向采购代理机构一次性付清代理服务费'")
        return None
    
    # 提取范围内的内容
    search_range = doc_content[start_pos:end_pos]
    log_parts.append(f"找到服务费说明范围，位置: {start_pos}-{end_pos}")
    
    # 在范围内查找服务费相关模式
    fee_pattern = r'百分之([\u4e00-\u9fa5]+\s*\([^)]+\))'
    match = re.search(fee_pattern, search_range)
    
    if match:
        extracted_fee = "百分之" + match.group(1)
        log_parts.append(f"提取服务费: {extracted_fee}")
        return extracted_fee
    else:
        # 尝试其他模式
        fee_pattern2 = r'服务费为成交金额的\s*([^。]+)'
        match2 = re.search(fee_pattern2, search_range)
        if match2:
            extracted_fee = match2.group(1).strip()
            log_parts.append(f"提取服务费 (备用模式): {extracted_fee}")
            return extracted_fee
        else:
            log_parts.append("在服务费说明范围内未找到服务费模式")
    return None


def extract_similar_project_performance_date(doc_content: str, state: GngkTenderGraphState, log_parts: List[str]) -> Optional[str]:
    if not doc_content:
        return None

    marker = "2、类似项目业绩"
    marker_pos = doc_content.find(marker)
    if marker_pos == -1:
        log_parts.append("未找到标记 '2、类似项目业绩'")
        return None

    next_item_pos = doc_content.find("3、", marker_pos + len(marker))
    search_end = next_item_pos if next_item_pos != -1 else min(len(doc_content), marker_pos + 8000)
    search_range = doc_content[marker_pos:search_end]

    pattern = r"(自\d{4}年\d{1,2}月\d{1,2}日至今)"
    match = re.search(pattern, search_range)
    if match:
        extracted = match.group(1).strip()
        log_parts.append(f"在“2、类似项目业绩”条目中提取日期: {extracted}")
        return extracted

    log_parts.append("在“2、类似项目业绩”条目范围内未找到日期模式 '自xxxx年xx月xx日至今'")
    return None


def extract_contact_fields(doc_content: str, state: GngkTenderGraphState, log_parts: List[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """从正文中提取 project_zbr_xbr, zbr_xbr_tel, zbr_pinyin"""
    if not doc_content:
        return None, None, None
    
    agency_marker = "采购代理机构名称："
    agency_pos = doc_content.find(agency_marker)
    
    if agency_pos == -1:
        log_parts.append("在文档中未找到 '采购代理机构名称：' 标记，尝试在全文中按锚点提取联系字段")
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
        log_parts.append(f"在 '采购代理机构名称：' 之后未找到 '邮编：' 标记")
        if agency_pos != -1:
            search_start = agency_pos + len(agency_marker)
            search_end = min(len(doc_content), agency_pos + 2000)
    else:
        log_parts.append(f"在位置 {zipcode_pos} 找到 '邮编：' 标记")
        zipcode_line_end = zipcode_pos
        while zipcode_line_end < len(doc_content) and doc_content[zipcode_line_end] not in ['\n', '\r']:
            zipcode_line_end += 1
        while zipcode_line_end < len(doc_content) and doc_content[zipcode_line_end] in ['\n', '\r']:
            zipcode_line_end += 1
        search_start = zipcode_line_end
        search_end = min(len(doc_content), search_start + 2000)
    
    search_range = doc_content[search_start:search_end]
    log_parts.append(f"在范围 [{search_start}, {search_end}] 中搜索，内容长度: {len(search_range)}")
    
    project_zbr_xbr = None
    zbr_xbr_tel = None
    zbr_pinyin = None

    def _strip_wrappers(value: str) -> str:
        cleaned = value.strip()
        wrapper_pairs = [("[", "]"), ("［", "］"), ("【", "】"), ("(", ")"), ("（", "）")]
        for left, right in wrapper_pairs:
            if cleaned.startswith(left) and cleaned.endswith(right) and len(cleaned) >= 2:
                cleaned = cleaned[1:-1].strip()
        cleaned = re.sub(r"[ \t\r\n]+", " ", cleaned).strip()
        return cleaned

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
        anchor_pattern = (
            r"邮编[:：]\s*200002\s*(?:\r?\n\s*)*联系人[:：]\s*(.*?)\s*电话[:：]\s*021-63230480\s*转"
        )
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


def get_replacements(state: GngkTenderGraphState, config) -> GngkTenderGraphState:
    """
    在 Word 文档中查找需要替换的占位符，并根据 state 中的字段建立映射关系。
    
    这个节点会：
    1. 打开 prepared_doc_path 的 Word 文档
    2. 读取文档内容，查找所有可能的占位符
    3. 根据 state 中的字段（project_name, project_number, project_content, bzj_rule, 
       buyer_name, project_zbr_xbr, zbr_xbr_tel, zbr_pinyin）查找对应的占位符
    4. 将找到的占位符信息保存到 state 中，并根据 placeholder_mapping 生成替换列表
    """
    start_time = time.time()
    print(f"[get_replacements] 开始执行...")
    
    template_path = state.get("prepared_doc_path")
    
    if not template_path:
        raise ValueError("需要 prepared_doc_path 来获取替换内容")
    
    # 确保路径是绝对路径（Word COM 对象需要绝对路径）
    import os
    if not os.path.isabs(template_path):
        template_path = os.path.abspath(template_path)
    
    # 检查文件是否存在
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"未找到模板文档: {template_path}")
    
    # 检查文件是否可读
    if not os.access(template_path, os.R_OK):
        raise PermissionError(f"无法读取模板文档: {template_path}")
    
    found_placeholders: Dict[str, str] = {}  # {field_name: found_placeholder}
    log_parts = []
    word = None
    doc = None
    com_initialized = False
    
    try:
        # 使用统一的工具函数创建 Word 应用程序
        # 在并发环境下使用独立实例，避免多用户冲突
        word, com_initialized = create_word_application(
            initial_delay=1.0,  # 创建前等待，让之前的实例有时间完全关闭
            post_init_delay=0.5,  # 给 Word 一点时间完成初始化
            use_existing=False,  # 并发环境下必须使用独立实例
            verify=True,
            node_name="get_replacements"
        )
        log_parts.append("成功创建/获取 Word 实例")
        
        try:
            # 使用统一的工具函数打开文档（带重试机制）
            doc = open_document_with_retry(
                word_app=word,
                file_path=template_path,
                read_only=True,
                node_name="get_replacements"
            )
            log_parts.append(f"已打开: {template_path}")
            
            # 使用统一的工具函数取消文档保护
            if unprotect_document(doc, node_name="get_replacements"):
                log_parts.append("文档已取消保护")
            
            # 读取文档全文内容用于分析
            doc_content = doc.Content.Text
            log_parts.append(f"文档内容长度: {len(doc_content)} 个字符")
            
            # 提取首页页眉内容
            try:
                # 获取第一页的页眉（wdHeaderFooterPrimary = 1）
                first_page_header = doc.Sections(1).Headers(1).Range.Text
            except Exception as e:
                log_parts.append(f"读取页眉时出错: {e}")
                first_page_header = ""
            
            # 按顺序同步执行各个字段的查找
            # 注意：contact_fields 函数返回三个值，需要特殊处理
            
            # 提取 project_content
            if state.get("project_content"):
                try:
                    result = extract_project_content(doc_content, state, log_parts)
                    if result is not None:
                        found_placeholders["project_content"] = result
                except Exception as e:
                    log_parts.append(f"提取项目内容时出错: {e}")

            # 提取 project_content_v1（第二章 项目名称下一段的「设备名称及数量：...」）
            if state.get("project_content") or state.get("project_content_v1"):
                try:
                    result = extract_project_content_v1(doc_content, state, log_parts)
                    if result is not None:
                        found_placeholders["project_content_v1"] = result
                except Exception as e:
                    log_parts.append(f"提取项目内容(v1)时出错: {e}")

            # 提取 project_number
            if state.get("project_number"):
                try:
                    result = extract_project_number(doc_content, first_page_header, state, log_parts)
                    if result is not None:
                        found_placeholders["project_number"] = result
                except Exception as e:
                    log_parts.append(f"提取项目编号时出错: {e}")
            
            # 提取 project_name
            if state.get("project_name"):
                try:
                    result = extract_project_name(doc_content, first_page_header, state, log_parts)
                    if result is not None:
                        found_placeholders["project_name"] = result
                except Exception as e:
                    log_parts.append(f"提取项目名称时出错: {e}")
            
            # 提取 buyer_name
            if state.get("buyer_name"):
                try:
                    result = extract_buyer_name(doc_content, state, log_parts)
                    if result is not None:
                        found_placeholders["buyer_name"] = result
                except Exception as e:
                    log_parts.append(f"提取采购人名称时出错: {e}")
            
            
            # 提取 bzj_rule
            if state.get("bzj_rule"):
                try:
                    result = extract_bzj_rule(doc_content, state, log_parts)
                    if result is not None:
                        found_placeholders["bzj_rule"] = result
                except Exception as e:
                    log_parts.append(f"提取保证金规则时出错: {e}")
            
            if state.get("project_zbr_xbr") or state.get("zbr_xbr_tel") or state.get("zbr_pinyin"):
                try:
                    project_zbr_xbr, zbr_xbr_tel, zbr_pinyin = extract_contact_fields(doc_content, state, log_parts)
                    if project_zbr_xbr:
                        found_placeholders["project_zbr_xbr"] = project_zbr_xbr
                    if zbr_xbr_tel:
                        found_placeholders["zbr_xbr_tel"] = zbr_xbr_tel
                    if zbr_pinyin:
                        found_placeholders["zbr_pinyin"] = zbr_pinyin
                except Exception as e:
                    log_parts.append(f"提取联系字段时出错: {e}")
            
            if state.get("shell_start_date") or state.get("shell_end_date"):
                try:
                    shell_start_date, shell_end_date = extract_shell_dates(doc_content, state, log_parts)
                    if shell_start_date:
                        found_placeholders["shell_start_date"] = shell_start_date
                    if shell_end_date:
                        found_placeholders["shell_end_date"] = shell_end_date
                except Exception as e:
                    log_parts.append(f"提取售标时间时出错: {e}")
            
            # 提取 submit_date
            if state.get("submit_date"):
                try:
                    result = extract_submit_date(doc_content, state, log_parts)
                    if result is not None:
                        found_placeholders["submit_date"] = result
                except Exception as e:
                    log_parts.append(f"提取递交文件时间时出错: {e}")
            
            # 提取 platform
            if state.get("platform"):
                try:
                    result = extract_platform(doc_content, state, log_parts)
                    if result is not None:
                        found_placeholders["platform"] = result
                except Exception as e:
                    log_parts.append(f"提取发布平台时出错: {e}")
            
            # 提取 service_fee
            if state.get("service_fee"):
                try:
                    result = extract_service_fee(doc_content, state, log_parts)
                    if result is not None:
                        found_placeholders["service_fee"] = result
                except Exception as e:
                    log_parts.append(f"提取服务费时出错: {e}")

            # 记录查找结果
            if found_placeholders:
                log_parts.append(f"在文档中找到 {len(found_placeholders)} 个占位符")
            else:
                log_parts.append("在文档中未找到占位符")
            
        except Exception as e:
            error_msg = f"读取文档时出错: {e}"
            log_parts.append(error_msg)
            # 在重新抛出异常之前，确保关闭文档和 Word
            if 'doc' in locals() and doc:
                try:
                    doc.Close(SaveChanges=False)
                except:
                    pass
            if 'word' in locals() and word:
                close_word_application(word_app=word, doc=None, com_initialized=com_initialized, wait_time=0.0, node_name="get_replacements")
            elif com_initialized:
                try:
                    # 使用统一的工具函数关闭 Word 应用程序
                    close_word_application(word_app=None, doc=None, com_initialized=True, wait_time=0.0, node_name="get_replacements")
                except:
                    pass
            raise
        finally:
            # 使用统一的工具函数关闭 Word 应用程序
            close_word_application(
                word_app=word,
                doc=doc,
                com_initialized=com_initialized,
                wait_time=1.5,
                node_name="get_replacements"
            )
            log_parts.append("资源清理完成")
    
    except Exception as e:
        error_msg = f"初始化 Word COM 时出错: {e}"
        log_parts.append(error_msg)
        # 即使发生异常，也要确保关闭 Word 和清理 COM
        close_word_application(
            word_app=word,
            doc=doc,
            com_initialized=com_initialized,
            wait_time=1.5,
            node_name="get_replacements"
        )
        raise
    
    # Update state with found placeholders
    new_state_dict = dict(state)
    # 将找到的占位符信息保存到 state 中
    # 可以使用一个新的字段来存储，或者直接使用现有的字段
    # 这里我们创建一个新字段 placeholder_mapping 来存储字段名到占位符的映射
    new_state_dict["placeholder_mapping"] = found_placeholders
    
    # 根据 placeholder_mapping 生成替换列表
    replacements = []
    if found_placeholders:
        # 定义字段名列表（对应 state 中的字段）
        field_names = [
            "project_content",
            "project_content_v1",
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
        
        # 根据 placeholder_mapping 生成替换列表
        for field_name in field_names:
            # 检查是否有该字段的占位符映射（从文档中提取的旧值）
            old_value = found_placeholders.get(field_name)
            if not old_value:
                continue
            
            # 获取该字段的新值（从 state 中获取）
            new_value = state.get(field_name)
            if field_name == "project_content_v1" and not new_value:
                fallback = state.get("project_content")
                if fallback:
                    new_value = fallback
                    log_parts.append("字段 'project_content_v1' 未提供新值，使用 'project_content' 的值作为替换内容")
            if not new_value:
                log_parts.append(f"字段 '{field_name}' 有占位符 '{old_value}' 但 state 中没有新值，跳过")
                continue
            
            # 如果旧值和新值相同，跳过替换
            if old_value == new_value:
                log_parts.append(f"字段 '{field_name}': 旧值 '{old_value}' 等于新值，跳过")
                continue
            
            # 生成替换对 (旧值, 新值)
            replacements.append((old_value, new_value))
            log_parts.append(f"为字段 '{field_name}' 生成替换: '{old_value}' -> '{new_value}'")
        
        # 如果没有生成任何替换项，记录日志
        if not replacements:
            log_parts.append("未生成任何替换 (所有字段要么缺失要么未更改)")
        else:
            log_parts.append(f"生成了 {len(replacements)} 对替换")
            # 详细列出所有替换对
            for i, (old_val, new_val) in enumerate(replacements, 1):
                # 截断过长的值以便显示
                old_display = old_val[:50] + "..." if len(old_val) > 50 else old_val
                new_display = new_val[:50] + "..." if len(new_val) > 50 else new_val
                log_parts.append(f"  [{i}] ({old_display}, {new_display})")
    else:
        log_parts.append("未找到占位符映射，跳过替换生成")
    
    # 只返回需要更新的键，避免并行执行时的状态冲突
    # 在 LangGraph 中，并行节点应该只返回部分状态更新
    replacement_log = "; ".join(log_parts)
    new_state = GngkTenderGraphState(
        placeholder_mapping=found_placeholders,
        replacements=replacements,
        replacement_log=replacement_log
    )
    # 为了日志记录，创建完整状态（仅用于日志）
    full_state_for_log = dict(state)
    full_state_for_log.update({
        "placeholder_mapping": found_placeholders,
        "replacements": replacements,
        "replacement_log": replacement_log
    })
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"[get_replacements]: 执行日志:{replacement_log}")
    print(f"[get_replacements] 执行完成，耗时: {elapsed_time:.2f} 秒 ({elapsed_time*1000:.0f} 毫秒)")
    
    return new_state


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
    from states import GngkTenderGraphState
    
    # 测试文档路径列表
    test_doc_paths = [
        "test_word/252030-招标文件-清洁稿【基因测序仪】 - 副本.doc",
    ]
    
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
        test_state: GngkTenderGraphState = {
            "prepared_doc_path": str(test_doc_path),
            "project_number": "253505",  
            "project_name": "细胞电转仪", 
            "project_content": "项目名称及数量：细胞电转仪   壹套",
            "project_content_v1": "设备名称及数量：细胞电转仪/壹套",
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
            "similar_project_performance_date": "自2022年09月01日至今",
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
