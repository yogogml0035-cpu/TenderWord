from __future__ import annotations

import re
from dataclasses import dataclass

from backend.states import TenderGraphStateBase


@dataclass(frozen=True)
class GjgkReplacementEntry:
    field_name: str | None
    search_text: str
    replace_text: str
    comment_label: str | None = None


def _normalize_code(value) -> str:
    if value in (None, ""):
        return ""
    return str(value).strip()


def _map_fund_source_lx(value) -> str | None:
    normalized = _normalize_code(value)
    if normalized == "0":
        return "自筹资金"
    if normalized == "1":
        return "财政资金"
    return None


def extract_delivery_location_from_polished_text(polished_text: str | None) -> str | None:
    text = str(polished_text or "").replace("\r\n", "\n").replace("\r", "\n")
    if not text.strip():
        return None

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        match = re.match(r"^(交货地点|交付地点|项目现场)\s*[：:]\s*(.+)$", stripped)
        if match:
            value = match.group(2).strip()
            return value or None
    return None


def build_gjgk_special_replacements(
    state: TenderGraphStateBase,
) -> tuple[list[GjgkReplacementEntry], dict[str, str], list[str]]:
    placeholder_mapping = state.get("placeholder_mapping", {}) or {}
    log_parts: list[str] = []
    derived_updates: dict[str, str] = {}
    entries: list[GjgkReplacementEntry] = []

    old_fund_source = str(placeholder_mapping.get("fund_source_lx") or "").strip()
    mapped_fund_source = _map_fund_source_lx(state.get("fund_source_lx"))
    if old_fund_source and mapped_fund_source:
        if old_fund_source != mapped_fund_source:
            entries.append(
                GjgkReplacementEntry(
                    field_name="fund_source_lx",
                    search_text=old_fund_source,
                    replace_text=mapped_fund_source,
                    comment_label="ERP数据",
                )
            )
        else:
            log_parts.append("gjgk: fund_source_lx 文案与模板一致，跳过替换")
    elif old_fund_source and not mapped_fund_source:
        log_parts.append(
            f"gjgk: 未识别的 fund_source_lx 编码 {state.get('fund_source_lx')!r}，仅记录日志不替换"
        )

    old_tender_invitation = str(placeholder_mapping.get("tender_invitation") or "").strip()
    new_tender_invitation = str(state.get("tender_invitation") or "").strip()
    if old_tender_invitation and new_tender_invitation:
        if old_tender_invitation != new_tender_invitation:
            entries.append(
                GjgkReplacementEntry(
                    field_name="tender_invitation",
                    search_text=old_tender_invitation,
                    replace_text=new_tender_invitation,
                    comment_label="ERP数据",
                )
            )
        else:
            log_parts.append("gjgk: tender_invitation 与模板一致，跳过替换")

    old_delivery_location = str(placeholder_mapping.get("delivery_location") or "").strip()
    extracted_delivery_location = extract_delivery_location_from_polished_text(
        state.get("polished_text")
    )
    if extracted_delivery_location:
        derived_updates["delivery_location"] = extracted_delivery_location
        if old_delivery_location and old_delivery_location != extracted_delivery_location:
            entries.append(
                GjgkReplacementEntry(
                    field_name="delivery_location",
                    search_text=old_delivery_location,
                    replace_text=extracted_delivery_location,
                    comment_label="技术参数数据",
                )
            )
    elif old_delivery_location:
        derived_updates["delivery_location"] = old_delivery_location
        log_parts.append("gjgk: 未从 polished_text 提取到 delivery_location，保留模板原值")

    return entries, derived_updates, log_parts
