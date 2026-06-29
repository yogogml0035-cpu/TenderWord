from __future__ import annotations

import re
from typing import Callable, List, Optional

from backend.nodes.common_word_nodes.get_replacements_core import (
    ExtractorSpec,
    ReplacementFieldSpec,
)
from backend.nodes.common_word_nodes.get_replacements_shared import (
    build_common_replacement_fields,
    extract_project_name,
    extract_project_number_from_bid_header,
    extract_public_tender_buyer_name,
    extract_public_tender_bzj_rule,
    extract_public_tender_contact_fields,
    extract_public_tender_investment,
    extract_public_tender_platform,
    extract_public_tender_project_content,
    extract_public_tender_project_content_v2,
    extract_service_fee,
    extract_shell_dates,
    extract_submit_date,
    format_public_tender_investment_value,
    make_public_tender_project_content_labeled_line_extractor,
    make_public_tender_project_content_labeled_line_formatter,
    _strip_project_content_field_label,
)
from backend.states import GngkTenderGraphState
from backend.util.common_util.tender_number import extract_numeric_tail_project_number


ProjectContentExtractor = Callable[
    [str, GngkTenderGraphState, List[str]], Optional[str]
]


def _clean_word_line(value: str) -> str:
    return value.replace("\x07", "").strip()


def _iter_clean_lines(text: str) -> list[str]:
    return [_clean_word_line(line) for line in re.split(r"[\r\n\x07]+", text)]


def _strip_optional_wrappers(value: str) -> str:
    cleaned = value.strip()
    for left, right in (("[", "]"), ("［", "］"), ("【", "】")):
        if cleaned.startswith(left) and cleaned.endswith(right) and len(cleaned) > 2:
            return cleaned[1:-1].strip()
    return cleaned


def _clean_project_name_candidate(value: str) -> str:
    cleaned = _strip_optional_wrappers(_clean_word_line(value))
    cleaned = re.sub(r"采购$", "", cleaned).strip()
    cleaned = re.split(
        r"\s{2,}|[（(]\s*项目预算|[\/／]?\s*(?:壹|一|贰|二|两|叁|三|肆|四|伍|五|陆|六|柒|七|捌|八|玖|九|拾|十)\s*(?:批|套|台|项|件|只|个|组|节|辆|台/套|台套)|项目预算",
        cleaned,
        maxsplit=1,
    )[0].strip()
    return cleaned.rstrip("：:").strip()


def extract_gngk_project_name(
    doc_content: str,
    first_page_header: str,
    state: GngkTenderGraphState,
    log_parts: List[str],
) -> Optional[str]:
    """Extract GNGK project name, preserving the existing header-first priority."""
    header_value = extract_project_name(
        doc_content,
        first_page_header,
        state,
        log_parts,
    )
    if header_value:
        return header_value
    if not doc_content or not state.get("project_name"):
        return None

    first_page_content = doc_content[:5000]
    title_marker = re.search(r"国内公开招标采购", first_page_content)
    if title_marker:
        title_lines = _iter_clean_lines(first_page_content[: title_marker.start()])
        for line in reversed(title_lines):
            cleaned = _clean_project_name_candidate(line)
            if cleaned and cleaned not in {"中华人民共和国", "招标文件"}:
                log_parts.append(f"从正文封面标题区提取项目名称: {cleaned}")
                return cleaned

    label_pattern = r"项目名称\s*[：:]\s*([^\r\n\x07]+)"
    match = re.search(label_pattern, first_page_content)
    if match:
        cleaned = _clean_project_name_candidate(match.group(1))
        if cleaned:
            log_parts.append(f"从正文项目名称行提取项目名称: {cleaned}")
            return cleaned

    log_parts.append("正文中未找到可提取的 GNGK 项目名称")
    return None


def extract_gngk_project_number(
    doc_content: str,
    first_page_header: str,
    state: GngkTenderGraphState,
    log_parts: List[str],
) -> Optional[str]:
    """Extract GNGK project number, preserving the existing header-first priority."""
    header_value = extract_project_number_from_bid_header(
        doc_content,
        first_page_header,
        state,
        log_parts,
    )
    if header_value:
        return header_value
    if not doc_content or not state.get("project_number"):
        return None

    first_page_content = doc_content[:5000]
    match = re.search(r"招标编号\s*[：:]\s*([^\r\n\x07；;]+)", first_page_content)
    if not match:
        log_parts.append("正文中未找到 '招标编号' 模式")
        return None

    number_text = _clean_word_line(match.group(1))
    extracted_number = extract_numeric_tail_project_number(number_text)
    if extracted_number:
        log_parts.append(
            f"从正文中提取项目编号: {extracted_number} (来源: {number_text})"
        )
        return extracted_number

    log_parts.append(f"无法从正文项目编号文本中提取有效编号: {number_text}")
    return None


def build_gngk_common_extractors(
    project_content_extractor: ProjectContentExtractor = extract_public_tender_project_content,
) -> List[ExtractorSpec]:
    return [
        ExtractorSpec(
            name="project_content",
            enabled_if=lambda state: state.get("project_content") is not None,
            extract_callable=project_content_extractor,
        ),
        ExtractorSpec(
            name="project_content_v2",
            enabled_if=lambda state: state.get("project_content") is not None,
            extract_callable=extract_public_tender_project_content_v2,
        ),
        ExtractorSpec(
            name="project_content_equipment_line",
            enabled_if=lambda state: state.get("project_content") is not None,
            extract_callable=make_public_tender_project_content_labeled_line_extractor(
                "设备名称及数量"
            ),
        ),
        ExtractorSpec(
            name="project_content_procurement_line",
            enabled_if=lambda state: state.get("project_content") is not None,
            extract_callable=make_public_tender_project_content_labeled_line_extractor(
                "采购内容"
            ),
        ),
        ExtractorSpec(
            name="project_number",
            enabled_if=lambda state: state.get("project_number") is not None,
            extract_callable=extract_gngk_project_number,
        ),
        ExtractorSpec(
            name="project_name",
            enabled_if=lambda state: state.get("project_name") is not None,
            extract_callable=extract_gngk_project_name,
        ),
        ExtractorSpec(
            name="bzj_rule",
            enabled_if=lambda state: state.get("bzj_rule") is not None,
            extract_callable=extract_public_tender_bzj_rule,
        ),
        ExtractorSpec(
            name="buyer_name",
            enabled_if=lambda state: state.get("buyer_name") is not None,
            extract_callable=extract_public_tender_buyer_name,
        ),
        ExtractorSpec(
            name="investment",
            enabled_if=lambda state: state.get("investment") is not None,
            extract_callable=extract_public_tender_investment,
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
            extract_callable=extract_public_tender_contact_fields,
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
            extract_callable=extract_public_tender_platform,
        ),
        ExtractorSpec(
            name="service_fee",
            enabled_if=lambda state: state.get("service_fee") is not None,
            extract_callable=extract_service_fee,
        ),
    ]


def build_gngk_common_replacement_fields() -> List[ReplacementFieldSpec]:
    fields = build_common_replacement_fields()
    investment_field = ReplacementFieldSpec(
        field_name="investment",
        new_value_formatter=format_public_tender_investment_value,
    )
    project_content_labeled_fields = [
        ReplacementFieldSpec(
            field_name="project_content_v2",
            fallback_fields=["project_content"],
            new_value_formatter=_strip_project_content_field_label,
        ),
        ReplacementFieldSpec(
            field_name="project_content_equipment_line",
            fallback_fields=["project_content"],
            new_value_formatter=make_public_tender_project_content_labeled_line_formatter(
                "设备名称及数量"
            ),
        ),
        ReplacementFieldSpec(
            field_name="project_content_procurement_line",
            fallback_fields=["project_content"],
            new_value_formatter=make_public_tender_project_content_labeled_line_formatter(
                "采购内容"
            ),
        ),
    ]
    for index, field in enumerate(fields):
        if field.field_name == "project_content":
            fields[index + 1:index + 1] = project_content_labeled_fields
            break
    else:
        fields.extend(project_content_labeled_fields)

    for index, field in enumerate(fields):
        if field.field_name == "buyer_name":
            fields.insert(index + 1, investment_field)
            break
    else:
        fields.append(investment_field)
    return fields


GNGK_COMMON_EXTRACTORS: List[ExtractorSpec] = build_gngk_common_extractors()
GNGK_COMMON_REPLACEMENT_FIELDS: List[
    ReplacementFieldSpec
] = build_gngk_common_replacement_fields()


__all__ = [
    "GNGK_COMMON_EXTRACTORS",
    "GNGK_COMMON_REPLACEMENT_FIELDS",
    "build_gngk_common_extractors",
    "build_gngk_common_replacement_fields",
    "extract_gngk_project_name",
    "extract_gngk_project_number",
]
