from __future__ import annotations

import pytest

from backend.prompts.comment_prompt import COMMENT_PROMPT_REGISTRY, render_comment_prompt
from backend.prompts.generate_prompt import GENERATE_PROMPT_REGISTRY, render_generate_prompt
from backend.prompts.rewrite_prompt import render_rewrite_prompt
from backend.prompts.routing_prompt import (
    build_rewrite_target_selection_bundle,
    parse_rewrite_target_selection,
    render_rewrite_relevance_prompt,
    render_route_or_reply_prompt,
)
from backend.prompts.types import (
    CommentPromptInput,
    GeneratePromptInput,
    RewriteHistoryMessage,
    RewritePromptInput,
    RewriteRelevancePromptInput,
    RewriteStateSnapshot,
    RewriteTargetSelectionPromptInput,
    RouteHistoryMessage,
    RouteOrReplyPromptInput,
)


def test_generate_prompt_registry_uses_shared_templates_for_current_tender_types():
    assert GENERATE_PROMPT_REGISTRY["xjcg"] == GENERATE_PROMPT_REGISTRY["gngk"]


def test_render_generate_prompt_includes_required_sections():
    rendered = render_generate_prompt(
        GeneratePromptInput(
            tender_type="xjcg",
            project_info="项目基础信息",
            tender_params="技术参数原材料",
            origin_tender_params="参考内容模具",
        )
    )

    assert "高保真招标文件重构引擎" in rendered.system_prompt
    assert "项目基础信息" in rendered.user_prompt
    assert "技术参数原材料" in rendered.user_prompt
    assert "参考内容模具" in rendered.user_prompt


def test_render_comment_prompt_serializes_structured_inputs():
    rendered = render_comment_prompt(
        CommentPromptInput(
            tender_type="gngk",
            polished_text="修改后正文",
            comment_plan_detail=[{"content": "建议补充", "scope_text": "第二章"}],
            strikethrough_plan=[{"paragraph_text": "段落", "strikethrough_text": "删除线"}],
            non_black_font_plan=[{"paragraph_text": "段落", "font_text": "蓝色字体"}],
        )
    )

    assert "纯净 JSON 数组" in rendered.system_prompt
    assert "修改后正文" in rendered.user_prompt
    assert "建议补充" in rendered.user_prompt
    assert "删除线" in rendered.user_prompt
    assert "蓝色字体" in rendered.user_prompt


def test_render_rewrite_prompt_keeps_base_text_and_user_instruction():
    rendered = render_rewrite_prompt(
        RewritePromptInput(base_text="原始正文", user_prompt="把第三章写得更正式")
    )

    assert "招标文档修改助手" in rendered.system_prompt
    assert "原始正文" in rendered.user_prompt
    assert "把第三章写得更正式" in rendered.user_prompt


def test_render_rewrite_relevance_prompt_truncates_document_preview():
    rendered = render_rewrite_relevance_prompt(
        RewriteRelevancePromptInput(
            prompt="请补充售后要求",
            latest_rewrite_state=RewriteStateSnapshot(
                project_number="ZB-001",
                project_name="测试项目",
                tender_type="xjcg",
                polished_text="A" * 700,
            ),
        )
    )

    assert "只输出 true 或 false" in rendered.user_prompt
    assert "project_number=ZB-001" in rendered.user_prompt
    assert "latest_polished_preview=" in rendered.user_prompt
    assert "A" * 601 not in rendered.user_prompt
    assert "..." in rendered.user_prompt


def test_render_route_or_reply_prompt_compresses_history_and_uses_shared_prompt():
    rendered = render_route_or_reply_prompt(
        RouteOrReplyPromptInput(
            messages=[
                RouteHistoryMessage(role="user", content="你好"),
                RouteHistoryMessage(role="assistant", content="欢迎使用"),
                RouteHistoryMessage(role="user", content="B" * 350),
            ],
            latest_user_message="请判断是否要改写",
            latest_rewrite_state=RewriteStateSnapshot(
                project_name="示例项目",
                tender_type="gngk",
                polished_text="C" * 500,
            ),
            has_rewrite_history=True,
        )
    )

    assert "只输出 rewrite" in rendered.system_prompt
    assert "当前不是有效的修改指令" not in rendered.system_prompt
    assert "has_rewrite_history=yes" in rendered.user_prompt
    assert "用户: 你好" in rendered.user_prompt
    assert "助手: 欢迎使用" in rendered.user_prompt
    assert "B" * 301 not in rendered.user_prompt
    assert "C" * 401 not in rendered.user_prompt


def test_build_rewrite_target_selection_bundle_preserves_candidate_order_and_contract():
    bundle = build_rewrite_target_selection_bundle(
        RewriteTargetSelectionPromptInput(
            messages=[
                RewriteHistoryMessage(role="user", content="先改第一版"),
                RewriteHistoryMessage(
                    role="assistant",
                    content="rewrite_success",
                    rewrite_state=RewriteStateSnapshot(
                        tender_type="xjcg",
                        prepared_doc_path="D:/one.docx",
                        polished_text="第一版内容",
                    ),
                    created_at=1.0,
                ),
                RewriteHistoryMessage(role="user", content="再来一版"),
                RewriteHistoryMessage(
                    role="assistant",
                    content="rewrite_success",
                    rewrite_state=RewriteStateSnapshot(
                        tender_type="xjcg",
                        prepared_doc_path="D:/two.docx",
                        polished_text="第二版内容",
                    ),
                    created_at=2.0,
                ),
            ],
            user_prompt="把上一版第三章写正式",
        )
    )

    assert len(bundle.assistant_candidates) == 2
    assert bundle.assistant_candidates[0].assistant_index == 0
    assert bundle.assistant_candidates[1].assistant_index == 1
    assert "candidate_index=0" in bundle.rendered_prompt.user_prompt
    assert "candidate_index=1" in bundle.rendered_prompt.user_prompt
    assert "把上一版第三章写正式" in bundle.rendered_prompt.user_prompt
    assert "请只输出一个纯数字索引。" in bundle.rendered_prompt.user_prompt


def test_parse_rewrite_target_selection_validates_output_shape():
    assert parse_rewrite_target_selection("1", 2) == 1

    with pytest.raises(ValueError):
        parse_rewrite_target_selection("rewrite", 2)

    with pytest.raises(ValueError):
        parse_rewrite_target_selection("3", 2)


def test_comment_prompt_registry_uses_shared_templates_for_current_tender_types():
    assert COMMENT_PROMPT_REGISTRY["xjcg"] == COMMENT_PROMPT_REGISTRY["gngk"]
