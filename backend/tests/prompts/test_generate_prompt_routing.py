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

def test_render_generate_by_param_prompt_limits_reference_tables_and_business_shells() -> None:
    rendered = render_generate_by_param_prompt(
        build_prompt_input(generation_style="param")
    )

    assert "参考内容】只允许提供：包/标段标题外壳" in rendered.system_prompt
    assert "设备/服务清单不自动迁移到项目概述" in rendered.system_prompt
    assert "禁止旧表壳劫持" in rendered.system_prompt
    assert "绝不能输出品牌或数量列" in rendered.system_prompt
    assert "空白单元格续行合并" in rendered.system_prompt
    assert "不得重复生成商务章节" in rendered.system_prompt

def test_render_generate_by_template_prompt_preserves_colon_attached_lists() -> None:
    rendered = render_generate_by_template_prompt(build_prompt_input())

    assert "硬换行与冒号挂载列表协议" in rendered.system_prompt
    assert "原材料里的物理换行和显式编号列表是硬边界" in rendered.system_prompt
    assert "带显式编号的子项永远不是同一属性短语枚举" in rendered.system_prompt
    assert "1.1、CRO服务" in rendered.system_prompt

def test_render_generate_by_template_prompt_blocks_reference_symbol_inheritance() -> None:
    rendered = render_generate_by_template_prompt(build_prompt_input())

    assert "参考符号零继承" in rendered.system_prompt
    assert "换料行必须重新判符号" in rendered.system_prompt
    assert (
        "参考内容为 `★1、用途：旧内容`，原材料为 `1.1用途：新内容`"
        in rendered.system_prompt
    )
    assert "条款行首符号不是正文语义" in rendered.system_prompt
