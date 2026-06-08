"""Unified prompt builders and contracts."""

from backend.prompts.comment_prompt import (
    COMMENT_PROMPT_REGISTRY,
    COMMENT_SYSTEM_PROMPT,
    COMMENT_USER_PROMPT,
    render_comment_prompt,
    render_comment_prompt_with_bad_case_context,
)
from backend.prompts.generate_by_param_prompt import (
    GENERATE_BY_PARAM_PROMPT_REGISTRY,
    PARAM_POLISH_SYSTEM_PROMPT,
    PARAM_POLISH_USER_PROMPT,
    render_generate_by_param_prompt,
)
from backend.prompts.generate_by_template_prompt import (
    GENERATE_BY_TEMPLATE_PROMPT_REGISTRY,
    TEMPLATE_POLISH_SYSTEM_PROMPT,
    TEMPLATE_POLISH_USER_PROMPT,
    render_generate_by_template_prompt,
)
from backend.prompts.generate_prompt import (
    GENERATE_PROMPT_REGISTRY,
    POLISH_SYSTEM_PROMPT,
    POLISH_USER_PROMPT,
    normalize_generation_style,
    render_generate_prompt,
)
from backend.prompts.rewrite_target_selection_prompt import (
    JUDGE_TARGET_SYSTEM_PROMPT,
    build_rewrite_target_selection_bundle,
    parse_rewrite_target_selection,
)
from backend.prompts.skill_prompt import render_task_skill_prompt
from backend.prompts.template_candidate_ranking_prompt import (
    TEMPLATE_CANDIDATE_RANKING_SYSTEM_PROMPT,
    parse_template_candidate_ranking_output,
    render_template_candidate_ranking_prompt,
)
from backend.prompts.types import (
    CommentPromptInput,
    GeneratePromptInput,
    RenderedPrompt,
    RewriteAssistantCandidate,
    RewriteHistoryMessage,
    RewriteStateSnapshot,
    TaskSkillPromptInput,
    TaskSkillPromptSection,
    TemplateCandidateRankingItem,
    TemplateCandidateRankingPromptInput,
    RewriteTargetSelectionBundle,
    RewriteTargetSelectionPromptInput,
)

__all__ = [
    "COMMENT_PROMPT_REGISTRY",
    "COMMENT_SYSTEM_PROMPT",
    "COMMENT_USER_PROMPT",
    "CommentPromptInput",
    "GENERATE_BY_PARAM_PROMPT_REGISTRY",
    "GENERATE_BY_TEMPLATE_PROMPT_REGISTRY",
    "GENERATE_PROMPT_REGISTRY",
    "GeneratePromptInput",
    "JUDGE_TARGET_SYSTEM_PROMPT",
    "PARAM_POLISH_SYSTEM_PROMPT",
    "PARAM_POLISH_USER_PROMPT",
    "POLISH_SYSTEM_PROMPT",
    "POLISH_USER_PROMPT",
    "RenderedPrompt",
    "RewriteAssistantCandidate",
    "RewriteHistoryMessage",
    "RewriteStateSnapshot",
    "TaskSkillPromptInput",
    "TaskSkillPromptSection",
    "TEMPLATE_CANDIDATE_RANKING_SYSTEM_PROMPT",
    "TEMPLATE_POLISH_SYSTEM_PROMPT",
    "TEMPLATE_POLISH_USER_PROMPT",
    "TemplateCandidateRankingItem",
    "TemplateCandidateRankingPromptInput",
    "RewriteTargetSelectionBundle",
    "RewriteTargetSelectionPromptInput",
    "build_rewrite_target_selection_bundle",
    "normalize_generation_style",
    "parse_rewrite_target_selection",
    "render_comment_prompt",
    "render_comment_prompt_with_bad_case_context",
    "render_generate_by_param_prompt",
    "render_generate_by_template_prompt",
    "render_generate_prompt",
    "render_task_skill_prompt",
    "render_template_candidate_ranking_prompt",
    "parse_template_candidate_ranking_output",
]
