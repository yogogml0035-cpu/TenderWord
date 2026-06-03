from __future__ import annotations

import asyncio
import json
import pathlib
import shutil
import time
import uuid
from typing import Any, Dict, List

from backend.agents.generation.json_utils import coerce_audit_findings
from backend.agents.generation.types import AuditFinding
from backend.config.tender_config import (
    CONTENT_UPDATE_MODE_PROTECTED_FIELDS,
    get_content_update_mode,
    get_protected_field_profile,
)
from backend.helper.word_helper.protected_fields import match_protected_field_line
from backend.models import AgentStepEventData
from backend.prompts.skill_prompt import render_task_skill_prompt
from backend.prompts.rewrite_target_selection_prompt import (
    build_rewrite_target_selection_bundle,
    parse_rewrite_target_selection,
)
from backend.prompts.types import (
    RewriteHistoryMessage as PromptRewriteHistoryMessage,
    RewriteStateSnapshot,
    RewriteTargetSelectionPromptInput,
    TaskSkillPromptInput,
    TaskSkillPromptSection,
)
from backend.skills import get_skill_guide
from backend.services.conversation_service import RewriteMessage, get_conversation_service
from backend.states import TaskSkillGraphState
from backend.util.common_util import StreamCallbacks, stream_llm_completion
from backend.util.log_util.progress_log import progress_log
from backend.util.log_util.skill_audit_log import (
    REWRITE_STAGE_SKILL_PROMPT_RENDER,
    REWRITE_STAGE_TARGET_SELECTION,
    REWRITE_STAGE_TEXT,
    resolve_task_audit_log_path,
    write_task_audit_stage,
)


REWRITE_RUNTIME_SECTION_HEADING = "## 后台 rewrite 任务正文改写指令"
REWRITE_AGENT_NODE = "rewrite_agent"
REWRITE_GENERATE_AGENT_NODE = "rewrite_generate_agent"
REWRITE_VERIFY_AGENT_NODE = "rewrite_verify_agent"
REWRITE_REVISE_AGENT_NODE = "rewrite_revise_agent"
REWRITE_MAX_AUDIT_ROUNDS = 2

REWRITE_VERIFY_SYSTEM_PROMPT = """
你是招标文件重写审核子智能体 rewrite_verify_agent。

输出硬契约：
1. 只能输出严格合法的 JSON 数组本身，不要输出解释、Markdown、代码块或自然语言总结。
2. 无问题时只输出 []。
3. 有问题时数组元素只能包含两个非空字符串字段：evidence 和 fix_hint。
4. evidence 必须指出【重写后正文】相对【当前文档内容】、【用户修改指令】或【受保护字段要求】的具体问题。
5. fix_hint 必须给出最小必要修复方式，要求保持其它内容不变。

审核重点：
1. 重写后正文必须覆盖当前文档内容的完整范围；除非用户明确要求删除/仅保留，不得省略未提及章节、包件或字段。
2. 用户指令命中的局部范围应被修改，未命中的内容应尽量原样保留。
3. 受保护字段要求中列出的字段行必须保留字段名、冒号和相对顺序。
4. 不要因为措辞轻微优化、编号样式或标点差异报错；只输出需要修复的问题。
""".strip()

REWRITE_REVISE_SYSTEM_PROMPT = """
你是招标文件重写修订子智能体 rewrite_revise_agent。

硬性规则：
1. 只根据【审核 JSON】中的 evidence 与 fix_hint 修复对应位置。
2. 未被审核 JSON 指定的位置必须尽量逐字保留，不得继续润色、扩写、删减或重排。
3. 输出必须是修订后的完整正文，不要输出解释、Markdown、代码块或 JSON。
""".strip()


def _get_model_provider(config: Dict[str, Any] | None) -> str:
    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    model_provider = configurable.get("model_provider", "deepseek")
    return str(model_provider or "deepseek")


def _get_configurable(config: Dict[str, Any] | None) -> Dict[str, Any]:
    return config.get("configurable", {}) if isinstance(config, dict) else {}


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def _extract_rewrite_runtime_instruction(instruction: str) -> str:
    text = str(instruction or "").strip()
    if REWRITE_RUNTIME_SECTION_HEADING not in text:
        return text
    return text.split(REWRITE_RUNTIME_SECTION_HEADING, 1)[1].strip()


def _protected_markers_for_state(state: TaskSkillGraphState) -> tuple[str, ...]:
    tender_type = str(state.get("tender_type") or "xjcg").strip() or "xjcg"
    try:
        if get_content_update_mode(tender_type) != CONTENT_UPDATE_MODE_PROTECTED_FIELDS:
            return ()
        return get_protected_field_profile(tender_type).ordered_markers
    except ValueError:
        return ()


def _format_protected_requirement(markers: tuple[str, ...]) -> str:
    if not markers:
        return "无"
    return (
        "最终正文必须保留以下受保护字段行，字段名、冒号和相对顺序不得丢失；"
        "字段行可以保留原编号前缀："
        + " -> ".join(markers)
    )


def _marker_indices(text: str, markers: tuple[str, ...]) -> dict[str, int]:
    lines = str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    indices: dict[str, int] = {}
    for marker in markers:
        for index, line in enumerate(lines):
            if match_protected_field_line(line, marker):
                indices[marker] = index
                break
    return indices


def _audit_protected_fields(
    *,
    base_text: str,
    candidate_text: str,
    markers: tuple[str, ...],
) -> list[AuditFinding]:
    if not markers:
        return []

    findings: list[AuditFinding] = []
    base_indices = _marker_indices(base_text, markers)
    candidate_indices = _marker_indices(candidate_text, markers)
    for marker in markers:
        if marker in candidate_indices:
            continue
        base_hint = "当前文档内容中也缺少该字段，请按该招标类型补回字段行。"
        if marker in base_indices:
            base_hint = "从当前文档内容中复制该字段行并放回最终正文，保持其它内容不变。"
        findings.append(
            AuditFinding(
                evidence=f"重写后正文缺少受保护字段行 `{marker}`。",
                fix_hint=base_hint,
            )
        )

    ordered_indices = [
        candidate_indices[marker]
        for marker in markers
        if marker in candidate_indices
    ]
    if ordered_indices != sorted(ordered_indices):
        findings.append(
            AuditFinding(
                evidence=(
                    "重写后正文中受保护字段顺序错误；期望顺序为 "
                    + " -> ".join(markers)
                    + "。"
                ),
                fix_hint="调整受保护字段行顺序，保持字段值和其它正文不变。",
            )
        )

    return findings


def _findings_to_payload(findings: list[AuditFinding]) -> list[dict[str, str]]:
    return [finding.model_dump(mode="json") for finding in findings]


def _text_chars(value: str) -> int:
    return len(str(value or "").strip())


class _RewriteAgentStepTracker:
    def __init__(self, config: Dict[str, Any] | None) -> None:
        configurable = _get_configurable(config)
        self._task_id = str(configurable.get("task_id") or "").strip()
        self._task_kind = str(configurable.get("task_kind") or "rewrite").strip() or "rewrite"
        self._callback = configurable.get("agent_step_callback")
        self._rounds: list[dict[str, Any]] = []

    def emit(
        self,
        *,
        node: str,
        phase: str,
        label: str,
        summary: str,
        round_index: int,
        content: str | None,
        findings: list[AuditFinding] | None = None,
        is_complete: bool = True,
        final_result: dict[str, Any] | None = None,
    ) -> None:
        if not self._task_id or not callable(self._callback):
            return

        serialized_findings = _findings_to_payload(findings or [])
        if phase in {"draft", "audit", "revision"}:
            self._upsert_round(
                {
                    "round": round_index,
                    "phase": phase,
                    "label": label,
                    "summary": summary,
                    "issue_count": len(serialized_findings),
                    "fix_count": len(serialized_findings) if phase == "revision" else 0,
                    "content": content,
                    "findings": serialized_findings,
                }
            )

        content_agent: dict[str, Any] = {
            "phase": phase,
            "summary": summary,
            "rounds": list(self._rounds),
            "highlights": serialized_findings,
        }
        if final_result is not None:
            content_agent["final_result"] = final_result

        self._callback(
            AgentStepEventData(
                task_id=self._task_id,
                task_kind=self._task_kind,
                step_type=phase if phase != "final" else "final",
                round=round_index,
                node=node,
                content=content,
                findings=serialized_findings,
                content_agent=content_agent,
                is_complete=is_complete,
            )
        )

    def _upsert_round(self, round_data: dict[str, Any]) -> None:
        round_index = int(round_data["round"])
        phase = str(round_data["phase"])
        self._rounds = [
            item
            for item in self._rounds
            if not (int(item.get("round") or 0) == round_index and item.get("phase") == phase)
        ]
        self._rounds.append(round_data)
        phase_order = {"draft": 0, "audit": 1, "revision": 2}
        self._rounds.sort(
            key=lambda item: (
                int(item.get("round") or 0),
                phase_order.get(str(item.get("phase") or ""), 99),
            )
        )


def _build_prompt_history_messages(
    rewrite_messages: List[RewriteMessage],
) -> List[PromptRewriteHistoryMessage]:
    prompt_messages: List[PromptRewriteHistoryMessage] = []
    for message in rewrite_messages:
        prompt_messages.append(
            PromptRewriteHistoryMessage(
                role=message.role,
                content=message.content,
                rewrite_state=RewriteStateSnapshot.from_mapping(message.rewrite_state),
                created_at=message.created_at,
            )
        )
    return prompt_messages


def _list_assistant_messages(rewrite_messages: List[RewriteMessage]) -> List[RewriteMessage]:
    return [
        message
        for message in rewrite_messages
        if message.role == "assistant" and isinstance(message.rewrite_state, dict)
    ]


def _get_rewrite_log_path(config: Dict[str, Any] | None) -> str:
    return resolve_task_audit_log_path(config)


def _select_rewrite_target_index(user_prompt: str, rewrite_messages: List[RewriteMessage], config) -> int:
    rendered_bundle = build_rewrite_target_selection_bundle(
        RewriteTargetSelectionPromptInput(
            messages=_build_prompt_history_messages(rewrite_messages),
            user_prompt=user_prompt,
        )
    )
    if not rendered_bundle.assistant_candidates:
        raise ValueError("当前会话没有可用的 rewrite 版本候选")

    model_provider = _get_model_provider(config)
    rewrite_log_path = _get_rewrite_log_path(config)

    def _capture_request_messages(messages: list[dict[str, Any]]) -> None:
        if not rewrite_log_path:
            return
        write_task_audit_stage(
            rewrite_log_path,
            REWRITE_STAGE_TARGET_SELECTION,
            messages,
        )

    callbacks = StreamCallbacks(on_request_messages=_capture_request_messages)

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(
        stream_llm_completion(
            model_provider=model_provider,
            system_prompt=rendered_bundle.rendered_prompt.system_prompt,
            user_prompt=rendered_bundle.rendered_prompt.user_prompt,
            callbacks=callbacks,
            extra_params_override={"temperature": 0.0},
            check_interval=3.0,
        )
    )
    selected_index = parse_rewrite_target_selection(
        result, len(rendered_bundle.assistant_candidates)
    )
    progress_log.info(
        "[resolve_rewrite_target] 已选择 assistant candidate_index=%s",
        selected_index,
    )
    return selected_index


def _build_rewrite_output_path(source_path: pathlib.Path) -> pathlib.Path:
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    suffix = source_path.suffix or ".docx"
    candidate = source_path.with_name(f"{source_path.stem}_rewrite_{timestamp}{suffix}")
    if candidate.exists():
        candidate = source_path.with_name(
            f"{source_path.stem}_rewrite_{timestamp}_{uuid.uuid4().hex[:4]}{suffix}"
        )
    return candidate


def resolve_rewrite_target(state: TaskSkillGraphState, config) -> TaskSkillGraphState:
    conversation_id = str(state.get("conversation_id") or "").strip()
    rewrite_user_prompt = str(state.get("rewrite_user_prompt") or "").strip()
    if not conversation_id:
        raise ValueError("conversation_id 不能为空")
    if not rewrite_user_prompt:
        raise ValueError("rewrite_user_prompt 不能为空")

    conversation_service = get_conversation_service()
    rewrite_messages = conversation_service.list_rewrite_messages(conversation_id)
    if not rewrite_messages:
        raise ValueError("当前会话没有可用的 rewrite 历史")

    selected_index = _select_rewrite_target_index(rewrite_user_prompt, rewrite_messages, config)
    assistant_messages = _list_assistant_messages(rewrite_messages)
    target_state = dict(assistant_messages[selected_index].rewrite_state or {})

    source_prepared_doc_path = pathlib.Path(
        str(target_state.get("prepared_doc_path") or "")
    ).expanduser()
    if not source_prepared_doc_path.is_file():
        raise FileNotFoundError(f"rewrite 目标文档不存在: {source_prepared_doc_path}")

    rewrite_output_path = _build_rewrite_output_path(source_prepared_doc_path.resolve())
    rewrite_output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(source_prepared_doc_path), str(rewrite_output_path))

    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    cleanup_holder = configurable.get("rewrite_cleanup_holder")
    if isinstance(cleanup_holder, dict):
        cleanup_holder["path"] = str(rewrite_output_path)

    updates: Dict[str, Any] = {
        "conversation_id": conversation_id,
        "rewrite_user_prompt": rewrite_user_prompt,
        "rewrite_target_index": selected_index,
        "rewrite_base_text": str(target_state.get("polished_text") or ""),
        "source_document_path": str(rewrite_output_path),
        "prepared_doc_path": str(rewrite_output_path),
        "rewrite_temp_output_path": str(rewrite_output_path),
        "source_prepared_doc_path": str(source_prepared_doc_path.resolve()),
        "rewrite_mode": True,
    }

    for key, value in target_state.items():
        if key in {"prepared_doc_path", "polished_text"}:
            continue
        if isinstance(value, str):
            updates[key] = value

    return TaskSkillGraphState(**updates)


def _build_rewrite_prompt(
    *,
    state: TaskSkillGraphState,
    rewrite_user_prompt: str,
    protected_markers: tuple[str, ...],
) -> tuple[str, str]:
    skill = get_skill_guide("rewrite")
    rendered_prompt = render_task_skill_prompt(
        TaskSkillPromptInput(
            skill_id=skill.name,
            instruction=_extract_rewrite_runtime_instruction(skill.instruction),
            sections=(
                TaskSkillPromptSection(
                    title="当前文档内容",
                    content=str(state.get("rewrite_base_text") or state.get("polished_text") or ""),
                ),
                TaskSkillPromptSection(
                    title="技术参数参考资料",
                    content=str(state.get("tender_params") or ""),
                ),
                TaskSkillPromptSection(
                    title="用户修改指令",
                    content=rewrite_user_prompt,
                ),
                TaskSkillPromptSection(
                    title="受保护字段要求",
                    content=_format_protected_requirement(protected_markers),
                ),
            ),
        )
    )
    return rendered_prompt.system_prompt, rendered_prompt.user_prompt


def _build_rewrite_callbacks(
    *,
    config: Dict[str, Any] | None,
    audit_stage: str | None = None,
) -> StreamCallbacks:
    configurable = _get_configurable(config)
    suppress_llm_stdout = bool(configurable.get("suppress_llm_stdout", False))
    task_audit_log_path = resolve_task_audit_log_path(config)

    def _log_chunk(text: str) -> None:
        if not suppress_llm_stdout:
            progress_log.debug(text)

    def _capture_request_messages(messages: list[dict[str, Any]]) -> None:
        if not audit_stage or not task_audit_log_path:
            return
        write_task_audit_stage(
            task_audit_log_path,
            audit_stage,
            messages,
        )

    return StreamCallbacks(
        on_chunk=_log_chunk,
        on_request_messages=_capture_request_messages if audit_stage else None,
    )


def _run_rewrite_subagent(
    *,
    state: TaskSkillGraphState,
    config: Dict[str, Any] | None,
    rewrite_user_prompt: str,
    protected_markers: tuple[str, ...],
) -> str:
    system_prompt, user_prompt = _build_rewrite_prompt(
        state=state,
        rewrite_user_prompt=rewrite_user_prompt,
        protected_markers=protected_markers,
    )
    task_audit_log_path = resolve_task_audit_log_path(config)
    if task_audit_log_path:
        write_task_audit_stage(
            task_audit_log_path,
            REWRITE_STAGE_SKILL_PROMPT_RENDER,
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

    return str(
        _run_async(
            stream_llm_completion(
                model_provider=_get_model_provider(config),
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                callbacks=_build_rewrite_callbacks(
                    config=config,
                    audit_stage=REWRITE_STAGE_TEXT,
                ),
                check_interval=3.0,
            )
        )
    )


def _render_verify_user_prompt(
    *,
    base_text: str,
    candidate_text: str,
    rewrite_user_prompt: str,
    protected_markers: tuple[str, ...],
) -> str:
    return (
        "请审核【重写后正文】是否满足 rewrite 契约。\n\n"
        "输出必须是严格 JSON 数组：[] 或 "
        '[{"evidence":"...","fix_hint":"..."}]。'
        "不要输出解释、Markdown、代码块或其它字段。\n\n"
        "【用户修改指令】\n"
        f"{rewrite_user_prompt}\n\n"
        "【受保护字段要求】\n"
        f"{_format_protected_requirement(protected_markers)}\n\n"
        "【当前文档内容】\n"
        f"{base_text}\n\n"
        "【重写后正文】\n"
        f"{candidate_text}"
    )


def _run_verify_subagent(
    *,
    base_text: str,
    candidate_text: str,
    rewrite_user_prompt: str,
    protected_markers: tuple[str, ...],
    config: Dict[str, Any] | None,
) -> list[AuditFinding]:
    raw_content = str(
        _run_async(
            stream_llm_completion(
                model_provider=_get_model_provider(config),
                system_prompt=REWRITE_VERIFY_SYSTEM_PROMPT,
                user_prompt=_render_verify_user_prompt(
                    base_text=base_text,
                    candidate_text=candidate_text,
                    rewrite_user_prompt=rewrite_user_prompt,
                    protected_markers=protected_markers,
                ),
                callbacks=_build_rewrite_callbacks(config=config),
                extra_params_override={"temperature": 0.0},
                check_interval=3.0,
            )
        )
    )
    llm_findings = coerce_audit_findings(raw_content, fallback_on_error=True)
    protected_findings = _audit_protected_fields(
        base_text=base_text,
        candidate_text=candidate_text,
        markers=protected_markers,
    )
    return protected_findings + llm_findings


def _render_revise_user_prompt(
    *,
    base_text: str,
    rewrite_user_prompt: str,
    protected_markers: tuple[str, ...],
    current_text: str,
    findings: list[AuditFinding],
) -> str:
    return (
        "请按审核 JSON 对【当前重写正文】做最小必要修复。\n"
        "除 evidence/fix_hint 明确指定的位置外，其它内容必须保持不变。\n\n"
        "【用户修改指令】\n"
        f"{rewrite_user_prompt}\n\n"
        "【受保护字段要求】\n"
        f"{_format_protected_requirement(protected_markers)}\n\n"
        "【当前文档内容】\n"
        f"{base_text}\n\n"
        "【审核 JSON】\n"
        f"{json.dumps(_findings_to_payload(findings), ensure_ascii=False)}\n\n"
        "【当前重写正文】\n"
        f"{current_text}"
    )


def _run_revise_subagent(
    *,
    base_text: str,
    rewrite_user_prompt: str,
    protected_markers: tuple[str, ...],
    current_text: str,
    findings: list[AuditFinding],
    config: Dict[str, Any] | None,
) -> str:
    return str(
        _run_async(
            stream_llm_completion(
                model_provider=_get_model_provider(config),
                system_prompt=REWRITE_REVISE_SYSTEM_PROMPT,
                user_prompt=_render_revise_user_prompt(
                    base_text=base_text,
                    rewrite_user_prompt=rewrite_user_prompt,
                    protected_markers=protected_markers,
                    current_text=current_text,
                    findings=findings,
                ),
                callbacks=_build_rewrite_callbacks(config=config),
                extra_params_override={"temperature": 0.1},
                check_interval=3.0,
            )
        )
    )


def rewrite_text(state: TaskSkillGraphState, config) -> TaskSkillGraphState:
    rewrite_user_prompt = str(state.get("rewrite_user_prompt") or "").strip()
    if not rewrite_user_prompt:
        raise ValueError("rewrite_user_prompt 不能为空")

    base_text = str(state.get("rewrite_base_text") or state.get("polished_text") or "")
    if not base_text.strip():
        raise ValueError("rewrite_base_text 不能为空")

    protected_markers = _protected_markers_for_state(state)
    tracker = _RewriteAgentStepTracker(config)

    draft_text = _run_rewrite_subagent(
        state=state,
        config=config,
        rewrite_user_prompt=rewrite_user_prompt,
        protected_markers=protected_markers,
    )
    tracker.emit(
        node=REWRITE_GENERATE_AGENT_NODE,
        phase="draft",
        label="重写正文",
        summary=f"重写正文完成，约 {_text_chars(draft_text)} 字。",
        round_index=1,
        content=draft_text,
    )

    current_text = draft_text
    latest_findings: list[AuditFinding] = []
    revision_rounds = 0

    for round_index in range(1, REWRITE_MAX_AUDIT_ROUNDS + 1):
        latest_findings = _run_verify_subagent(
            base_text=base_text,
            candidate_text=current_text,
            rewrite_user_prompt=rewrite_user_prompt,
            protected_markers=protected_markers,
            config=config,
        )
        audit_summary = (
            f"第 {round_index} 轮审核发现 {len(latest_findings)} 个问题。"
            if latest_findings
            else f"第 {round_index} 轮审核通过。"
        )
        tracker.emit(
            node=REWRITE_VERIFY_AGENT_NODE,
            phase="audit",
            label="重写审核" if round_index == 1 else f"第 {round_index} 轮复核",
            summary=audit_summary,
            round_index=round_index,
            content=json.dumps(_findings_to_payload(latest_findings), ensure_ascii=False),
            findings=latest_findings,
        )

        if not latest_findings:
            break
        if round_index >= REWRITE_MAX_AUDIT_ROUNDS:
            break

        revised_text = _run_revise_subagent(
            base_text=base_text,
            rewrite_user_prompt=rewrite_user_prompt,
            protected_markers=protected_markers,
            current_text=current_text,
            findings=latest_findings,
            config=config,
        )
        revision_rounds += 1
        current_text = revised_text
        tracker.emit(
            node=REWRITE_REVISE_AGENT_NODE,
            phase="revision",
            label=f"第 {round_index} 轮修订",
            summary=f"第 {round_index} 轮修订完成，已处理 {len(latest_findings)} 个问题。",
            round_index=round_index,
            content=revised_text,
            findings=latest_findings,
        )

    remaining_protected_findings = _audit_protected_fields(
        base_text=base_text,
        candidate_text=current_text,
        markers=protected_markers,
    )
    if remaining_protected_findings:
        joined = "；".join(finding.evidence for finding in remaining_protected_findings)
        raise ValueError(f"rewrite 智能体审核未通过: {joined}")

    final_summary = (
        f"最终完成，修复 {revision_rounds} 轮，最终正文约 {_text_chars(current_text)} 字。"
    )
    tracker.emit(
        node=REWRITE_AGENT_NODE,
        phase="final",
        label="最终完成",
        summary=final_summary,
        round_index=max(1, revision_rounds + 1),
        content=final_summary,
        findings=latest_findings,
        final_result={
            "summary": final_summary,
            "revision_rounds": revision_rounds,
            "final_chars": _text_chars(current_text),
            "issue_count": len(latest_findings),
            "content": current_text,
        },
    )

    return TaskSkillGraphState(
        polished_text=current_text,
        generate_polished_done=True,
    )
