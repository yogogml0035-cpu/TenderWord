"""Fake agent run runtime for the new task-context assistant stream."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any, Callable, Optional

from pydantic import BaseModel

from backend.agents.task_context_assistant import (
    AgentRunAuditLogger,
    CREATE_REWRITE_TASK_TOOL,
    RewriteTaskExecutor,
    make_create_rewrite_task_executor,
)
from backend.models import (
    AgentRunRewriteContextSnapshot,
    AgentNeedsInputEventData,
    AgentRunDoneEventData,
    AgentRunErrorEventData,
    AgentRunStartedEventData,
    AgentRunStreamRequest,
    AgentSkill,
    AgentTaskAcceptedEventData,
    AgentThinkingStageEventData,
    AgentToolCallEventData,
    TaskKind,
    TaskStatus,
)
from backend.services.chat_stream_service import to_ndjson_line

logger = logging.getLogger(__name__)


class AgentRunService:
    """首期 agent run fake runtime。"""

    def __init__(
        self,
        *,
        run_id_factory: Optional[Callable[[], str]] = None,
        task_id_factory: Optional[Callable[[AgentSkill], str]] = None,
        rewrite_task_executor: RewriteTaskExecutor | None = None,
        audit_logger: AgentRunAuditLogger | None = None,
    ) -> None:
        self._run_id_factory = run_id_factory or (
            lambda: f"run-{uuid.uuid4().hex}"
        )
        self._task_id_factory = task_id_factory or self._default_task_id_factory
        self._rewrite_task_executor = (
            rewrite_task_executor or make_create_rewrite_task_executor()
        )
        self._audit_logger = audit_logger or AgentRunAuditLogger()

    async def stream(
        self,
        request: Any,
        payload: AgentRunStreamRequest,
    ) -> AsyncIterator[str]:
        """按 NDJSON 输出 fake agent run 事件。"""

        run_id = self._run_id_factory()
        selected_skill = self._select_skill(payload)

        if await self._is_disconnected(request):
            return

        yield self._emit_event(
            event_name="run_started",
            payload=AgentRunStartedEventData(
                run_id=run_id,
                conversation_id=payload.conversation_id,
                model=payload.model,
                selected_skills=payload.selected_skills,
            ),
            request_payload=payload,
        )

        try:
            for event_name, event_data in await self._build_run_plan(
                run_id=run_id,
                payload=payload,
                selected_skill=selected_skill,
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
                "agent run fake runtime failed: conversation_id=%s, run_id=%s",
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

    async def _build_run_plan(
        self,
        *,
        run_id: str,
        payload: AgentRunStreamRequest,
        selected_skill: AgentSkill | None,
    ) -> list[tuple[str, BaseModel]]:
        plan: list[tuple[str, BaseModel]] = []
        plan.append(
            (
                "thinking_stage",
                AgentThinkingStageEventData(
                    run_id=run_id,
                    stage="understand",
                    label="理解需求",
                    status="completed",
                    summary=self._build_understand_summary(payload.message, selected_skill),
                    selected_skill=selected_skill,
                ),
            )
        )

        if selected_skill == AgentSkill.REWRITE:
            return plan + await self._build_rewrite_plan(run_id=run_id, payload=payload)

        plan.append(
            (
                "thinking_stage",
                AgentThinkingStageEventData(
                    run_id=run_id,
                    stage="guard",
                    label="检查上下文",
                    status="completed",
                    summary="fake runtime 暂时只支持 rewrite 任务创建。",
                    guard_result="needs_input",
                ),
            )
        )
        plan.append(
            (
                "needs_input",
                AgentNeedsInputEventData(
                    run_id=run_id,
                    message="请说明这次要执行 rewrite。",
                    missing_requirements=["selected_skill"],
                ),
            )
        )
        return plan

    async def _build_rewrite_plan(
        self,
        *,
        run_id: str,
        payload: AgentRunStreamRequest,
    ) -> list[tuple[str, BaseModel]]:
        uploaded_file = payload.context_snapshot.uploaded_files[0] if payload.context_snapshot.uploaded_files else None
        rewrite_context = payload.context_snapshot.rewrite_context
        if uploaded_file is not None:
            missing_rewrite_context = self._validate_rewrite_context(rewrite_context)
            if missing_rewrite_context is not None:
                return self._build_needs_input_plan(
                    run_id=run_id,
                    selected_skill=AgentSkill.REWRITE,
                    guard_summary=str(missing_rewrite_context["summary"]),
                    message=str(missing_rewrite_context["message"]),
                    missing_requirements=list(missing_rewrite_context["missing_requirements"]),
                )

            rewrite_response = await self._rewrite_task_executor(
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
            if not rewrite_response.success:
                if rewrite_response.error in {"REWRITE_NO_DOCUMENT", "REQ_MISSING_FIELD"}:
                    return self._build_needs_input_plan(
                        run_id=run_id,
                        selected_skill=AgentSkill.REWRITE,
                        guard_summary="当前会话缺少可执行上传文件 rewrite 的文档或表单上下文。",
                        message=rewrite_response.message
                        or "请先补全要重写的 Word 文件和当前页面上下文。",
                        missing_requirements=["uploaded_word_file", "rewrite_context"],
                    )
                raise RuntimeError(
                    rewrite_response.error
                    or rewrite_response.message
                    or "create_rewrite_task_tool failed"
                )

            return self._build_task_created_plan(
                run_id=run_id,
                selected_skill=AgentSkill.REWRITE,
                task_kind=rewrite_response.task_kind,
                task_id=rewrite_response.task_id,
                status=rewrite_response.status or TaskStatus.QUEUED,
                queue_position=rewrite_response.queue_position,
                waiting_count=rewrite_response.waiting_count,
                guard_summary="检测到当前会话已有上传文件和完整 rewrite 上下文。",
                tool_name=CREATE_REWRITE_TASK_TOOL,
                done_message="已为你创建 rewrite 任务。",
            )

        if not payload.context_snapshot.rewrite_available:
            return [
                (
                    "thinking_stage",
                    AgentThinkingStageEventData(
                        run_id=run_id,
                        stage="guard",
                        label="检查上下文",
                        status="completed",
                        summary="当前会话缺少可改写文档上下文。",
                        selected_skill=AgentSkill.REWRITE,
                        guard_result="needs_input",
                    ),
                ),
                (
                    "needs_input",
                    AgentNeedsInputEventData(
                        run_id=run_id,
                        message="当前会话没有可用文档，请先完成一次生成。",
                        selected_skill=AgentSkill.REWRITE,
                        missing_requirements=["rewrite_history"],
                    ),
                ),
            ]

        rewrite_response = await self._rewrite_task_executor(
            conversation_id=payload.conversation_id,
            user_prompt=payload.message,
            model=payload.model,
            rewrite_log_path=None,
        )
        if not rewrite_response.success:
            if rewrite_response.error == "REWRITE_NO_DOCUMENT":
                return [
                    (
                        "thinking_stage",
                        AgentThinkingStageEventData(
                            run_id=run_id,
                            stage="guard",
                            label="检查上下文",
                            status="completed",
                            summary="当前会话缺少可改写文档上下文。",
                            selected_skill=AgentSkill.REWRITE,
                            guard_result="needs_input",
                        ),
                    ),
                    (
                        "needs_input",
                        AgentNeedsInputEventData(
                            run_id=run_id,
                            message=rewrite_response.message or "当前会话没有可用文档，请先完成一次生成。",
                            selected_skill=AgentSkill.REWRITE,
                            missing_requirements=["rewrite_history"],
                        ),
                    ),
                ]
            raise RuntimeError(
                rewrite_response.error
                or rewrite_response.message
                or "create_rewrite_task_tool failed"
            )

        return self._build_task_created_plan(
            run_id=run_id,
            selected_skill=AgentSkill.REWRITE,
            task_kind=rewrite_response.task_kind,
            task_id=rewrite_response.task_id,
            status=rewrite_response.status or TaskStatus.QUEUED,
            queue_position=rewrite_response.queue_position,
            waiting_count=rewrite_response.waiting_count,
            guard_summary="检测到当前会话已有可改写文档。",
            tool_name=CREATE_REWRITE_TASK_TOOL,
            done_message="已为你创建 rewrite 任务。",
        )

    def _build_needs_input_plan(
        self,
        *,
        run_id: str,
        selected_skill: AgentSkill,
        guard_summary: str,
        message: str,
        missing_requirements: list[str],
    ) -> list[tuple[str, BaseModel]]:
        return [
            (
                "thinking_stage",
                AgentThinkingStageEventData(
                    run_id=run_id,
                    stage="guard",
                    label="检查上下文",
                    status="completed",
                    summary=guard_summary,
                    selected_skill=selected_skill,
                    guard_result="needs_input",
                ),
            ),
            (
                "needs_input",
                AgentNeedsInputEventData(
                    run_id=run_id,
                    message=message,
                    selected_skill=selected_skill,
                    missing_requirements=missing_requirements,
                ),
            ),
        ]

    def _validate_rewrite_context(
        self,
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

    def _build_task_created_plan(
        self,
        *,
        run_id: str,
        selected_skill: AgentSkill,
        task_kind: TaskKind,
        task_id: str,
        status: TaskStatus = TaskStatus.QUEUED,
        queue_position: int | None = None,
        waiting_count: int | None = None,
        guard_summary: str,
        tool_name: str,
        done_message: str,
    ) -> list[tuple[str, BaseModel]]:
        return [
            (
                "thinking_stage",
                AgentThinkingStageEventData(
                    run_id=run_id,
                    stage="guard",
                    label="检查上下文",
                    status="completed",
                    summary=guard_summary,
                    selected_skill=selected_skill,
                    guard_result="passed",
                ),
            ),
            (
                "tool_call",
                AgentToolCallEventData(
                    run_id=run_id,
                    tool_name=tool_name,
                    summary=f"已调用 {tool_name}。",
                    task_kind=task_kind,
                ),
            ),
            (
                "task_accepted",
                AgentTaskAcceptedEventData(
                    run_id=run_id,
                    task_id=task_id,
                    task_kind=task_kind,
                    status=status,
                    queue_position=queue_position if queue_position is not None else 0,
                    waiting_count=waiting_count if waiting_count is not None else 0,
                ),
            ),
            (
                "done",
                AgentRunDoneEventData(
                    run_id=run_id,
                    message=done_message,
                    task_id=task_id,
                    selected_skill=selected_skill,
                ),
            ),
        ]

    def _select_skill(self, payload: AgentRunStreamRequest) -> AgentSkill | None:
        if payload.selected_skills:
            return payload.selected_skills[0]

        normalized_message = payload.message.lower()
        if (
            payload.context_snapshot.uploaded_files
            or "rewrite" in normalized_message
            or "改写" in payload.message
            or "重写" in payload.message
            or "修改文件" in payload.message
        ):
            return AgentSkill.REWRITE
        return None

    def _build_understand_summary(
        self,
        message: str,
        selected_skill: AgentSkill | None,
    ) -> str:
        normalized_message = str(message or "").strip()
        if selected_skill == AgentSkill.REWRITE:
            return f"已识别为 rewrite 请求：{normalized_message}"
        return f"已收到用户消息，等待进一步确认任务能力：{normalized_message}"

    async def _is_disconnected(self, request: Any) -> bool:
        checker = getattr(request, "is_disconnected", None)
        if not callable(checker):
            return False
        result = checker()
        if asyncio.iscoroutine(result):
            return bool(await result)
        return bool(result)

    def _default_task_id_factory(self, skill: AgentSkill) -> str:
        return f"fake-{skill.value}-task-{uuid.uuid4().hex[:12]}"

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


_agent_run_service: AgentRunService | None = None


def get_agent_run_service() -> AgentRunService:
    """获取 agent run 服务单例。"""

    global _agent_run_service
    if _agent_run_service is None:
        _agent_run_service = AgentRunService()
    return _agent_run_service
