from __future__ import annotations

from backend.prompts.types import RenderedPrompt, TaskSkillPromptInput


def render_task_skill_prompt(data: TaskSkillPromptInput) -> RenderedPrompt:
    instruction = str(data.instruction or "").strip()
    if not instruction:
        raise ValueError("skill instruction 不能为空")

    sections: list[str] = [f"【skill_id】\n{data.skill_id}"]
    for section in data.sections:
        content = str(section.content or "").strip() or "（无）"
        sections.append(f"【{section.title}】\n{content}")

    return RenderedPrompt(
        system_prompt=instruction,
        user_prompt="\n\n".join(sections).strip(),
    )
