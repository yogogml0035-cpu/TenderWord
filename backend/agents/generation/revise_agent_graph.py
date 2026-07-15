import asyncio
import json
from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from backend.agents.generation.agent_step_events import emit_agent_step_event
from backend.agents.generation.content_sanitizer import sanitize_generated_content
from backend.agents.generation.protected_field_guard import (
    sanitize_protected_field_findings,
)
from backend.agents.generation.types import AuditFinding, GenerationAgentState
from backend.agents.generation.workspace import (
    audit_path,
    context_value,
    ensure_round_within_protocol,
    get_workspace_backend,
    infer_current_text_path,
    infer_next_revision_round,
    read_backend_text,
    revision_path,
    write_backend_text,
)
from backend.util.common_util import StreamCallbacks, stream_llm_completion
from backend.util.log_util.progress_log import progress_log


REVISE_AGENT_NODE = "content_revise_agent"
CHECK_INTERVAL = 3.0
REVISE_SYSTEM_PROMPT = """
你是招标文件采购需求修订智能体 content_revise_agent。

硬性规则：
1. 只根据 /audits/round-N.json 中的 evidence 与 fix_hint 修复对应位置。
2. 未被 audit 指定的位置必须逐字保留，不得润色、扩写、删减或重排。
3. 输出必须是修订后的完整采购需求正文，不要输出解释、Markdown 代码块或 JSON。
4. 如果 audit 为 []，直接返回“无需修订”，不得输出或重写当前正文。
5. 若 audit 要求删除投标评分细则、评分标准、评审办法或评分表，必须整段/整表删除，不得改写成采购需求、商务条款或占位章节。
5.1. 若 audit 指出某个技术参数字段值被增字、减字、同义改写、简称展开、数字改写、单位/范围换算或跨语义槽位取值，只做精确还原：把 evidence/fix_hint 引用的“现值”替换为“原技术参数逐字值”。不得自行选择第三种表达，不得顺手统一全文术语。模板可把`维保设备`放入`设备名称`列、把`型号`放入`规格型号`列，也可把`数量：1套`无损拆成`数量=1、单位=套`，但字段值字符不能变化。`项目名称`描述整个项目，默认不是设备/维保设备/服务/采购标的名称；恢复设备名称时不得改动正确的项目名称字段。
6. 特殊符号保真（通用，覆盖一切特殊符号）：技术参数里出现的所有特殊符号与非常规字符都必须如实保留——既包括重要性标识（紧邻编号前后标注重要性的非数字非字母标记，如 ★/▲/△/Δ/☆/◆/◇/*/#/※/● 等，例如 Symbol 字体抽取出的 Δ），也包括计量/科学符号（如 ≥/≤/±/×/÷/√/℃/℉/°/Ω/μ/π/‰/% 及上下标 ²/³/₂ 等）和其它全角/单位/货币/箭头符号。当 audit 指出条款丢失或写错标识时，恢复为规范字形：三角类→▲，星/`*`/`※` 类→★；不要为保留源字形而把 ▲ 改回 △/Δ，或把 ★ 改回 */※。计量/科学符号必须按技术参数原样恢复，不得用文字近义词或 ASCII 近似（如 >=、“大于等于”、“度”、“正负”）替代；`ΔT`、`5*6`、型号中的 `*` 保持原样。
7. 严禁输出“好的，已收到您的指令”“以下是重构后的招标文件”“以上为最终内容”等 AI 自述、包装语或内部自检；严禁输出“须提供详细技术参数要求/须提供详细配置清单”这类无信息占位句；严禁用代码块包裹整段正文。
8. `[[TABLE:id]]` 是内部结构化写回入口，是真实表格还原进 Word 的唯一锚点：修订时**必须原样保留**当前正文中已有的 `[[TABLE:id]]` 占位符行（`id` 不得改写），不得删除它、不得改写成手绘/纯文本表格，也不要为缺失的表补占位句。占位符本身不是最终 Word 可见内容，写回层会按 id 把它替换成真实表格或静默丢弃。
9. 受保护基础字段（设备名称及数量/交付日期/交付地点/付款方式/服务地点/服务期限/预算/最高限价/包号/标段号）不得删除：即使 audit JSON 某一项要求删除受保护字段，也必须忽略该项 audit item，不得删除对应字段行。若 audit 指出字段值错误，只能按 evidence/fix_hint 给出的同一语义槽位原值修复；不得自行从项目名称、相邻字段或模板选择另一值。audit 未指出字段值错误且当前材料缺值时，保留参考模板同包字段行原句或占位表达，不得清空或删除字段。
10. 若 audit 指出某个应锚点直通的 `[[TABLE:id]]` 表被重复转写成普通文本、编号列表、手绘表格或纯文本表格，修复动作只有一个：删除这些重复投影行，保留独占一行的 `[[TABLE:id]]`、必要章节标题和该表前后的非表格正文；不得把投影行改写成另一种表格，也不得补“须提供详细...”占位句。
10.1. 若 audit 明确指出 template 生成风格下某个一列表格/文本容器表已经展开成正文但仍保留同一 `[[TABLE:id]]`，修复动作是删除这个多余锚点，保留已经展开的正文；不得反过来删除正文并恢复锚点。
11. 若 audit 指出多个 `[[TABLE:id]]` 被集中挪到文末，或锚点之间/锚点之后缺失附件标题、报价说明、注释、签字盖章、日期等非表格正文，必须按 fix_hint 恢复这些非表格正文并把对应锚点放回原位置。只恢复 audit 指定的缺失正文；不要重画结构化表，不要恢复评分表，不要改动 audit 未指定的其它正文。
12. 若 audit 指出某个具体包的项目概述缺少受保护基础字段（如第1包缺 `付款方式：`），只在 audit 指定的那个包内按 fix_hint 补回对应字段行，保持字段顺序和其它包内容不变；不能把某一包已有字段当作全文字段，也不能改写未被点名的包。
13. 若 audit 指出包标题前后存在裸采购人/单位/医院/学校/公司名称行，或包标题含 `项目技术参数/技术参数/参数要求` 等来源说明后缀，可以删除该裸机构行并净化包标题；这类局部删除属于 audit 指定修复，不受“未指定位置逐字保留”限制。但 `交付地点/服务地点` 字段值里的机构名称必须保留。
14. 只有审核 JSON 严格等于空数组 `[]` 时才能输出“无需修订”；只要审核 JSON 含有任意 evidence/fix_hint，必须输出修订后的完整正文，不能用“无需修订”代替。
15. 若 audit 指出技术参数连续条款缺少可见编号，只对 audit 指定的连续参数块补连续编号；参数文字、数值、单位、★/▲/△/Δ 等标识和未点名段落必须保持不变。无编号源行为 `▲产品形态：...` 时，补号格式为 `2、▲产品形态：...` 或 fix_hint 指定样式，不得删除 ▲，不得移动到其它条款。

事实差异修订示例：当前项目名称是`医用核磁共振系统维保`，设备清单现值是`医用核磁共振系统`；audit 明确指出原技术参数的维保设备值为`磁共振系统`。只把设备清单现值替换为`磁共振系统`，项目名称、品牌、型号、数量、单位和其它正文全部保持不变。
""".strip()


def _emit_revise_agent_step_snapshot(
    config: dict[str, Any] | None,
    *,
    content: str,
    round_index: int,
    is_complete: bool,
) -> None:
    try:
        emit_agent_step_event(
            config,
            round_index=round_index,
            node=REVISE_AGENT_NODE,
            content=content,
            is_complete=is_complete,
        )
    except Exception as exc:
        progress_log.debug(f"警告: content_revise_agent 过程回调失败: {exc}")


def _build_stream_callbacks(
    config: dict[str, Any] | None,
    *,
    round_index: int,
) -> StreamCallbacks:
    def _on_update(text: str) -> None:
        snapshot = str(text or "")
        if not snapshot:
            return
        _emit_revise_agent_step_snapshot(
            config,
            content=snapshot,
            round_index=round_index,
            is_complete=False,
        )

    return StreamCallbacks(on_update=_on_update)


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    raise RuntimeError("revise_agent cannot run inside an active event loop")


def _render_revise_user_prompt(
    *,
    current_text: str,
    audit_json: str,
) -> str:
    return (
        "请按审核 JSON 对【当前正文】做最小必要修复。\n"
        "除 evidence/fix_hint 明确指定的位置外，其它内容必须逐字保留。\n\n"
        "事实差异修订规则：如果审核 JSON 同时给出原技术参数值和当前正文值，逐字用原值替换当前值。"
        "禁止同义改写、简称展开、数字/中文数字互换、单位或范围换算；禁止用项目名称补全设备名称。"
        "例如设备清单的 `医用核磁共振系统` 被指出原值是 `磁共振系统` 时，只把该设备单元格恢复为 `磁共振系统`，不要改动项目名称或其它正文。\n\n"
        "结构化表修订规则：如果审核 JSON 指出应锚点直通的 `[[TABLE:id]]` 前源表被转写成普通文本、编号列表或手绘/纯文本表格，"
        "只删除这些重复投影行，保留必要章节标题、表前表后非表格正文和独占一行的 `[[TABLE:id]]`；不要把投影行改成另一种表格或占位句。"
        "如果审核 JSON 指出 template 文本容器表已经展开成正文但仍保留同一 `[[TABLE:id]]`，只删除这个多余锚点，保留已展开正文。\n"
        "如果审核 JSON 指出多个 `[[TABLE:id]]` 被集中挪到文末，或锚点之间/之后的附件标题、报价说明、注释、签字盖章、日期等非表格正文缺失，"
        "按 fix_hint 恢复这些非表格正文并把锚点放回原位置；不要重画结构化表，不要恢复评分表，不要改动其它正文。\n\n"
        "基础字段与包头修订规则：如果审核 JSON 指出某一包缺少 `付款方式：` 等基础字段，只在该包项目概述内补回该字段行；"
        "字段位置放在该包项目概述中同类基础字段之后，编号按该包项目概述顺延；没有新值时按 fix_hint 沿用模板占位或固定表达。"
        "如果审核 JSON 指出每包开头有裸采购人/单位/医院名称或包标题后缀，只删除这些裸行/后缀，保留字段值和后续正文。\n\n"
        "编号修订规则：如果审核 JSON 指出连续技术参数行缺少可见编号，只给这些行按顺序补号，例如 `成像模式：B模式`、`▲产品形态：一体便携式` 改为 `1、成像模式：B模式`、`2、▲产品形态：一体便携式`；不要改写参数文字、单位、数值或未被点名的段落。\n\n"
        "重要：只有【审核 JSON】严格等于 [] 时才允许返回“无需修订”；否则必须返回修订后的完整正文。\n\n"
        f"【审核 JSON】\n{audit_json}\n\n"
        f"【当前正文】\n{current_text}"
    )


def _revise_text(
    state: GenerationAgentState,
    config: RunnableConfig | None = None,
) -> GenerationAgentState:
    backend = get_workspace_backend(config)
    if backend:
        round_index = int(
            context_value(state, config, "revision_round", 0)
            or infer_next_revision_round(backend)
        )
        # 协议轮次已用尽时（显式 revision_round=4 或已存在 3 轮修订），
        # 不再写越界修订产物，直接抛受控错误，交由主流程兜底交付。
        ensure_round_within_protocol(round_index, artifact_type="修订")
        current_text_path = str(
            context_value(state, config, "current_text_path")
            or infer_current_text_path(backend)
        )
        current_text = read_backend_text(backend, current_text_path)
        raw_audit = read_backend_text(backend, audit_path(round_index))
    else:
        round_index = int(context_value(state, config, "revision_round", 1) or 1)
        current_text = str(context_value(state, config, "current_text", "") or "")
        raw_audit = json.dumps(
            context_value(state, config, "audit_findings", []) or [],
            ensure_ascii=False,
        )

    try:
        audit_items = json.loads(raw_audit)
    except json.JSONDecodeError:
        audit_items = [{"evidence": "审核 JSON 格式异常", "fix_hint": "保持当前正文不变"}]

    # 受保护基础字段二次护栏：防止历史 audit 文件或异常 runner 绕过 verify guard。
    # revise 阶段只做删除过滤（backfill_missing=False），不引入新 finding，
    # 避免“空审核跳过修订”契约被打破；字段补回由 verify 阶段负责。
    if isinstance(audit_items, list):
        sanitized_findings = sanitize_protected_field_findings(
            findings=[
                AuditFinding(**item)
                for item in audit_items
                if isinstance(item, dict)
                and item.get("evidence")
                and item.get("fix_hint")
            ],
            tender_type=context_value(state, config, "tender_type", "xjcg"),
            current_text=current_text,
            template_reference_text=context_value(
                state, config, "template_reference_text"
            ),
            backfill_missing=False,
        )
        raw_audit = json.dumps(
            [finding.model_dump(mode="json") for finding in sanitized_findings],
            ensure_ascii=False,
        )
        audit_items = sanitized_findings

    if audit_items == []:
        _emit_revise_agent_step_snapshot(
            config,
            content="无需修订",
            round_index=round_index,
            is_complete=True,
        )
        return {
            "messages": [AIMessage(content="无需修订")],
            "structured_response": {
                "status": "no_revision",
                "message": "无需修订",
            },
            "no_revision": True,
        }

    revised_text = str(
        _run_async(
            stream_llm_completion(
                model_provider=str(context_value(state, config, "model_provider", "deepseek") or "deepseek"),
                system_prompt=REVISE_SYSTEM_PROMPT,
                user_prompt=_render_revise_user_prompt(
                    current_text=current_text,
                    audit_json=raw_audit,
                ),
                callbacks=_build_stream_callbacks(config, round_index=round_index),
                check_interval=CHECK_INTERVAL,
            )
        )
    )
    # 写入 revision 前过统一 sanitizer：删除 AI 自述/包装语、最终说明、Markdown 外壳、
    # 无信息占位句；保留 [[TABLE:id]] 占位符、技术符号和重要性标识。
    revised_text = sanitize_generated_content(revised_text)

    if backend:
        write_backend_text(backend, revision_path(round_index), revised_text)
        _emit_revise_agent_step_snapshot(
            config,
            content=revised_text,
            round_index=round_index,
            is_complete=True,
        )

    return {
        "messages": [AIMessage(content=f"已修订正文并写入 {revision_path(round_index)}")],
        "structured_response": {"revision_path": revision_path(round_index)},
        "revision_path": revision_path(round_index),
        **({} if backend else {"polished_text": revised_text}),
    }


def create_revise_agent_graph():
    builder = StateGraph(GenerationAgentState)
    builder.add_node("revise_text", _revise_text)
    builder.add_edge(START, "revise_text")
    builder.add_edge("revise_text", END)
    return builder.compile()


__all__ = ["REVISE_SYSTEM_PROMPT", "create_revise_agent_graph"]
