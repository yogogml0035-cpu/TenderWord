from __future__ import annotations

import pytest

from backend.config.tender_config import get_protected_field_profile


@pytest.mark.parametrize(
    ("tender_type", "expected_key"),
    [
        ("xjcg", "common_two_field"),
        ("gngk_hw_zc", "common_two_field"),
        ("gngk_hw_cz", "common_two_field"),
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


def test_get_protected_field_profile_rejects_direct_replace_type() -> None:
    with pytest.raises(ValueError, match="gjgk.*direct_replace.*受保护字段 profile"):
        get_protected_field_profile("gjgk")
