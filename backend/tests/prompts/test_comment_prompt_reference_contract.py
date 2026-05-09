from __future__ import annotations

from backend.prompts.comment_prompt import render_comment_prompt
from backend.prompts.types import CommentPromptInput


def test_render_comment_prompt_requires_precise_unique_reference_text() -> None:
    rendered = render_comment_prompt(
        CommentPromptInput(
            tender_type="gjgk",
            polished_text="系统稳定性强，服务免费。",
            comment_plan_detail=[],
            strikethrough_plan=[],
            non_black_font_plan=[],
        )
    )

    assert "Ctrl+F 精确搜索" in rendered.system_prompt
    assert "不得改写、概括、补字、删字、改标点" in rendered.system_prompt
    assert "不要单独使用“最优”“稳定性”“免费”“≥”" in rendered.system_prompt
    assert "仍无法唯一定位时，删除该条" in rendered.system_prompt
    assert "禁止把不连续片段拼成一个 `reference_text`" in rendered.system_prompt

    assert "连续、逐字、可 Ctrl+F 精确搜索到" in rendered.user_prompt
    assert "短词风险必须扩展为同一句、同一分句或同一单元格内的连续原文" in rendered.user_prompt
    assert "无法找到可精确回填的唯一原文锚点，请输出空数组" in rendered.user_prompt
