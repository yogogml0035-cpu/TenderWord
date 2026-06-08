from __future__ import annotations

from backend.prompts.comment_prompt import (
    render_comment_prompt,
    render_comment_prompt_with_bad_case_context,
)
from backend.prompts.types import CommentPromptInput


def test_retrieval_aware_comment_prompt_matches_base_prompt_without_context() -> None:
    prompt_input = CommentPromptInput(
        tender_type="gjgk",
        polished_text="系统稳定性强，服务免费。",
    )
    base_prompt = render_comment_prompt(prompt_input)

    assert render_comment_prompt_with_bad_case_context(prompt_input) == base_prompt
    assert (
        render_comment_prompt_with_bad_case_context(prompt_input, [])
        == base_prompt
    )
    assert (
        render_comment_prompt_with_bad_case_context(
            prompt_input,
            [
                {
                    "risk_type": "",
                    "risk_pattern": "",
                    "recommended_comment_policy": "",
                    "applicability_boundary": "",
                    "anchor_policy": "",
                }
            ],
        )
        == base_prompt
    )


def test_retrieval_aware_comment_prompt_appends_structured_bad_case_rules() -> None:
    prompt_input = CommentPromptInput(
        tender_type="gjgk",
        polished_text="投标人须提供原厂授权函。",
    )
    base_prompt = render_comment_prompt(prompt_input)

    rendered = render_comment_prompt_with_bad_case_context(
        prompt_input,
        [
            {
                "case_id": "TW_COMMENT_SHOULD_NOT_RENDER",
                "score": 0.99,
                "risk_type": "合规风险",
                "risk_pattern": "原厂授权作为资格条件",
                "recommended_comment_policy": "建议提示：除进口产品外，不应要求原厂授权。",
                "applicability_boundary": "适用于非进口货物采购资格条件。",
                "anchor_policy": "锚定当前正文中的原厂授权要求。",
                "matched_clause_text": "命中条款正文不应进入 prompt",
            }
        ],
    )

    assert rendered.system_prompt.startswith(base_prompt.system_prompt.rstrip())
    assert "可能包含【bad_case参考规则】" in rendered.system_prompt
    assert "如果存在，该规则块只能作为风险判断" in rendered.system_prompt
    assert "无论是否存在 bad case 规则块" in rendered.system_prompt
    assert "严禁把 bad case 文本、风险模式或推荐口径当作 `reference_text`" in rendered.system_prompt

    assert rendered.user_prompt.startswith(base_prompt.user_prompt.rstrip())
    assert "【bad_case参考规则】" in rendered.user_prompt
    assert "风险类型: 合规风险" in rendered.user_prompt
    assert "风险模式: 原厂授权作为资格条件" in rendered.user_prompt
    assert "推荐批注口径: 建议提示：除进口产品外，不应要求原厂授权。" in rendered.user_prompt
    assert "适用边界: 适用于非进口货物采购资格条件。" in rendered.user_prompt
    assert "锚点策略: 锚定当前正文中的原厂授权要求。" in rendered.user_prompt
    assert "`reference_text` 只能来自上方【修改文本】" in rendered.user_prompt

    assert "TW_COMMENT_SHOULD_NOT_RENDER" not in rendered.user_prompt
    assert "0.99" not in rendered.user_prompt
    assert "命中条款正文不应进入 prompt" not in rendered.user_prompt
    assert "case_id" not in rendered.user_prompt
