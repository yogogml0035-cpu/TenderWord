"""Agent run runtime for the task-context assistant stream."""

from __future__ import annotations

import ast
import asyncio
import inspect
import json
import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Optional, Protocol

from pydantic import BaseModel, ValidationError

from backend.agents.generation.model_factory import create_generation_chat_model
from backend.agents.task_context_assistant import (
    AgentRunAuditLogger,
    CREATE_REWRITE_TASK_TOOL,
    RewriteTaskExecutor,
    TaskContextAssistantToolContext,
    create_read_current_conversation_summary_tool,
    create_read_current_task_public_summary_tool,
    create_rewrite_task_tool,
    create_task_context_assistant,
)
from backend.models import (
    AgentNeedsInputEventData,
    AgentRunDoneEventData,
    AgentRunErrorEventData,
    AgentRunRewriteContextSnapshot,
    AgentRunStartedEventData,
    AgentRunStreamRequest,
    AgentSkill,
    AgentTaskAcceptedEventData,
    AgentThinkingStageEventData,
    AgentToolCallEventData,
    GenerateResponse,
    TaskKind,
    TaskStatus,
)
from backend.services.chat_stream_service import to_ndjson_line

logger = logging.getLogger(__name__)

AgentRunRuntime = Literal["fake", "deepagents"]


@dataclass(frozen=True)
class AgentRunDecision:
    selected_skill: AgentSkill | None
    guard_summary: str
    guard_result: Literal["passed", "needs_input"]
    message: str
    missing_requirements: tuple[str, ...] = field(default_factory=tuple)
    tool_name: str | None = None
    task_kind: TaskKind | None = None
    task_id: str | None = None
    status: TaskStatus = TaskStatus.QUEUED
    queue_position: int = 0
    waiting_count: int = 0

    @classmethod
    def task_created(
        cls,
        *,
        response: GenerateResponse,
        guard_summary: str,
        done_message: str,
        tool_name: str = CREATE_REWRITE_TASK_TOOL,
    ) -> "AgentRunDecision":
        return cls(
            selected_skill=AgentSkill.REWRITE,
            guard_summary=guard_summary,
            guard_result="passed",
            message=done_message,
            tool_name=tool_name,
            task_kind=response.task_kind,
            task_id=response.task_id,
            status=response.status or TaskStatus.QUEUED,
            queue_position=response.queue_position
            if response.queue_position is not None
            else 0,
            waiting_count=response.waiting_count
            if response.waiting_count is not None
            else 0,
        )

    @classmethod
    def needs_input(
        cls,
        *,
        message: str,
        guard_summary: str,
        missing_requirements: list[str] | tuple[str, ...],
        selected_skill: AgentSkill | None = None,
    ) -> "AgentRunDecision":
        return cls(
            selected_skill=selected_skill,
            guard_summary=guard_summary,
            guard_result="needs_input",
            message=message,
            missing_requirements=tuple(missing_requirements),
        )


class TaskContextAssistantRunner(Protocol):
    async def run(self, payload: AgentRunStreamRequest) -> AgentRunDecision:
        ...


class TaskContextDeepAgentsRunner:
    """Runs the real DeepAgents task-context assistant and normalizes its result."""

    def __init__(
        self,
        *,
        audit_logger: AgentRunAuditLogger,
        agent_factory: Callable[..., Any] | None = None,
        model_factory: Callable[[str], Any] | None = None,
    ) -> None:
        self._audit_logger = audit_logger
        self._agent_factory = agent_factory or create_task_context_assistant
        self._model_factory = model_factory or create_generation_chat_model

    async def run(self, payload: AgentRunStreamRequest) -> AgentRunDecision:
        agent_layout = self._agent_factory(
            model=self._model_factory(payload.model.value),
            tools=self._build_tools(),
        )
        try:
            output = await self._invoke_agent(
                getattr(agent_layout, "agent"),
                self._build_agent_payload(payload),
                self._build_agent_config(payload),
            )
        finally:
            cleanup = getattr(agent_layout, "cleanup", None)
            if callable(cleanup):
                cleanup()

        return self._decision_from_agent_output(payload, output)

    def _build_tools(self) -> list[Any]:
        context = TaskContextAssistantToolContext(
            agent_run_audit_logger=self._audit_logger,
        )
        return [
            create_rewrite_task_tool(context),
            create_read_current_conversation_summary_tool(context),
            create_read_current_task_public_summary_tool(context),
        ]

    def _build_agent_payload(self, payload: AgentRunStreamRequest) -> dict[str, Any]:
        context_json = json.dumps(
            payload.context_snapshot.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        )
        selected_skills = [skill.value for skill in payload.selected_skills]
        user_prompt = f"""
你已经拿到 TenderWord 前端提交的受控上下文快照。用户不需要显式输入 `/rewrite` 或 `$rewrite`，你必须根据本轮消息语义和上下文决定是否调用 rewrite skill。

可用 skill：
- rewrite：基于当前会话已生成文档或已上传 Word 文件继续修改、改写、润色、补充、压缩、调整格式/排版/行距/换行/风格。

当前请求：
- conversation_id: {payload.conversation_id}
- model: {payload.model.value}
- explicit_selected_skills: {json.dumps(selected_skills, ensure_ascii=False)}
- user_message: {payload.message}

受控上下文快照：
{context_json}

决策要求：
1. 如果用户是在已有生成文档或上传 Word 文件基础上表达内容、条款、参数、格式、排版、行距、换行、长短、风格等调整诉求，应选择 rewrite 并调用 create_rewrite_task_tool。
2. 当前会话已有 rewrite history 且没有上传文件时，调用 create_rewrite_task_tool 只传 conversation_id、user_prompt、model、rewrite_log_path=null。
3. 存在上传 Word 文件时，必须同时传 file_path、form_type、insertion_config、tender_lx、fund_source_lx 和可用的 tender_data_snapshot。
4. 如果上下文缺少执行 rewrite 的必要条件，不要调用工具，只做最小追问。
5. 如果用户消息不是文档任务请求，说明当前任务上下文助手只支持 rewrite，不要编造其他能力。
6. 最终回复只给任务创建结果或最小追问，不要暴露隐藏推理、客户原文或本机路径。
""".strip()
        return {"messages": [{"role": "user", "content": user_prompt}]}

    def _build_agent_config(self, payload: AgentRunStreamRequest) -> dict[str, Any]:
        return {
            "configurable": {
                "conversation_id": payload.conversation_id,
                "agent_context_snapshot": payload.context_snapshot.model_dump(
                    mode="json"
                ),
            }
        }

    async def _invoke_agent(
        self,
        agent: Any,
        payload: dict[str, Any],
        config: dict[str, Any],
    ) -> Any:
        ainvoke = getattr(agent, "ainvoke", None)
        if callable(ainvoke):
            if _call_accepts_config(ainvoke):
                return await ainvoke(payload, config)
            return await ainvoke(payload)

        invoke = getattr(agent, "invoke", None)
        if callable(invoke):
            if _call_accepts_config(invoke):
                return await asyncio.to_thread(invoke, payload, config)
            return await asyncio.to_thread(invoke, payload)

        raise RuntimeError("task-context assistant runner does not support invoke")

    def _decision_from_agent_output(
        self,
        payload: AgentRunStreamRequest,
        output: Any,
    ) -> AgentRunDecision:
        tool_result = _find_generate_response_payload(output)
        if tool_result is not None:
            try:
                response = GenerateResponse.model_validate(tool_result)
            except ValidationError as exc:
                raise RuntimeError(
                    "create_rewrite_task_tool returned invalid payload"
                ) from exc
            return _decision_from_rewrite_response(payload, response)

        final_text = _last_message_text(output)
        return AgentRunDecision.needs_input(
            selected_skill=_explicit_selected_skill(payload),
            guard_summary="任务上下文助手未创建 rewrite 任务。",
            message=final_text or "请说明要如何修改当前文档。",
            missing_requirements=_infer_missing_requirements(payload),
        )

class DirectRewriteTaskRunner:
    """Compatibility runner used by tests and explicit dependency injection."""

    def __init__(self, rewrite_task_executor: RewriteTaskExecutor) -> None:
        self._rewrite_task_executor = rewrite_task_executor

    async def run(self, payload: AgentRunStreamRequest) -> AgentRunDecision:
        uploaded_file = (
            payload.context_snapshot.uploaded_files[0]
            if payload.context_snapshot.uploaded_files
            else None
        )
        if uploaded_file is not None:
            missing_rewrite_context = _validate_uploaded_rewrite_context(
                payload.context_snapshot.rewrite_context
            )
            if missing_rewrite_context is not None:
                return AgentRunDecision.needs_input(
                    selected_skill=AgentSkill.REWRITE,
                    guard_summary=str(missing_rewrite_context["summary"]),
                    message=str(missing_rewrite_context["message"]),
                    missing_requirements=list(
                        missing_rewrite_context["missing_requirements"]
                    ),
                )

            rewrite_context = payload.context_snapshot.rewrite_context
            assert rewrite_context is not None
            response = await self._rewrite_task_executor(
                conversation_id=payload.conversation_id,
                user_prompt=payload.message,
                model=payload.model,
                rewrite_log_path=None,
                file_path=uploaded_file.file_path,
                form_type=rewrite_context.form_type,
                insertion_config=rewrite_context.insertion_config,
                tender_lx=rewrite_context.tender_lx,
                fund_source_lx=rewrite_context.fund_source_lx,
                tender_data_snapshot=rewrite_context.tender_data_snapshot,
            )
            return _decision_from_rewrite_response(
                payload,
                response,
                guard_summary="检测到当前会话已有上传文件和完整 rewrite 上下文。",
            )

        if not payload.context_snapshot.rewrite_available:
            return _missing_rewrite_history_decision(
                selected_skill=AgentSkill.REWRITE
                if _explicit_selected_skill(payload) == AgentSkill.REWRITE
                else None
            )

        response = await self._rewrite_task_executor(
            conversation_id=payload.conversation_id,
            user_prompt=payload.message,
            model=payload.model,
            rewrite_log_path=None,
        )
        return _decision_from_rewrite_response(
            payload,
            response,
            guard_summary="检测到当前会话已有可改写文档。",
        )


class AgentRunService:
    """Streams task-context assistant events for the frontend thinking card."""

    def __init__(
        self,
        *,
        run_id_factory: Optional[Callable[[], str]] = None,
        agent_runner: TaskContextAssistantRunner | None = None,
        rewrite_task_executor: RewriteTaskExecutor | None = None,
        audit_logger: AgentRunAuditLogger | None = None,
        runtime: AgentRunRuntime = "deepagents",
    ) -> None:
        self._run_id_factory = run_id_factory or (
            lambda: f"run-{uuid.uuid4().hex}"
        )
        self._audit_logger = audit_logger or AgentRunAuditLogger()
        self._agent_runner = agent_runner or (
            DirectRewriteTaskRunner(rewrite_task_executor)
            if rewrite_task_executor is not None
            else None
        )
        self._runtime = runtime

    async def stream(
        self,
        request: Any,
        payload: AgentRunStreamRequest,
    ) -> AsyncIterator[str]:
        """按 NDJSON 输出 agent run 事件。"""

        run_id = self._run_id_factory()

        if await self._is_disconnected(request):
            return

        yield self._emit_event(
            event_name="run_started",
            payload=AgentRunStartedEventData(
                run_id=run_id,
                conversation_id=payload.conversation_id,
                model=payload.model,
                runtime=self._runtime,
                selected_skills=payload.selected_skills,
            ),
            request_payload=payload,
        )

        if await self._is_disconnected(request):
            return

        yield self._emit_event(
            event_name="thinking_stage",
            payload=AgentThinkingStageEventData(
                run_id=run_id,
                stage="understand",
                label="理解需求",
                status="completed",
                summary=self._build_understand_summary(payload),
                selected_skill=_explicit_selected_skill(payload),
            ),
            request_payload=payload,
        )

        try:
            decision = self._preflight_decision(payload)
            if decision is None:
                decision = await self._get_agent_runner().run(payload)
            for event_name, event_data in self._build_decision_events(
                run_id=run_id,
                decision=decision,
            ):
                if await self._is_disconnected(request):
                    return
                yield self._emit_event(
                    event_name=event_name,
                    payload=event_data,
                    request_payload=payload,
                )
                await asyncio.sleep(0)
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception(
                "agent run deepagents runtime failed: conversation_id=%s, run_id=%s",
                payload.conversation_id,
                run_id,
            )
            if await self._is_disconnected(request):
                return
            yield self._emit_event(
                event_name="error",
                payload=AgentRunErrorEventData(
                    run_id=run_id,
                    code="AGENT_RUN_FAILED",
                    message="agent run 执行失败，请稍后重试",
                ),
                request_payload=payload,
            )

    def _get_agent_runner(self) -> TaskContextAssistantRunner:
        if self._agent_runner is not None:
            return self._agent_runner
        return TaskContextDeepAgentsRunner(audit_logger=self._audit_logger)

    def _preflight_decision(
        self,
        payload: AgentRunStreamRequest,
    ) -> AgentRunDecision | None:
        if payload.context_snapshot.uploaded_files:
            missing_rewrite_context = _validate_uploaded_rewrite_context(
                payload.context_snapshot.rewrite_context
            )
            if missing_rewrite_context is None:
                return None
            return AgentRunDecision.needs_input(
                selected_skill=AgentSkill.REWRITE,
                guard_summary=str(missing_rewrite_context["summary"]),
                message=str(missing_rewrite_context["message"]),
                missing_requirements=list(
                    missing_rewrite_context["missing_requirements"]
                ),
            )

        if not payload.context_snapshot.rewrite_available:
            return _missing_rewrite_history_decision(
                selected_skill=AgentSkill.REWRITE
                if _explicit_selected_skill(payload) == AgentSkill.REWRITE
                else None
            )

        return None

    def _build_decision_events(
        self,
        *,
        run_id: str,
        decision: AgentRunDecision,
    ) -> list[tuple[str, BaseModel]]:
        events: list[tuple[str, BaseModel]] = [
            (
                "thinking_stage",
                AgentThinkingStageEventData(
                    run_id=run_id,
                    stage="guard",
                    label="检查上下文",
                    status="completed",
                    summary=decision.guard_summary,
                    selected_skill=decision.selected_skill,
                    guard_result=decision.guard_result,
                ),
            )
        ]

        if decision.guard_result == "needs_input":
            events.append(
                (
                    "needs_input",
                    AgentNeedsInputEventData(
                        run_id=run_id,
                        message=decision.message,
                        selected_skill=decision.selected_skill,
                        missing_requirements=list(decision.missing_requirements),
                    ),
                )
            )
            return events

        if not decision.tool_name or not decision.task_kind or not decision.task_id:
            events.append(
                (
                    "error",
                    AgentRunErrorEventData(
                        run_id=run_id,
                        code="AGENT_RUN_INVALID_DECISION",
                        message="agent run 未返回有效任务创建结果，请重试",
                    ),
                )
            )
            return events

        events.extend(
            [
                (
                    "tool_call",
                    AgentToolCallEventData(
                        run_id=run_id,
                        tool_name=decision.tool_name,
                        summary=f"已调用 {decision.tool_name}。",
                        task_kind=decision.task_kind,
                    ),
                ),
                (
                    "task_accepted",
                    AgentTaskAcceptedEventData(
                        run_id=run_id,
                        task_id=decision.task_id,
                        task_kind=decision.task_kind,
                        status=decision.status,
                        queue_position=decision.queue_position,
                        waiting_count=decision.waiting_count,
                    ),
                ),
                (
                    "done",
                    AgentRunDoneEventData(
                        run_id=run_id,
                        message=decision.message,
                        task_id=decision.task_id,
                        selected_skill=decision.selected_skill,
                    ),
                ),
            ]
        )
        return events

    def _build_understand_summary(self, payload: AgentRunStreamRequest) -> str:
        if _explicit_selected_skill(payload) == AgentSkill.REWRITE:
            return "已收到明确的 rewrite 请求。"
        return "已收到用户消息，正在结合当前文档上下文判断可执行任务。"

    async def _is_disconnected(self, request: Any) -> bool:
        checker = getattr(request, "is_disconnected", None)
        if not callable(checker):
            return False
        result = checker()
        if asyncio.iscoroutine(result):
            return bool(await result)
        return bool(result)

    def _emit_event(
        self,
        *,
        event_name: str,
        payload: BaseModel,
        request_payload: AgentRunStreamRequest,
    ) -> str:
        self._audit_logger.append_event(
            event_name=event_name,
            conversation_id=request_payload.conversation_id,
            selected_skills=request_payload.selected_skills,
            payload=payload,
        )
        return self._event_line(event_name, payload)

    def _event_line(self, event_name: str, payload: BaseModel) -> str:
        return to_ndjson_line(event_name, payload.model_dump(mode="json"))


def _call_accepts_config(callable_obj: Callable[..., Any]) -> bool:
    try:
        signature = inspect.signature(callable_obj)
    except (TypeError, ValueError):
        return True

    parameters = list(signature.parameters.values())
    if any(parameter.kind == inspect.Parameter.VAR_POSITIONAL for parameter in parameters):
        return True
    if "config" in signature.parameters:
        return True
    positional_count = sum(
        parameter.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
        for parameter in parameters
    )
    return positional_count >= 2


def _decision_from_rewrite_response(
    payload: AgentRunStreamRequest,
    response: GenerateResponse,
    *,
    guard_summary: str = "DeepAgents 已根据用户语义和当前文档上下文选择 rewrite。",
) -> AgentRunDecision:
    if not response.success:
        if response.error in {"REWRITE_NO_DOCUMENT", "REQ_MISSING_FIELD"}:
            return AgentRunDecision.needs_input(
                selected_skill=AgentSkill.REWRITE,
                guard_summary="已选择 rewrite，但当前上下文缺少必要条件。",
                message=response.message or "请先补全要修改的文档和当前页面上下文。",
                missing_requirements=_infer_missing_requirements(payload),
            )
        raise RuntimeError(
            response.error or response.message or "create_rewrite_task_tool failed"
        )

    if response.task_kind != TaskKind.REWRITE:
        raise RuntimeError("create_rewrite_task_tool returned non-rewrite task")

    return AgentRunDecision.task_created(
        response=response,
        guard_summary=guard_summary,
        done_message="已为你创建 rewrite 任务。",
    )


def _missing_rewrite_history_decision(
    *,
    selected_skill: AgentSkill | None,
) -> AgentRunDecision:
    return AgentRunDecision.needs_input(
        selected_skill=selected_skill,
        guard_summary="当前会话缺少可改写文档上下文。",
        message="当前会话没有可用文档，请先完成一次生成。",
        missing_requirements=["rewrite_history"],
    )


def _validate_uploaded_rewrite_context(
    rewrite_context: AgentRunRewriteContextSnapshot | None,
) -> dict[str, str | list[str]] | None:
    if rewrite_context is None:
        return {
            "summary": "当前页面缺少可识别的 rewrite 上下文。",
            "message": "请先补全当前页面的 rewrite 上下文。",
            "missing_requirements": ["rewrite_context"],
        }

    insertion_config = rewrite_context.insertion_config
    before_text = str(getattr(insertion_config, "before_text", "") or "").strip()
    after_text = str(getattr(insertion_config, "after_text", "") or "").strip()
    if not before_text or not after_text:
        return {
            "summary": "当前页面缺少插入锚点配置。",
            "message": "请先补全当前页面的插入锚点。",
            "missing_requirements": ["insertion_config"],
        }

    if rewrite_context.form_type is None:
        return {
            "summary": "当前页面缺少可识别的表单类型。",
            "message": "请先补全当前页面的招标类型。",
            "missing_requirements": ["form_type"],
        }

    missing_draft_fields: list[str] = []
    if rewrite_context.tender_lx is None:
        missing_draft_fields.append("tender_lx")
    if rewrite_context.fund_source_lx is None:
        missing_draft_fields.append("fund_source_lx")
    if missing_draft_fields:
        return {
            "summary": "当前页面缺少必要的标的类型或资金性质。",
            "message": "请先补全当前页面的货物/工程/服务类型和资金性质。",
            "missing_requirements": missing_draft_fields,
        }

    return None


def _explicit_selected_skill(payload: AgentRunStreamRequest) -> AgentSkill | None:
    return payload.selected_skills[0] if payload.selected_skills else None


def _infer_missing_requirements(payload: AgentRunStreamRequest) -> list[str]:
    if not payload.context_snapshot.uploaded_files:
        if payload.context_snapshot.rewrite_available:
            return ["rewrite_instruction"]
        return ["rewrite_history"]

    rewrite_context = payload.context_snapshot.rewrite_context
    if rewrite_context is None:
        return ["rewrite_context"]

    missing: list[str] = []
    insertion_config = rewrite_context.insertion_config
    before_text = str(getattr(insertion_config, "before_text", "") or "").strip()
    after_text = str(getattr(insertion_config, "after_text", "") or "").strip()
    if insertion_config is None or not before_text or not after_text:
        missing.append("insertion_config")
    if rewrite_context.form_type is None:
        missing.append("form_type")
    if rewrite_context.tender_lx is None:
        missing.append("tender_lx")
    if rewrite_context.fund_source_lx is None:
        missing.append("fund_source_lx")
    return missing or ["rewrite_context"]


def _find_generate_response_payload(output: Any) -> dict[str, Any] | None:
    for message in _iter_messages(output):
        if _message_name(message) not in ("", CREATE_REWRITE_TASK_TOOL):
            continue
        for candidate in _coerce_candidate_payloads(_message_content(message)):
            if _looks_like_generate_response(candidate):
                return candidate

    for candidate in _coerce_candidate_payloads(output):
        if _looks_like_generate_response(candidate):
            return candidate

    return None


def _iter_messages(value: Any):
    if value is None:
        return
    if isinstance(value, dict):
        messages = value.get("messages")
        if messages is not None:
            yield from _iter_messages(messages)
            return
        if "content" in value:
            yield value
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_messages(item)
        return
    if hasattr(value, "content"):
        yield value


def _message_name(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("name") or "").strip()
    return str(getattr(message, "name", "") or "").strip()


def _message_content(message: Any) -> Any:
    if isinstance(message, dict):
        return message.get("content")
    return getattr(message, "content", None)


def _message_text(message: Any) -> str:
    content = _message_content(message)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
        return "".join(parts).strip()
    return str(content or "").strip()


def _last_message_text(output: Any) -> str:
    if isinstance(output, str):
        return output.strip()

    text = ""
    for message in _iter_messages(output):
        if _looks_like_tool_message(message):
            continue
        next_text = _message_text(message)
        if next_text:
            text = next_text
    return text


def _looks_like_tool_message(message: Any) -> bool:
    if isinstance(message, dict):
        message_type = str(message.get("type") or "").lower()
        if message_type == "tool":
            return True
        return bool(message.get("tool_call_id"))
    return message.__class__.__name__ == "ToolMessage" or bool(
        getattr(message, "tool_call_id", None)
    )


def _coerce_candidate_payloads(value: Any):
    if value is None:
        return
    if isinstance(value, dict):
        yield value
        for nested_key in ("data", "result", "output"):
            if nested_key in value:
                yield from _coerce_candidate_payloads(value[nested_key])
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            yield from _coerce_candidate_payloads(item)
        return
    if not isinstance(value, str):
        return

    normalized = value.strip()
    if not normalized:
        return
    parsed = _parse_mapping_text(normalized)
    if parsed is not None:
        yield from _coerce_candidate_payloads(parsed)


def _parse_mapping_text(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        pass

    try:
        return ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return None


def _looks_like_generate_response(value: dict[str, Any]) -> bool:
    return "success" in value and "task_id" in value


_agent_run_service: AgentRunService | None = None


def get_agent_run_service() -> AgentRunService:
    """获取 agent run 服务单例。"""

    global _agent_run_service
    if _agent_run_service is None:
        _agent_run_service = AgentRunService()
    return _agent_run_service


__all__ = [
    "AgentRunDecision",
    "AgentRunService",
    "TaskContextAssistantRunner",
    "TaskContextDeepAgentsRunner",
    "get_agent_run_service",
]
