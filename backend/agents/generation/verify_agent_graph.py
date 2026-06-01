import asyncio
import json
from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from backend.agents.generation.agent_step_events import (
    emit_agent_step_event,
    get_configurable,
)
from backend.agents.generation.json_utils import (
    build_audit_findings_fallback,
    coerce_audit_findings,
    filter_noop_audit_findings,
    is_contract_placeholder_text,
    parse_audit_findings,
)
from backend.agents.generation.types import (
    AuditFinding,
    GenerationAgentProtocolError,
    GenerationAgentState,
)
from backend.agents.generation.workspace import (
    audit_path,
    context_value,
    get_workspace_backend,
    infer_current_text_path,
    infer_next_audit_round,
    read_backend_text,
    read_generation_context,
    write_backend_text,
)
from backend.util.common_util import StreamCallbacks, stream_llm_completion
from backend.util.log_util.progress_log import progress_log


CHECK_INTERVAL = 3.0
VERIFY_JSON_REPAIR_RETRY_LIMIT = 1
VERIFY_JSON_REPAIR_TEMPERATURE = 0.1
VERIFY_SYSTEM_PROMPT = """
你是招标文件采购需求审核智能体 content_verify_agent。

输出硬契约：
1. 只能输出严格合法的 JSON 数组本身，禁止输出“第 1 轮审核”、解释、Markdown、代码块、前后缀文本或自然语言总结。
2. 无问题时只输出 []。
3. 有问题时数组元素只能是对象，且只能包含两个非空字符串字段：evidence 和 fix_hint。
4. 字段名必须固定为英文 evidence 与 fix_hint，禁止使用“证据”“修复建议”等中文字段名，禁止增加 severity、type、round 等其它字段。
5. evidence 必须指出【待审核正文】中的具体问题、缺漏或多余内容，并引用可定位的正文片段或缺失的技术参数片段。
6. fix_hint 必须给出最小必要修复方式，要求保持其它内容不变。
7. 只输出需要修复的问题；不需要修改、实质一致、仅格式差异或“不视为问题”的内容必须省略，不能作为 finding 输出。
8. 禁止输出 evidence 写“两者一致/无问题”且 fix_hint 写“无需修改”的对象；这种情况等价于 []。

审核真源：
1. 【技术参数（原材料，事实真源）】是实质参数、★/▲符号、包件数量和业务要求的事实真源。
2. 【项目基础信息】是项目名称、数量、交付地点、付款方式等基础信息的事实真源；不要用技术参数中的设备标题覆盖项目基础信息。
3. 【参考内容】只提供章节、编号、表格和语气模具，不是事实真源；不要因为正文没有沿用参考内容的旧设备名、旧参数或旧保修期而报错。

必查规则：
1. 技术参数中的每一条 ★ 或 ▲ 指标都必须在待审核正文中保留同类符号和对应参数内容，不能缺漏、降级为普通条款或换成另一种符号。
2. 待审核正文中不得额外增加技术参数原文没有的 ★ 或 ▲ 指标；参考内容里的 ★/▲ 不能继承到新正文。
3. 如果技术参数明显包含多个包件、标段、采购包或多个独立设备组，待审核正文必须覆盖全部包件；只生成其中一个包件时必须报缺失包件。
4. 技术参数中的实质参数、商务/售后要求和配置清单不得被参考内容旧数据替换；发现正文保留旧模板事实时才报错。
5. 仅编号样式、章节外壳、标点或表格形态跟技术参数原文不同，不算问题；这些可来自参考内容。

Few-shots：
输入要点：技术参数含 `★1.1、波长范围：400-700nm`，待审核正文写成 `1、波长范围：400-700nm`。
输出：
[{"evidence":"技术参数中的 `★1.1、波长范围：400-700nm` 是 ★ 指标，但待审核正文对应条款 `1、波长范围：400-700nm` 缺少 ★ 符号。","fix_hint":"将该正文条款改为带 ★ 的指标条款，保持参数文字不变。"}]

输入要点：技术参数含 `1.1、重量≤10kg` 且没有 ★/▲，待审核正文写成 `★1、重量≤10kg`。
输出：
[{"evidence":"技术参数中的 `1.1、重量≤10kg` 没有 ★ 或 ▲，但待审核正文额外写成 `★1、重量≤10kg`。","fix_hint":"删除该条正文中多余的 ★ 符号，保持参数文字不变。"}]

输入要点：技术参数包含“包件一：显微镜”和“包件二：离心机”，待审核正文只生成“包件一：显微镜”。
输出：
[{"evidence":"技术参数明显包含包件一和包件二，但待审核正文只覆盖包件一，缺少包件二 `离心机` 的采购需求内容。","fix_hint":"补充包件二及其对应技术参数内容，保持包件一内容不变。"}]

输入要点：项目基础信息为“项目名称及数量：细胞电转仪 壹套”，参考内容旧设备名为“细胞自动计数仪”，技术参数为细胞电转仪参数，待审核正文使用“细胞电转仪”且参数完整。
输出：
[]

输入要点：技术参数第 3.1 条和待审核正文第 3.1 条的 ★ 符号、尺寸要求、接口数量和文字内容完全一致。
输出：
[]
""".strip()
VERIFY_JSON_REPAIR_SYSTEM_PROMPT = (
    "你是 JSON 修复助手。只把输入修复为严格合法的 JSON 数组。"
    "数组每项必须包含非空字符串 evidence 和 fix_hint。禁止新增审核问题，禁止解释。"
)


def _emit_verify_agent_step_snapshot(
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
            node="content_verify_agent",
            content=content,
            is_complete=is_complete,
        )
    except Exception as exc:
        progress_log.debug(f"警告: content_verify_agent 过程回调失败: {exc}")


def _build_stream_callbacks(
    config: dict[str, Any] | None,
    *,
    round_index: int,
) -> StreamCallbacks:
    def _on_update(text: str) -> None:
        snapshot = str(text or "")
        if not snapshot:
            return
        _emit_verify_agent_step_snapshot(
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
    raise RuntimeError("verify_agent cannot run inside an active event loop")


def _get_generation_context(config: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(config, dict):
        return {}
    configurable = get_configurable(config)
    if not isinstance(configurable, dict):
        return {}
    context = configurable.get("generation_agent_context")
    return context if isinstance(context, dict) else {}


def _context_value(
    state: GenerationAgentState,
    config: dict[str, Any] | None,
    key: str,
    default: Any = "",
) -> Any:
    return context_value(state, config, key, default)


def _contract_error_needs_retry(error: BaseException) -> bool:
    message = str(error)
    return any(
        marker in message
        for marker in ("缺少 evidence", "必须是对象", "必须是 JSON 数组")
    )

def _render_json_repair_prompt(raw_content: str, error: BaseException) -> str:
    return (
        "请修复下面的审核智能体输出，使其成为严格合法的 JSON 数组。\n"
        "输出规则：\n"
        "1. 只输出 JSON 数组本身，不要解释，不要代码块。\n"
        "2. 每一项必须包含非空字符串字段 evidence 和 fix_hint。\n"
        "3. 不要新增原输出中没有表达的审核问题；只能补齐字段名、数组包裹、引号、逗号、转义和缺失字段。\n"
        "4. 如果某项只有 evidence，请根据 evidence 写最小修复建议；如果某项只有 fix_hint，"
        "请把该建议概括为 evidence，同时保留 fix_hint。\n"
        "5. 如果原输出表达“没有问题”，请输出 []。\n\n"
        f"解析错误：{error}\n\n"
        f"原始输出：\n{raw_content}"
    )

def _request_json_repair(
    raw_content: str,
    *,
    error: BaseException,
    model_provider: str,
) -> str:
    return str(
        _run_async(
            stream_llm_completion(
                model_provider=model_provider,
                system_prompt=VERIFY_JSON_REPAIR_SYSTEM_PROMPT,
                user_prompt=_render_json_repair_prompt(raw_content, error),
                callbacks=StreamCallbacks(),
                extra_params_override={"temperature": VERIFY_JSON_REPAIR_TEMPERATURE},
                check_interval=CHECK_INTERVAL,
            )
        )
    )

def _render_verify_user_prompt(
    *,
    project_info: Any,
    template_reference_text: Any,
    tender_params: Any,
    current_text: str,
) -> str:
    return (
        "请审核【待审核正文】是否违反当前项目的生成契约。\n\n"
        "输出必须是严格 JSON 数组：[] 或 "
        '[{"evidence":"...","fix_hint":"..."}]。'
        "不要输出解释、Markdown、代码块、轮次标题或其它字段。\n\n"
        "审核时请严格区分三类输入：\n"
        "1. 【项目基础信息】提供项目名称、数量、交付、付款等基础事实。\n"
        "2. 【参考内容】只作章节/编号/表格/语气模板，不作事实真源。\n"
        "3. 【技术参数（原材料，事实真源）】提供必须进入正文的实质参数、★/▲指标和包件数量。\n\n"
        "重点检查：\n"
        "- 技术参数中出现的 ★、▲ 指标是否在正文中逐项保留同类符号和对应参数内容。\n"
        "- 正文是否额外增加了技术参数没有的 ★、▲ 指标。\n"
        "- 技术参数明显是多个包件/标段/采购包/独立设备组时，正文是否只生成了其中一个。\n"
        "- 正文是否用参考内容旧事实替换了技术参数或项目基础信息中的新事实。\n"
        "- 不要因为正文编号、章节外壳、表格形态与技术参数原文不同而报错。\n\n"
        "只返回需要修复的问题；不需要修改的问题不要出现在 JSON 数组里。"
        "如果比对结论是“实质一致、无问题、无需修改”，必须输出 []，"
        "不要把一致性说明写成 evidence。\n\n"
        f"【项目基础信息】\n{project_info or ''}\n\n"
        f"【参考内容（只作模板，不作事实真源）】\n{template_reference_text or ''}\n\n"
        f"【技术参数（原材料，事实真源）】\n{tender_params or ''}\n\n"
        f"【待审核正文】\n{current_text}"
    )

def _parse_or_repair_audit_findings(
    raw_content: str,
    *,
    model_provider: str,
) -> list[AuditFinding]:
    try:
        return filter_noop_audit_findings(parse_audit_findings(raw_content))
    except GenerationAgentProtocolError as first_error:
        last_error: BaseException = first_error

    if _contract_error_needs_retry(last_error):
        try:
            repaired_content = _request_json_repair(
                raw_content,
                error=last_error,
                model_provider=model_provider,
            )
            return coerce_audit_findings(repaired_content)
        except Exception as exc:
            last_error = exc

    try:
        return coerce_audit_findings(raw_content)
    except GenerationAgentProtocolError as exc:
        last_error = exc

    for _ in range(VERIFY_JSON_REPAIR_RETRY_LIMIT):
        try:
            repaired_content = _request_json_repair(
                raw_content,
                error=last_error,
                model_provider=model_provider,
            )
            return coerce_audit_findings(repaired_content)
        except Exception as exc:
            last_error = exc

    return build_audit_findings_fallback(last_error)


def _build_placeholder_text_findings(current_text: str) -> list[AuditFinding]:
    return [
        AuditFinding(
            evidence=(
                f"待审核正文只有占位符 `{current_text}`，不是实际采购需求正文。"
            ),
            fix_hint=(
                "返回上一轮真实采购需求正文并按审核意见做最小修复；"
                "不得输出尖括号占位符。"
            ),
        )
    ]


def _verify_text(
    state: GenerationAgentState,
    config: RunnableConfig | None = None,
) -> GenerationAgentState:
    backend = get_workspace_backend(config)
    file_context: dict[str, Any] = read_generation_context(backend) if backend else {}
    merged_state: GenerationAgentState = {**file_context, **state}
    if backend:
        current_text_path = str(
            _context_value(merged_state, config, "current_text_path")
            or infer_current_text_path(backend)
        )
        current_text = read_backend_text(backend, current_text_path)
        round_index = int(
            _context_value(merged_state, config, "revision_round", 0)
            or infer_next_audit_round(backend)
        )
    else:
        round_index = int(_context_value(state, config, "revision_round", 1) or 1)
        current_text = str(
            _context_value(state, config, "current_text")
            or _context_value(state, config, "draft_text")
            or ""
        )
    model_provider = str(_context_value(merged_state, config, "model_provider", "deepseek") or "deepseek")
    if is_contract_placeholder_text(current_text):
        findings = _build_placeholder_text_findings(current_text)
    else:
        user_prompt = _render_verify_user_prompt(
            project_info=_context_value(merged_state, config, "project_info"),
            template_reference_text=_context_value(merged_state, config, "template_reference_text"),
            tender_params=_context_value(merged_state, config, "tender_params"),
            current_text=current_text,
        )
        raw_content = _run_async(
            stream_llm_completion(
                model_provider=model_provider,
                system_prompt=VERIFY_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                callbacks=_build_stream_callbacks(config, round_index=round_index),
                check_interval=CHECK_INTERVAL,
            )
        )
        findings = _parse_or_repair_audit_findings(
            str(raw_content),
            model_provider=model_provider,
        )
    findings_payload = [finding.model_dump() for finding in findings]
    findings_json = json.dumps(findings_payload, ensure_ascii=False)
    if backend:
        write_backend_text(backend, audit_path(round_index), findings_json)
        _emit_verify_agent_step_snapshot(
            config,
            content=findings_json,
            round_index=round_index,
            is_complete=True,
        )
    return {
        "messages": [AIMessage(content=findings_json)],
        "structured_response": findings_payload,
        "findings": findings_payload,
        **({"audit_path": audit_path(round_index)} if backend else {}),
    }


def create_verify_agent_graph():
    builder = StateGraph(GenerationAgentState)
    builder.add_node("verify_text", _verify_text)
    builder.add_edge(START, "verify_text")
    builder.add_edge("verify_text", END)
    return builder.compile()


__all__ = [
    "VERIFY_JSON_REPAIR_SYSTEM_PROMPT",
    "VERIFY_SYSTEM_PROMPT",
    "create_verify_agent_graph",
]
