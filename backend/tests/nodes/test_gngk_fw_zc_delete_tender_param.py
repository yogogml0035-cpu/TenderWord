"""
gngk_fw_zc_delete_tender_param 节点的单元测试。

重写后的删除节点是独立实现，不再依赖 common delete_tender_param
的 FunctionType 注入方式。这些测试验证核心辅助函数的正确性。
"""

from __future__ import annotations

import importlib

import pytest

from backend.config.tender_config import get_protected_field_profile
from backend.helper.word_helper.cleanup_ops import (
    normalize_cleanup_text,
    is_effectively_empty_text,
)
from backend.helper.word_helper.protected_fields import (
    validate_profile_required_protected_fields,
)
from backend.helper.word_helper.range_utils import (
    range_overlaps,
    is_protected_range,
)

GNGK_THREE_FIELD_PROFILE = get_protected_field_profile("gngk_fw_zc")
delete_module = importlib.import_module(
    "backend.nodes.gngk_word_nodes.gngk_fw_zc_delete_tender_param"
)


def test_normalize_cleanup_text_removes_invisible_chars() -> None:
    text = "\r\n服务地点\t\u00a0\u200b"
    result = normalize_cleanup_text(text)
    assert result == "服务地点"


def test_normalize_cleanup_text_empty() -> None:
    assert normalize_cleanup_text("") == ""
    assert normalize_cleanup_text("\r\n\t") == ""


def test_is_effectively_empty_text() -> None:
    assert is_effectively_empty_text("") is True
    assert is_effectively_empty_text("\r\n") is True
    assert is_effectively_empty_text("\u200b\u00a0") is True
    assert is_effectively_empty_text("内容") is False


def test_range_overlaps() -> None:
    assert range_overlaps(0, 10, 5, 15) is True
    assert range_overlaps(0, 10, 10, 20) is False
    assert range_overlaps(5, 15, 0, 10) is True
    assert range_overlaps(0, 5, 10, 15) is False


def test_is_protected_range_with_overlap() -> None:
    class FakeRange:
        def __init__(self, start, end):
            self.Start = start
            self.End = end

    protected_fields = {
        "服务地点：": FakeRange(10, 20),
        "服务期限：": FakeRange(30, 40),
    }

    # 与受保护字段重叠
    assert is_protected_range(FakeRange(15, 25), protected_fields) is True
    # 不重叠
    assert is_protected_range(FakeRange(0, 5), protected_fields) is False
    # 完全在受保护字段内
    assert is_protected_range(FakeRange(12, 18), protected_fields) is True


def test_is_protected_range_no_overlap() -> None:
    class FakeRange:
        def __init__(self, start, end):
            self.Start = start
            self.End = end

    protected_fields = {
        "付款方式：": FakeRange(50, 60),
    }

    assert is_protected_range(FakeRange(0, 49), protected_fields) is False
    assert is_protected_range(FakeRange(60, 70), protected_fields) is False


def test_visible_text_strips_all_invisible() -> None:
    text = "\r\n\x07\x0b\x0c\a \t\u00a0\u3000\u200b\ufeff内容\r"
    result = normalize_cleanup_text(text)
    assert result == "内容"


def test_visible_text_empty() -> None:
    assert normalize_cleanup_text("") == ""
    assert normalize_cleanup_text("\r\n\t ") == ""


def test_require_all_protected_fields_raises_on_missing() -> None:
    with pytest.raises(ValueError, match="缺少关键受保护字段: 付款方式："):
        validate_profile_required_protected_fields(
            {"服务地点：": None, "服务期限：": None},
            GNGK_THREE_FIELD_PROFILE,
        )


def test_require_all_protected_fields_passes_when_all_present() -> None:
    # Should not raise
    validate_profile_required_protected_fields(
        {"服务地点：": None, "服务期限：": None, "付款方式：": None},
        GNGK_THREE_FIELD_PROFILE,
    )


def test_restore_payment_tail_paragraph_boundary_delegates_to_shared_helper(
    monkeypatch,
) -> None:
    captured: list[tuple[object, str, int]] = []

    def fake_shared_helper(doc, paragraph_range, **kwargs):
        captured.append(
            (
                paragraph_range,
                str(kwargs.get("field_name") or ""),
                int(kwargs.get("scan_bound_end") or 0),
            )
        )
        return True, 188

    monkeypatch.setattr(
        delete_module,
        "ensure_paragraph_break_after_paragraph",
        fake_shared_helper,
    )

    payment_range = object()
    log_parts: list[str] = []
    restored = delete_module._restore_payment_tail_paragraph_boundary(
        doc=object(),
        protected_fields={"付款方式：": payment_range},
        get_bound_end=lambda: 260,
        tender_type="gngk_fw_zc",
        log_parts=log_parts,
    )

    assert restored is True
    assert captured == [(payment_range, "付款方式", 260)]
    assert any("已补齐付款方式后的段落边界。" in line for line in log_parts)
