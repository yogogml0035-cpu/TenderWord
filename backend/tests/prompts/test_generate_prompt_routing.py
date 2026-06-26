from __future__ import annotations

from backend.agents.generation.content_agents import CONTENT_AGENT_SYSTEM_PROMPT
from backend.agents.generation.revise_agent_graph import REVISE_SYSTEM_PROMPT
from backend.agents.generation.verify_agent_graph import VERIFY_SYSTEM_PROMPT
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
        template_reference_text="模板章节外壳",
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


def test_render_generate_by_param_prompt_preserves_basic_info_shells() -> None:
    rendered = render_generate_by_param_prompt(
        build_prompt_input(generation_style="param")
    )

    assert "基础信息章节镜像铁律" in rendered.system_prompt
    assert "基础信息字段镜像优先" in rendered.system_prompt
    assert "项目元数据字段白名单" in rendered.system_prompt
    assert "不能改写成 `1、设备名称及数量`、`2、项目预算`" in rendered.system_prompt
    assert "基础信息章节不参与技术重组" in rendered.system_prompt
    assert "预算金额、最高限价等只能填入模板里本来就存在的预算/限价类槽位" in rendered.system_prompt


def test_render_generate_by_param_prompt_drops_technical_fields_in_project_overview() -> None:
    rendered = render_generate_by_param_prompt(
        build_prompt_input(generation_style="param")
    )

    assert "技术正文伪装字段黑名单" in rendered.system_prompt
    assert "服务范围、维保范围、功能检测范围、维护保养范围" in rendered.system_prompt
    assert "过滤器清单、更换周期、备品备件" in rendered.system_prompt
    assert "项目概述瘦身" in rendered.system_prompt
    assert "旧服务范围、旧清单、旧过滤器字段必须删除" in rendered.system_prompt
    assert "旧资产/旧清单硬删除" in rendered.system_prompt


def test_generate_prompts_drop_scoring_sections() -> None:
    param_rendered = render_generate_by_param_prompt(
        build_prompt_input(generation_style="param")
    )
    template_rendered = render_generate_by_template_prompt(build_prompt_input())

    assert "采购需求边界与评分污染过滤" in param_rendered.system_prompt
    assert "投标评分细则（100分）" in param_rendered.system_prompt
    assert "必须整段、整表删除" in param_rendered.system_prompt
    assert "评分污染红线" in param_rendered.system_prompt

    assert "采购需求边界与评分污染过滤" in template_rendered.system_prompt
    assert "评分大章不参与定位" in template_rendered.system_prompt
    assert "严禁触发“全量框架锁定+定点注入”" in template_rendered.system_prompt


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

def test_generate_prompt_renders_none_inputs_as_empty_text() -> None:
    data = GeneratePromptInput(
        tender_type="xjcg",
        generation_style="template",
        project_info=None,
        tender_params=None,
        template_reference_text=None,
    )

    rendered = render_generate_prompt(data)

    assert "None" not in rendered.user_prompt


def test_generation_agents_drop_scoring_sections() -> None:
    assert "投标阶段打分内容必须删除" in CONTENT_AGENT_SYSTEM_PROMPT
    assert "投标阶段打分规则" in VERIFY_SYSTEM_PROMPT
    assert "投标评分细则（100分）" in VERIFY_SYSTEM_PROMPT
    assert "必须整段/整表删除" in REVISE_SYSTEM_PROMPT


def test_generate_prompts_generalize_importance_markers_with_delta() -> None:
    """重要性标识规则泛化为 ★/▲/△/Δ/*/#/※/●，并给出 Δ 示例。"""
    template_rendered = render_generate_by_template_prompt(build_prompt_input())
    param_rendered = render_generate_by_param_prompt(build_prompt_input(generation_style="param"))

    for rendered in (template_rendered, param_rendered):
        assert "★/▲/△/Δ/*/#/※/●" in rendered.system_prompt

    # template 的符号白名单显式列出 Δ，并给出 Symbol 字体示例。
    assert "Symbol 字体抽取出的 `Δ`" in template_rendered.system_prompt
    assert "Δ3.1.1" in template_rendered.system_prompt
    # param 的标识保留规则显式包含 Δ。
    assert "Symbol 字体抽取出的 `Δ`" in param_rendered.system_prompt


def test_generate_prompts_exclude_technical_symbols_from_marker_whitelist() -> None:
    """正文技术符号 ≥/±/×/Ω/SpO₂ 不进入重要性标识白名单。"""
    template_rendered = render_generate_by_template_prompt(build_prompt_input())
    param_rendered = render_generate_by_param_prompt(build_prompt_input(generation_style="param"))

    for rendered in (template_rendered, param_rendered):
        assert "≥/±/×/Ω/SpO₂" in rendered.system_prompt


def test_generate_prompts_forbid_ai_preamble_and_filler() -> None:
    """生成 prompt 明确禁止 AI 自述、最终说明、无信息占位句。"""
    template_rendered = render_generate_by_template_prompt(build_prompt_input())
    param_rendered = render_generate_by_param_prompt(build_prompt_input(generation_style="param"))

    for rendered in (template_rendered, param_rendered):
        assert "禁止 AI 自述/包装语" in rendered.system_prompt
        assert "好的，已收到您的指令" in rendered.system_prompt
        assert "禁止无信息占位句" in rendered.system_prompt
        assert "须提供详细技术参数要求" in rendered.system_prompt

    # revise prompt 也禁止 AI 自述与占位句。
    assert "好的，已收到您的指令" in REVISE_SYSTEM_PROMPT
    assert "须提供详细技术参数要求" in REVISE_SYSTEM_PROMPT


def test_generate_prompts_flip_table_placeholder_to_internal_entry() -> None:
    """`[[TABLE:id]]` 被描述为内部写回入口，不再要求模型保留/补回占位符。"""
    template_rendered = render_generate_by_template_prompt(build_prompt_input())
    param_rendered = render_generate_by_param_prompt(build_prompt_input(generation_style="param"))

    for rendered in (template_rendered, param_rendered):
        assert "内部结构化写回入口" in rendered.system_prompt
        assert "不是最终正文的可见内容" in rendered.system_prompt or "不是最终正文可见内容" in rendered.system_prompt
        assert "不要" in rendered.system_prompt and "占位句" in rendered.system_prompt


def test_generate_param_prompt_preserves_field_shell_protection() -> None:
    """param 生成固化字段壳保护区：无新值时保留模板字段壳/占位值，不得删除。"""
    rendered = render_generate_by_param_prompt(build_prompt_input(generation_style="param"))

    assert "绝不能删掉该字段" in rendered.system_prompt
    assert "保留模板里的占位表达、固定表达或字段空壳" in rendered.system_prompt
    assert "设备名称及数量" in rendered.system_prompt
    assert "交付日期" in rendered.system_prompt
    assert "付款方式" in rendered.system_prompt
    assert "交付地点" in rendered.system_prompt


def test_verify_prompt_describes_table_placeholder_as_internal_entry() -> None:
    """审核规则泛化重要性标识并排除技术符号；
    占位符硬契约（附加到 user prompt）把占位符描述为内部写回入口且不要求补回。"""
    from backend.agents.generation.verify_agent_graph import (
        TABLE_PLACEHOLDER_CONTRACT_PROMPT,
    )

    # 审核规则泛化重要性标识并排除技术符号。
    assert "★/▲/△/Δ" in VERIFY_SYSTEM_PROMPT
    assert "SpO₂" in VERIFY_SYSTEM_PROMPT
    # 占位符硬契约描述为内部写回入口，且明确不要求补回。
    assert "内部写回入口" in TABLE_PLACEHOLDER_CONTRACT_PROMPT
    assert "不应作为可见行" in TABLE_PLACEHOLDER_CONTRACT_PROMPT
    assert "不要**为缺失" in TABLE_PLACEHOLDER_CONTRACT_PROMPT


def test_verify_prompt_states_protected_field_non_deletion_contract() -> None:
    """verify prompt 固化受保护字段口径：字段壳来自模板、字段值优先级、不得删除。"""
    # 系统提示词固化业务口径。
    assert "受保护基础字段（受保护字段）不得删除" in VERIFY_SYSTEM_PROMPT
    assert "设备名称及数量" in VERIFY_SYSTEM_PROMPT
    assert "付款方式" in VERIFY_SYSTEM_PROMPT
    assert "交付日期" in VERIFY_SYSTEM_PROMPT
    assert "服务地点" in VERIFY_SYSTEM_PROMPT
    assert "服务期限" in VERIFY_SYSTEM_PROMPT
    assert "字段值优先级为" in VERIFY_SYSTEM_PROMPT
    assert "项目基础信息 > 技术参数项目概述同名字段 > 参考模板同包字段原句" in VERIFY_SYSTEM_PROMPT
    assert "字段存在性优先级高于旧事实清理" in VERIFY_SYSTEM_PROMPT
    assert "审核只能要求补回/恢复受保护字段行，不能要求删除" in VERIFY_SYSTEM_PROMPT
    # 黑名单仍删除的伪装字段保留。
    assert "技术或商务正文伪装字段" in VERIFY_SYSTEM_PROMPT
    assert "评分/评审内容" in VERIFY_SYSTEM_PROMPT


def test_verify_prompt_includes_protected_field_few_shots() -> None:
    """verify prompt few-shot：参考模板有付款方式、新材料无付款方式时输出 []；
    待审核正文缺付款方式时 finding 必须要求补回。"""
    # 参考模板有付款方式、新材料无付款方式、正文已保留 -> []
    assert "待审核正文已正确保留" in VERIFY_SYSTEM_PROMPT
    assert "付款方式：设备安装验收合格后的三个月内付清全款" in VERIFY_SYSTEM_PROMPT
    # 待审核正文缺付款方式 -> finding 要求补回
    assert "缺少受保护基础字段 `付款方式：`" in VERIFY_SYSTEM_PROMPT
    # 审核意见要求删除付款方式时 -> []
    assert "无新材料支撑的旧事实" in VERIFY_SYSTEM_PROMPT


def test_revise_prompt_ignores_delete_protected_field_audit_item() -> None:
    """revise prompt 明确：忽略要求删除受保护字段的 audit item。"""
    assert "受保护基础字段" in REVISE_SYSTEM_PROMPT
    assert "即使 audit JSON 某一项要求删除受保护字段" in REVISE_SYSTEM_PROMPT
    assert "忽略该项 audit item" in REVISE_SYSTEM_PROMPT
    assert "不得删除对应字段行" in REVISE_SYSTEM_PROMPT


def test_verify_user_prompt_states_protected_field_hard_contract() -> None:
    """verify user prompt 的硬契约区写入“受保护字段不得删除/缺值继承模板同包字段原句/删除建议无效”。"""
    from backend.agents.generation.verify_agent_graph import _render_verify_user_prompt

    user_prompt = _render_verify_user_prompt(
        generation_style="template",
        project_info="项目基础信息",
        template_reference_text="模板",
        tender_params="技术参数",
        current_text="待审核正文",
    )
    assert "受保护字段不得删除" in user_prompt
    assert "缺值继承模板同包字段原句" in user_prompt
    assert "删除建议无效" in user_prompt
    assert "受保护字段硬契约" in user_prompt
