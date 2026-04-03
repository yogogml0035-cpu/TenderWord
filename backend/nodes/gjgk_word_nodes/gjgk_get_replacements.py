from __future__ import annotations

import pathlib
import re
import sys
from typing import List, Optional

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
    extract_public_tender_buyer_name,
    extract_public_tender_bzj_rule,
    extract_public_tender_contact_fields,
    extract_public_tender_project_content,
    extract_project_name,
    extract_public_tender_platform,
    extract_service_fee,
    extract_shell_dates,
    extract_submit_date,
    make_project_number_extractor,
)
from backend.states import GjgkTenderGraphState
from backend.util.common_util.tender_number import normalize_gjgk_project_number


extract_gjgk_project_number_from_bid_header = make_project_number_extractor(
    "招标编号",
    value_parser=normalize_gjgk_project_number,
)


def extract_fund_source_lx(
    doc_content: str, state: GjgkTenderGraphState, log_parts: List[str]
) -> Optional[str]:
    if not doc_content or state.get("fund_source_lx") in (None, ""):
        return None

    patterns = (
        r"(?:资金来源|资金性质|资金落实情况)\s*[：:]\s*([^\n\r]+)",
        r"(?:项目资金来源)\s*[：:]\s*([^\n\r]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, doc_content)
        if match:
            extracted = match.group(1).strip()
            log_parts.append(f"提取 fund_source_lx 占位值: {extracted}")
            return extracted

    log_parts.append("未找到 fund_source_lx 占位值")
    return None


def extract_tender_invitation(
    doc_content: str, state: GjgkTenderGraphState, log_parts: List[str]
) -> Optional[str]:
    if not doc_content or not state.get("tender_invitation"):
        return None

    patterns = (
        r"(项目名称\s*[：:]\s*[^\n\r，,]+[，,]\s*招标编号\s*[：:]\s*[^\n\r]+)",
        r"(项目名称\s*[：:]\s*[^\n\r]+招标编号\s*[：:]\s*[^\n\r]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, doc_content)
        if match:
            extracted = match.group(1).strip()
            log_parts.append(f"提取 tender_invitation 占位值: {extracted}")
            return extracted

    log_parts.append("未找到 tender_invitation 占位值")
    return None


def extract_delivery_location(
    doc_content: str, state: GjgkTenderGraphState, log_parts: List[str]
) -> Optional[str]:
    del state
    if not doc_content:
        return None

    pattern = r"(?:交货地点|交付地点|项目现场)\s*[：:]\s*([^\n\r]+)"
    match = re.search(pattern, doc_content)
    if match:
        extracted = match.group(1).strip()
        log_parts.append(f"提取 delivery_location 占位值: {extracted}")
        return extracted

    log_parts.append("未找到 delivery_location 占位值")
    return None


GJGK_EXTRACTORS: List[ExtractorSpec] = [
    ExtractorSpec(
        name="project_content",
        enabled_if=lambda state: state.get("project_content") is not None,
        extract_callable=extract_public_tender_project_content,
    ),
    ExtractorSpec(
        name="project_number",
        enabled_if=lambda state: state.get("project_number") is not None,
        extract_callable=extract_gjgk_project_number_from_bid_header,
    ),
    ExtractorSpec(
        name="project_name",
        enabled_if=lambda state: state.get("project_name") is not None,
        extract_callable=extract_project_name,
    ),
    ExtractorSpec(
        name="buyer_name",
        enabled_if=lambda state: state.get("buyer_name") is not None,
        extract_callable=extract_public_tender_buyer_name,
    ),
    ExtractorSpec(
        name="bzj_rule",
        enabled_if=lambda state: state.get("bzj_rule") is not None,
        extract_callable=extract_public_tender_bzj_rule,
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
    ExtractorSpec(
        name="fund_source_lx",
        enabled_if=lambda state: state.get("fund_source_lx") is not None,
        extract_callable=extract_fund_source_lx,
    ),
    ExtractorSpec(
        name="tender_invitation",
        enabled_if=lambda state: True,
        extract_callable=extract_tender_invitation,
    ),
    ExtractorSpec(
        name="delivery_location",
        enabled_if=lambda state: True,
        extract_callable=extract_delivery_location,
    ),
]


GJGK_REPLACEMENT_FIELDS: List[ReplacementFieldSpec] = build_common_replacement_fields()


def gjgk_get_replacements(
    state: GjgkTenderGraphState, config
) -> GjgkTenderGraphState:
    return run_get_replacements(
        state=state,
        config=config,
        extractors=GJGK_EXTRACTORS,
        replacement_fields=GJGK_REPLACEMENT_FIELDS,
    )
