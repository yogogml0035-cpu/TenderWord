from __future__ import annotations

from backend.prompts.generate_by_param_prompt import render_generate_by_param_prompt
from backend.prompts.generate_by_template_prompt import render_generate_by_template_prompt
from backend.prompts.generate_prompt import render_generate_prompt
from backend.prompts.types import GeneratePromptInput


def build_prompt_input(*, generation_style: str = "template") -> GeneratePromptInput:
    return GeneratePromptInput(
        tender_type="xjcg",
        generation_style=generation_style,
        project_info="项目基础信息",
        tender_params="技术参数正文",
        origin_tender_params="模板章节外壳",
    )


def test_render_generate_prompt_defaults_to_template_routing() -> None:
    data = build_prompt_input()

    assert render_generate_prompt(data) == render_generate_by_template_prompt(data)


def test_render_generate_prompt_routes_param_mode() -> None:
    data = build_prompt_input(generation_style="param")
    rendered = render_generate_prompt(data)

    assert rendered == render_generate_by_param_prompt(data)
    assert "参数优先模式" in rendered.system_prompt
    assert "按参数生成" in rendered.user_prompt


def test_render_generate_by_param_prompt_prunes_unsourced_intro_and_reindexes() -> None:
    rendered = render_generate_by_param_prompt(
        build_prompt_input(generation_style="param")
    )

    assert "引导段硬删除原则" in rendered.system_prompt
    assert "若新材料没有提供对应事实，必须彻底删除" in rendered.system_prompt
    assert "保层级，不照抄容器号" in rendered.system_prompt
    assert "最终必须改写为当前章的第 1 个有效条目" in rendered.system_prompt
