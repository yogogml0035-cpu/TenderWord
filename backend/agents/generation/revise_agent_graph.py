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
6. 特殊符号保真（通用，覆盖一切特殊符号）：技术参数里出现的所有特殊符号与非常规字符都必须按技术参数原样保留——既包括重要性标识（紧邻编号前后标注重要性的非数字非字母标记，如 ★/▲/△/Δ/☆/◆/◇/*/#/※/● 等，例如 Symbol 字体抽取出的 Δ），也包括计量/科学符号（如 ≥/≤/±/×/÷/√/℃/℉/°/Ω/μ/π/‰/% 及上下标 ²/³/₂ 等）和其它全角/单位/货币/箭头符号。当 audit 的 evidence/fix_hint 指出某条款丢失或写错了某个特殊符号时，必须按 fix_hint 把它恢复成技术参数原文的符号，不得用文字近义词或 ASCII 近似（如 >=、“大于等于”、“度”、“正负”）替代；技术符号按参数文本原样保留，不当作重要性标识、不据此增删 ★/▲。
7. 严禁输出“好的，已收到您的指令”“以下是重构后的招标文件”“以上为最终内容”等 AI 自述、包装语或内部自检；严禁输出“须提供详细技术参数要求/须提供详细配置清单”这类无信息占位句；严禁用代码块包裹整段正文。
8. `[[TABLE:id]]` 是内部结构化写回入口，是真实表格还原进 Word 的唯一锚点：修订时**必须原样保留**当前正文中已有的 `[[TABLE:id]]` 占位符行（`id` 不得改写），不得删除它、不得改写成手绘/纯文本表格，也不要为缺失的表补占位句。占位符本身不是最终 Word 可见内容，写回层会按 id 把它替换成真实表格或静默丢弃。
9. 受保护基础字段（设备名称及数量/交付日期/交付地点/付款方式/服务地点/服务期限/预算/最高限价/包号/标段号）不得删除：即使 audit JSON 某一项要求删除受保护字段，也必须忽略该项 audit item，不得删除对应字段行。字段值优先级为 项目基础信息 > 技术参数项目概述同名字段 > 参考模板同包字段原句；缺值时保留参考模板同包字段行原句或占位表达，不得清空或删除字段。
10. 若 audit 指出某个 `[[TABLE:id]]` 锚点表被重复转写成普通文本、编号列表、手绘表格或纯文本表格，修复动作只有一个：删除这些重复投影行，保留独占一行的 `[[TABLE:id]]` 和必要章节标题；不得把投影行改写成另一种表格，也不得补“须提供详细...”占位句。
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
        "结构化表修订规则：如果审核 JSON 指出 `[[TABLE:id]]` 前的源表被转写成普通文本、编号列表或手绘/纯文本表格，"
        "只删除这些重复投影行，保留必要章节标题和独占一行的 `[[TABLE:id]]`；不要把投影行改成另一种表格或占位句。\n\n"
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
