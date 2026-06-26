from __future__ import annotations

from backend.agents.generation.content_sanitizer import (
    looks_like_procurement_content,
    sanitize_generated_content,
)


def test_sanitize_strips_ai_preamble_and_tail() -> None:
    text = (
        "好的，已收到您的指令。\n"
        "1、技术参数：A。\n"
        "2、配置清单：主机1台。\n"
        "以上为最终重构内容，请核对确认。"
    )

    cleaned = sanitize_generated_content(text)

    assert "好的" not in cleaned
    assert "已收到您的指令" not in cleaned
    assert "以上为最终重构内容" not in cleaned
    assert "请核对确认" not in cleaned
    assert "1、技术参数：A。" in cleaned
    assert "2、配置清单：主机1台。" in cleaned


def test_sanitize_strips_markdown_code_fence_and_inline_decorations() -> None:
    text = (
        "```markdown\n"
        "## 技术要求\n"
        "**1、屏幕尺寸：15英寸**\n"
        "2、分辨率：4K\n"
        "```"
    )

    cleaned = sanitize_generated_content(text)

    assert "```" not in cleaned
    assert "##" not in cleaned
    assert "**" not in cleaned
    assert "技术要求" in cleaned
    assert "1、屏幕尺寸：15英寸" in cleaned
    assert "2、分辨率：4K" in cleaned


def test_sanitize_strips_filler_placeholder_sentences() -> None:
    text = (
        "三、配置清单\n"
        "须提供详细配置清单。\n"
        "四、技术参数\n"
        "3、须提供详细技术参数要求\n"
        "1、功率：100W。\n"
    )

    cleaned = sanitize_generated_content(text)

    assert "须提供详细配置清单" not in cleaned
    assert "须提供详细技术参数要求" not in cleaned
    # 章节标题与真实参数保留。
    assert "三、配置清单" in cleaned
    assert "四、技术参数" in cleaned
    assert "1、功率：100W。" in cleaned


def test_sanitize_preserves_technical_symbols_and_importance_markers() -> None:
    text = (
        "1、波长范围：400-700nm。\n"
        "★2、分辨率：≥4K。\n"
        "Δ3.1.1 接口：USB≥4个。\n"
        "3、精度：±0.1%，SpO₂ 误差≤2%。\n"
    )

    cleaned = sanitize_generated_content(text)

    # 技术符号（≥/±/SpO₂）和重要性标识（★/Δ）按原样保留，不被清洗。
    assert "≥4K" in cleaned
    assert "±0.1%" in cleaned
    assert "SpO₂" in cleaned
    assert "★2、分辨率" in cleaned
    assert "Δ3.1.1 接口" in cleaned


def test_sanitize_preserves_table_placeholder_lines() -> None:
    text = (
        "1、技术参数：A。\n"
        "[[TABLE:TP1_1]]\n"
        "2、备注：B。\n"
    )

    cleaned = sanitize_generated_content(text)

    # `[[TABLE:id]]` 是内部写回入口，sanitizer 不删除，交由写回层处理。
    assert "[[TABLE:TP1_1]]" in cleaned
    assert "1、技术参数：A。" in cleaned


def test_sanitize_collapses_blank_lines_and_trims_ends() -> None:
    text = "\n\n1、参数：A。\n\n\n\n2、参数：B。\n\n"

    cleaned = sanitize_generated_content(text)

    assert cleaned == "1、参数：A。\n\n2、参数：B。"


def test_sanitize_returns_empty_for_blank_input() -> None:
    assert sanitize_generated_content("") == ""
    assert sanitize_generated_content("   \n  \n") == ""


def test_sanitize_returns_empty_after_stripping_all_noise() -> None:
    text = "好的，已收到您的指令。\n以上为最终内容。\n须提供详细配置清单。"

    assert sanitize_generated_content(text) == ""


def test_looks_like_procurement_content_detects_real_content() -> None:
    assert looks_like_procurement_content("1、技术参数：A。\n2、配置：B。") is True
    assert looks_like_procurement_content("设备名称：高频电刀") is True
    assert looks_like_procurement_content("| 序号 | 参数 |\n| 1 | A |") is True
    assert looks_like_procurement_content("[[TABLE:TP1]]") is True


def test_looks_like_procurement_content_rejects_empty_or_pure_noise() -> None:
    assert looks_like_procurement_content("") is False
    assert looks_like_procurement_content("好的，已收到指令。\n以上为最终内容。") is False
