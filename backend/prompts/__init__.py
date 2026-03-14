"""Unified prompt builders, contracts, and routing literals."""

from backend.prompts.comment_prompt import (
    COMMENT_PROMPT_REGISTRY,
    COMMENT_SYSTEM_PROMPT,
    COMMENT_USER_PROMPT,
    render_comment_prompt,
)
from backend.prompts.generate_prompt import (
    GENERATE_PROMPT_REGISTRY,
    POLISH_SYSTEM_PROMPT,
    POLISH_USER_PROMPT,
    render_generate_prompt,
)
from backend.prompts.rewrite_prompt import (
    REWRITE_SYSTEM_PROMPT,
    REWRITE_USER_PROMPT,
    render_rewrite_prompt,
)
from backend.prompts.routing_prompt import (
    JUDGE_TARGET_SYSTEM_PROMPT,
    REPLY_ROUTE_LITERAL,
    REWRITE_ROUTE_LITERAL,
    ROUTE_OR_REPLY_SYSTEM_PROMPT,
    build_rewrite_target_selection_bundle,
    parse_rewrite_target_selection,
    render_route_or_reply_prompt,
)
from backend.prompts.types import (
    CommentPromptInput,
    GeneratePromptInput,
    RenderedPrompt,
    RewriteAssistantCandidate,
    RewriteHistoryMessage,
    RewritePromptInput,
    RewriteStateSnapshot,
    RewriteTargetSelectionBundle,
    RewriteTargetSelectionPromptInput,
    RouteHistoryMessage,
    RouteOrReplyPromptInput,
)

__all__ = [
    "COMMENT_PROMPT_REGISTRY",
    "COMMENT_SYSTEM_PROMPT",
    "COMMENT_USER_PROMPT",
    "CommentPromptInput",
    "GENERATE_PROMPT_REGISTRY",
    "GeneratePromptInput",
    "JUDGE_TARGET_SYSTEM_PROMPT",
    "POLISH_SYSTEM_PROMPT",
    "POLISH_USER_PROMPT",
    "REPLY_ROUTE_LITERAL",
    "REWRITE_ROUTE_LITERAL",
    "REWRITE_SYSTEM_PROMPT",
    "REWRITE_USER_PROMPT",
    "ROUTE_OR_REPLY_SYSTEM_PROMPT",
    "RenderedPrompt",
    "RewriteAssistantCandidate",
    "RewriteHistoryMessage",
    "RewritePromptInput",
    "RewriteStateSnapshot",
    "RewriteTargetSelectionBundle",
    "RewriteTargetSelectionPromptInput",
    "RouteHistoryMessage",
    "RouteOrReplyPromptInput",
    "build_rewrite_target_selection_bundle",
    "parse_rewrite_target_selection",
    "render_comment_prompt",
    "render_generate_prompt",
    "render_rewrite_prompt",
    "render_route_or_reply_prompt",
]
