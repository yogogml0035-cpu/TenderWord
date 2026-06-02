"""Fake agent run runtime for the new task-context assistant stream."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any, Callable, Optional

from pydantic import BaseModel

from backend.models import (
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
    ) -> None:
        self._run_id_factory = run_id_factory or (
            lambda: f"run-{uuid.uuid4().hex}"
        )
        self._task_id_factory = task_id_factory or self._default_task_id_factory

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

        yield self._event_line(
            "run_started",
            AgentRunStartedEventData(
                run_id=run_id,
                conversation_id=payload.conversation_id,
                model=payload.model,
                selected_skills=payload.selected_skills,
            ),
        )

        try:
            for event_name, event_data in self._build_run_plan(
                run_id=run_id,
                payload=payload,
                selected_skill=selected_skill,
            ):
                if await self._is_disconnected(request):
                    return
                yield self._event_line(event_name, event_data)
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
            yield self._event_line(
                "error",
                AgentRunErrorEventData(
                    run_id=run_id,
                    code="AGENT_RUN_FAILED",
                    message="agent run 执行失败，请稍后重试",
                ),
            )

    def _build_run_plan(
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
            return plan + self._build_rewrite_plan(run_id=run_id, payload=payload)
        if selected_skill == AgentSkill.EDIT:
            return plan + self._build_edit_plan(run_id=run_id, payload=payload)

        plan.append(
            (
                "thinking_stage",
                AgentThinkingStageEventData(
                    run_id=run_id,
                    stage="guard",
                    label="检查上下文",
                    status="completed",
                    summary="fake runtime 暂时只支持 rewrite 或 edit 任务创建。",
                    guard_result="needs_input",
                ),
            )
        )
        plan.append(
            (
                "needs_input",
                AgentNeedsInputEventData(
                    run_id=run_id,
                    message="请说明这次要执行 rewrite 还是 edit。",
                    missing_requirements=["selected_skill"],
                ),
            )
        )
        return plan

    def _build_rewrite_plan(
        self,
        *,
        run_id: str,
        payload: AgentRunStreamRequest,
    ) -> list[tuple[str, BaseModel]]:
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

        task_id = self._task_id_factory(AgentSkill.REWRITE)
        return self._build_task_created_plan(
            run_id=run_id,
            selected_skill=AgentSkill.REWRITE,
            task_kind=TaskKind.REWRITE,
            task_id=task_id,
            guard_summary="检测到当前会话已有可改写文档。",
            tool_name="create_rewrite_task_tool",
            done_message="已为你创建 rewrite 任务。",
        )

    def _build_edit_plan(
        self,
        *,
        run_id: str,
        payload: AgentRunStreamRequest,
    ) -> list[tuple[str, BaseModel]]:
        if not payload.context_snapshot.uploaded_files:
            return [
                (
                    "thinking_stage",
                    AgentThinkingStageEventData(
                        run_id=run_id,
                        stage="guard",
                        label="检查上下文",
                        status="completed",
                        summary="当前会话还没有可编辑的上传 Word 文件。",
                        selected_skill=AgentSkill.EDIT,
                        guard_result="needs_input",
                    ),
                ),
                (
                    "needs_input",
                    AgentNeedsInputEventData(
                        run_id=run_id,
                        message="请先上传要修改的 Word 文件。",
                        selected_skill=AgentSkill.EDIT,
                        missing_requirements=["uploaded_word_file"],
                    ),
                ),
            ]

        task_id = self._task_id_factory(AgentSkill.EDIT)
        return self._build_task_created_plan(
            run_id=run_id,
            selected_skill=AgentSkill.EDIT,
            task_kind=TaskKind.EDIT,
            task_id=task_id,
            guard_summary="检测到当前会话已有上传文件，可创建 edit 任务。",
            tool_name="create_edit_task_tool",
            done_message="已为你创建 edit 任务。",
        )

    def _build_task_created_plan(
        self,
        *,
        run_id: str,
        selected_skill: AgentSkill,
        task_kind: TaskKind,
        task_id: str,
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
                    summary=f"fake runtime 已调用 {tool_name}。",
                    task_kind=task_kind,
                ),
            ),
            (
                "task_accepted",
                AgentTaskAcceptedEventData(
                    run_id=run_id,
                    task_id=task_id,
                    task_kind=task_kind,
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
        if "rewrite" in normalized_message or "改写" in payload.message:
            return AgentSkill.REWRITE
        if "edit" in normalized_message or "修改文件" in payload.message:
            return AgentSkill.EDIT
        return None

    def _build_understand_summary(
        self,
        message: str,
        selected_skill: AgentSkill | None,
    ) -> str:
        normalized_message = str(message or "").strip()
        if selected_skill == AgentSkill.REWRITE:
            return f"已识别为 rewrite 请求：{normalized_message}"
        if selected_skill == AgentSkill.EDIT:
            return f"已识别为 edit 请求：{normalized_message}"
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

    def _event_line(self, event_name: str, payload: BaseModel) -> str:
        return to_ndjson_line(event_name, payload.model_dump(mode="json"))


_agent_run_service: AgentRunService | None = None


def get_agent_run_service() -> AgentRunService:
    """获取 agent run 服务单例。"""

    global _agent_run_service
    if _agent_run_service is None:
        _agent_run_service = AgentRunService()
    return _agent_run_service
