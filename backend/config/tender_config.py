"""招标类型配置模块.

集中管理各种招标类型的锚点文本与字号配置，避免在多个节点文件中重复定义。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


CONTENT_START_MODE_NEXT_PAGE_START = "next_page_start"
CONTENT_START_MODE_SAME_PAGE_AFTER_ANCHOR = "same_page_after_anchor"

CONTENT_UPDATE_MODE_PROTECTED_FIELDS = "protected_fields"
CONTENT_UPDATE_MODE_DIRECT_REPLACE = "direct_replace"


@dataclass(frozen=True)
class TenderAnchorConfig:
    before_text: str
    after_text: str
    before_size: float
    after_size: float
    content_start_mode: str = CONTENT_START_MODE_NEXT_PAGE_START
    content_update_mode: str = CONTENT_UPDATE_MODE_PROTECTED_FIELDS


@dataclass(frozen=True)
class ProtectedFieldProfile:
    key: str
    ordered_markers: tuple[str, ...]
    require_all: bool = True
    require_order: bool = True


# 历史单字号配置仍保留给旧逻辑/默认回退使用，避免误伤现有类型。
TARGET_SIZES: Dict[str, float] = {
    "xjcg": 18.0,
    "gngk": 22.0,
    "gngk_hw_zc": 22.0,
    "gngk_hw_cz": 22.0,
    "gngk_fw_zc": 22.0,
    "gngk_fw_cz": 22.0,
    "gngk_zc": 22.0,
    "gngk_cz": 22.0,
}


DEFAULT_TENDER_TYPE = "xjcg"
COMMON_TWO_FIELD_PROFILE_KEY = "common_two_field"
GNGK_THREE_FIELD_PROFILE_KEY = "gngk_three_field"
GNGK_TENDER_TYPES = frozenset(
    {
        "gngk",
        "gngk_hw_zc",
        "gngk_hw_cz",
        "gngk_fw_zc",
        "gngk_fw_cz",
        "gngk_zc",
        "gngk_cz",
    }
)

ANCHOR_CONFIGS: Dict[str, TenderAnchorConfig] = {
    "xjcg": TenderAnchorConfig(
        before_text="第三章  采购需求",
        after_text="第四章  响应文件有关格式",
        before_size=18.0,
        after_size=18.0,
    ),
    "gngk": TenderAnchorConfig(
        before_text="第三章 招标内容及要求",
        after_text="第四章 投标文件有关格式",
        before_size=22.0,
        after_size=22.0,
    ),
    "gngk_hw_zc": TenderAnchorConfig(
        before_text="第三章 招标内容及要求",
        after_text="第四章 投标文件有关格式",
        before_size=22.0,
        after_size=22.0,
    ),
    "gngk_fw_zc": TenderAnchorConfig(
        before_text="第三章 招标内容及要求",
        after_text="第四章 合同条款",
        before_size=22.0,
        after_size=22.0,
    ),
    "gngk_hw_cz": TenderAnchorConfig(
        before_text="第四章  招标需求",
        after_text="第五章  评标方法与程序",
        before_size=22.0,
        after_size=22.0,
    ),
    "gngk_fw_cz": TenderAnchorConfig(
        before_text="第三章 招标内容及要求",
        after_text="第四章 合同条款",
        before_size=22.0,
        after_size=22.0,
    ),
    "gngk_zc": TenderAnchorConfig(
        before_text="第三章 招标内容及要求",
        after_text="第四章 投标文件有关格式",
        before_size=22.0,
        after_size=22.0,
    ),
    "gngk_cz": TenderAnchorConfig(
        before_text="第四章  招标需求",
        after_text="第五章  评标方法与程序",
        before_size=22.0,
        after_size=22.0,
    ),
    "gjgk": TenderAnchorConfig(
        before_text="技术规格及要求",
        after_text="附件1：投标文件封面（格式）",
        before_size=16.0,
        after_size=14.0,
        content_start_mode=CONTENT_START_MODE_SAME_PAGE_AFTER_ANCHOR,
        content_update_mode=CONTENT_UPDATE_MODE_DIRECT_REPLACE,
    ),
}

PROTECTED_FIELD_PROFILES: Dict[str, ProtectedFieldProfile] = {
    COMMON_TWO_FIELD_PROFILE_KEY: ProtectedFieldProfile(
        key=COMMON_TWO_FIELD_PROFILE_KEY,
        ordered_markers=("交付日期：", "付款方式："),
    ),
    GNGK_THREE_FIELD_PROFILE_KEY: ProtectedFieldProfile(
        key=GNGK_THREE_FIELD_PROFILE_KEY,
        ordered_markers=("服务地点：", "服务期限：", "付款方式："),
    ),
}

PROTECTED_FIELD_PROFILE_OVERRIDES: Dict[str, str] = {
    "gngk_fw_zc": GNGK_THREE_FIELD_PROFILE_KEY,
}


def get_anchor_config(tender_type: str) -> TenderAnchorConfig:
    normalized_type = str(tender_type or "").strip() or DEFAULT_TENDER_TYPE
    if normalized_type in ANCHOR_CONFIGS:
        return ANCHOR_CONFIGS[normalized_type]

    fallback_size = TARGET_SIZES.get(normalized_type, TARGET_SIZES[DEFAULT_TENDER_TYPE])
    fallback_anchor = ANCHOR_CONFIGS[DEFAULT_TENDER_TYPE]
    return TenderAnchorConfig(
        before_text=fallback_anchor.before_text,
        after_text=fallback_anchor.after_text,
        before_size=fallback_size,
        after_size=fallback_size,
    )


def get_tender_type_family(tender_type: str | None) -> str:
    """将运行态 tender_type 归并到共享行为族。"""
    normalized_type = str(tender_type or "").strip() or DEFAULT_TENDER_TYPE
    if normalized_type in GNGK_TENDER_TYPES:
        return "gngk"
    return normalized_type


def get_default_anchor_texts(tender_type: str) -> tuple[str, str]:
    anchor_config = get_anchor_config(tender_type)
    return anchor_config.before_text, anchor_config.after_text


def get_anchor_target_sizes(tender_type: str) -> tuple[float, float]:
    anchor_config = get_anchor_config(tender_type)
    return anchor_config.before_size, anchor_config.after_size


def get_content_start_mode(tender_type: str) -> str:
    anchor_config = get_anchor_config(tender_type)
    return anchor_config.content_start_mode


def get_content_update_mode(tender_type: str) -> str:
    anchor_config = get_anchor_config(tender_type)
    return anchor_config.content_update_mode


def get_protected_field_profile(tender_type: str) -> ProtectedFieldProfile:
    normalized_type = str(tender_type or "").strip() or DEFAULT_TENDER_TYPE
    content_update_mode = get_content_update_mode(normalized_type)
    if content_update_mode != CONTENT_UPDATE_MODE_PROTECTED_FIELDS:
        raise ValueError(
            f"招标类型 {normalized_type} 使用 {content_update_mode} 模式，不支持受保护字段 profile"
        )

    profile_key = PROTECTED_FIELD_PROFILE_OVERRIDES.get(
        normalized_type,
        COMMON_TWO_FIELD_PROFILE_KEY,
    )
    profile = PROTECTED_FIELD_PROFILES.get(profile_key)
    if profile is None:
        raise ValueError(f"未找到受保护字段 profile: {profile_key}")
    return profile


def get_target_size(tender_type: str) -> float:
    """获取指定招标类型的默认字号回退值。"""
    before_size, after_size = get_anchor_target_sizes(tender_type)
    if abs(before_size - after_size) < 0.01:
        return before_size
    return TARGET_SIZES.get(str(tender_type or "").strip(), before_size)
