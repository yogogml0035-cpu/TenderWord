"""
gngk_fw_zc_delete_tender_param 节点的单元测试。

重写后的删除节点是独立实现，不再依赖 common delete_tender_param
的 FunctionType 注入方式。这些测试验证核心辅助函数的正确性。
"""

from __future__ import annotations

import importlib

delete_module = importlib.import_module(
    "backend.nodes.gngk_word_nodes.gngk_fw_zc_delete_tender_param"
)


def test_normalize_cleanup_text_removes_invisible_chars() -> None:
    text = "\r\n服务地点\t\u00a0\u200b"
    result = delete_module._normalize_cleanup_text(text)
    assert result == "服务地点"


def test_normalize_cleanup_text_empty() -> None:
    assert delete_module._normalize_cleanup_text("") == ""
    assert delete_module._normalize_cleanup_text("\r\n\t") == ""


def test_is_effectively_empty_text() -> None:
    assert delete_module._is_effectively_empty_text("") is True
    assert delete_module._is_effectively_empty_text("\r\n") is True
    assert delete_module._is_effectively_empty_text("\u200b\u00a0") is True
    assert delete_module._is_effectively_empty_text("内容") is False


def test_range_overlaps() -> None:
    assert delete_module._range_overlaps(0, 10, 5, 15) is True
    assert delete_module._range_overlaps(0, 10, 10, 20) is False
    assert delete_module._range_overlaps(5, 15, 0, 10) is True
    assert delete_module._range_overlaps(0, 5, 10, 15) is False


def test_is_protected_range_with_overlap() -> None:
    class FakeRange:
        def __init__(self, start, end):
            self.Start = start
            self.End = end

    protected_fields = {
        "服务地点": FakeRange(10, 20),
        "服务期限": FakeRange(30, 40),
    }

    # 与受保护字段重叠
    assert delete_module._is_protected_range(FakeRange(15, 25), protected_fields) is True
    # 不重叠
    assert delete_module._is_protected_range(FakeRange(0, 5), protected_fields) is False
    # 完全在受保护字段内
    assert delete_module._is_protected_range(FakeRange(12, 18), protected_fields) is True


def test_is_protected_range_no_overlap() -> None:
    class FakeRange:
        def __init__(self, start, end):
            self.Start = start
            self.End = end

    protected_fields = {
        "付款方式": FakeRange(50, 60),
    }

    assert delete_module._is_protected_range(FakeRange(0, 49), protected_fields) is False
    assert delete_module._is_protected_range(FakeRange(60, 70), protected_fields) is False


def test_visible_text_strips_all_invisible() -> None:
    text = "\r\n\x07\x0b\x0c\a \t\u00a0\u3000\u200b\ufeff内容\r"
    result = delete_module._visible_text(text)
    assert result == "内容"


def test_visible_text_empty() -> None:
    assert delete_module._visible_text("") == ""
    assert delete_module._visible_text("\r\n\t ") == ""


def test_require_all_protected_fields_raises_on_missing() -> None:
    import pytest

    with pytest.raises(ValueError, match="缺少关键受保护字段"):
        delete_module._require_all_protected_fields(
            {"服务地点": None, "服务期限": None},
            required_keywords=("服务地点", "服务期限", "付款方式"),
        )


def test_require_all_protected_fields_passes_when_all_present() -> None:
    # Should not raise
    delete_module._require_all_protected_fields(
        {"服务地点": None, "服务期限": None, "付款方式": None},
        required_keywords=("服务地点", "服务期限", "付款方式"),
    )
