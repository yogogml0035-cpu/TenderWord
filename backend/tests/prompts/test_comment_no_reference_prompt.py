from __future__ import annotations

import pytest

from backend.prompts.comment_no_reference_prompt import (
    render_comment_no_reference_prompt,
)
from backend.prompts.types import CommentNoReferencePromptInput


def test_render_comment_no_reference_prompt_keeps_three_dimension_review() -> None:
    rendered = render_comment_no_reference_prompt(
        CommentNoReferencePromptInput(
            tender_type="gngk_hw_zc",
            polished_text="系统稳定性强，投标人须提供原厂授权函。",
        )
    )

    assert "三维审查要求" in rendered.system_prompt
    assert "合规性维度" in rendered.system_prompt
    assert "公平性维度" in rendered.system_prompt
    assert "严谨性维度" in rendered.system_prompt
    assert "系统稳定性强，投标人须提供原厂授权函。" in rendered.user_prompt


def test_render_comment_no_reference_prompt_requires_clean_json_array() -> None:
    rendered = render_comment_no_reference_prompt(
        CommentNoReferencePromptInput(polished_text="投标时须提供原厂授权书原件。")
    )
    combined_prompt = f"{rendered.system_prompt}\n{rendered.user_prompt}"

    assert "纯净 JSON 数组" in combined_prompt
    assert "只输出 JSON 数组本身" in combined_prompt
    assert "`reference_text`" in combined_prompt
    assert "`comment_text`" in combined_prompt
    assert "必须且只能包含 `reference_text` 和 `comment_text` 两个字段" in combined_prompt
    assert "```" not in combined_prompt


def test_render_comment_no_reference_prompt_requires_precise_anchor_from_polished_text() -> None:
    rendered = render_comment_no_reference_prompt(
        CommentNoReferencePromptInput(polished_text="免费维保服务三年。")
    )
    combined_prompt = f"{rendered.system_prompt}\n{rendered.user_prompt}"

    assert "`reference_text` 必须精确来自【修改文本】" in combined_prompt
    assert "连续、逐字、原标点一致" in combined_prompt
    assert "不得改写、概括、补字、删字、改标点" in combined_prompt
    assert "能直接 Ctrl+F 搜索到" in combined_prompt
    assert "无法找到精确锚点时删除该候选" in combined_prompt


def test_render_comment_no_reference_prompt_has_no_reference_draft_logic() -> None:
    rendered = render_comment_no_reference_prompt(
        CommentNoReferencePromptInput(polished_text="技术参数应满足项目需要。")
    )
    combined_prompt = f"{rendered.system_prompt}\n{rendered.user_prompt}"

    assert "批注计划详情" not in combined_prompt
    assert "删除线计划" not in combined_prompt
    assert "非黑色字体计划" not in combined_prompt
    assert "历史参考逻辑" not in combined_prompt
    assert "参考逻辑" not in combined_prompt
    assert "送审稿" not in combined_prompt
    assert "差异" not in combined_prompt


def test_render_comment_no_reference_prompt_rejects_unknown_tender_type() -> None:
    with pytest.raises(ValueError, match="未知的招标类型"):
        render_comment_no_reference_prompt(
            CommentNoReferencePromptInput(tender_type="unknown", polished_text="正文")
        )
