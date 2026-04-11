from __future__ import annotations

from backend.prompts.generate_by_param_prompt import (
    GENERATE_BY_PARAM_PROMPT_REGISTRY,
    render_generate_by_param_prompt,
)
from backend.prompts.generate_by_template_prompt import (
    GENERATE_BY_TEMPLATE_PROMPT_REGISTRY,
    POLISH_SYSTEM_PROMPT,
    POLISH_USER_PROMPT,
    render_generate_by_template_prompt,
)
from backend.prompts.types import GeneratePromptInput, RenderedPrompt

DEFAULT_GENERATION_STYLE = "template"
PARAM_GENERATION_STYLE = "param"

# Backward compatibility for existing imports that expect template-mode symbols.
GENERATE_PROMPT_REGISTRY = GENERATE_BY_TEMPLATE_PROMPT_REGISTRY


def normalize_generation_style(style: str | None) -> str:
    normalized = str(style or "").strip().lower()
    if normalized == PARAM_GENERATION_STYLE:
        return PARAM_GENERATION_STYLE
    return DEFAULT_GENERATION_STYLE


def render_generate_prompt(data: GeneratePromptInput) -> RenderedPrompt:
    generation_style = normalize_generation_style(data.generation_style)
    if generation_style == PARAM_GENERATION_STYLE:
        return render_generate_by_param_prompt(data)
    return render_generate_by_template_prompt(data)


__all__ = [
    "DEFAULT_GENERATION_STYLE",
    "GENERATE_BY_PARAM_PROMPT_REGISTRY",
    "GENERATE_BY_TEMPLATE_PROMPT_REGISTRY",
    "GENERATE_PROMPT_REGISTRY",
    "PARAM_GENERATION_STYLE",
    "POLISH_SYSTEM_PROMPT",
    "POLISH_USER_PROMPT",
    "normalize_generation_style",
    "render_generate_prompt",
]
