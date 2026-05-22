from __future__ import annotations

import pytest

from backend.config.tender_config import (
    CONTENT_START_MODE_SAME_PAGE_AFTER_ANCHOR,
    CONTENT_UPDATE_MODE_DIRECT_REPLACE,
    get_anchor_target_sizes,
    get_content_start_mode,
    get_content_update_mode,
    get_default_anchor_texts,
    get_protected_field_profile,
)


@pytest.mark.parametrize(
    ("tender_type", "expected_key"),
    [
        ("xjcg", "common_two_field"),
        ("gngk_hw_zc", "common_two_field"),
        ("gngk_fw_cz", "common_two_field"),
        ("gngk_fw_zc", "gngk_three_field"),
    ],
)
def test_get_protected_field_profile_resolves_expected_profile(
    tender_type: str,
    expected_key: str,
) -> None:
    profile = get_protected_field_profile(tender_type)

    assert profile.key == expected_key


def test_gngk_hw_cz_uses_same_page_direct_replace_anchor_config() -> None:
    assert get_default_anchor_texts("gngk_hw_cz") == (
        "第四章  招标需求",
        "第五章  评标方法与程序",
    )
    assert get_anchor_target_sizes("gngk_hw_cz") == (22.0, 22.0)
    assert (
        get_content_start_mode("gngk_hw_cz")
        == CONTENT_START_MODE_SAME_PAGE_AFTER_ANCHOR
    )
    assert get_content_update_mode("gngk_hw_cz") == CONTENT_UPDATE_MODE_DIRECT_REPLACE


def test_get_protected_field_profile_rejects_direct_replace_type() -> None:
    with pytest.raises(
        ValueError,
        match="gngk_hw_cz.*direct_replace.*受保护字段 profile",
    ):
        get_protected_field_profile("gngk_hw_cz")
