"""文档生成服务模块.

封装文档生成的业务逻辑，集成 LangGraph 工作流。
"""

from __future__ import annotations

import asyncio
import copy
import logging
import pathlib
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Union

from backend.models import (
    AgentStepEventData,
    CommentSupplementRequest,
    DoneEventData,
    ErrorEventData,
    FormType,
    GenerateRequest,
    GenerateResponse,
    InsertionConfig,
    LLMEventData,
    LogEventData,
    ProgressEventData,
    SSEEvent,
    SSEEventType,
    TenderData,
)
from backend.helper.word_helper.inline_style_ops import (
    build_style_writeback_summary_payload,
)
from backend.nodes.common_word_nodes.comment_writeback import (
    build_comment_writeback_summary_payload,
)
from backend.services.conversation_service import get_conversation_service
from backend.task.task_queue_manager import get_task_queue
from backend.util.log_util.execution_log import log_generate_task_success
from backend.util.log_util.progress_log import progress_log
from backend.util.log_util.skill_audit_log import create_rewrite_audit_log
from backend.util.log_util.sse_log_handler import task_log_context
from backend.util.common_util.tender_number import normalize_gjgk_project_number
from backend.config.tender_config import get_default_anchor_texts

if TYPE_CHECKING:
    from backend.graphs.base_graph import BaseGraph

logger = logging.getLogger(__name__)

# 线程池执行器
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="doc_gen_")


LLM_SNAPSHOT_INTERVAL_SECONDS = 0.25

REWRITE_STATE_KEYS = [
    "tender_type",
    "prepared_doc_path",
    "source_document_path",
    "polished_text",
    "tender_params",
    "insertion_before_text",
    "insertion_after_text",
    "project_name",
    "project_number",
    "project_content",
    "buyer_name",
    "investment",
    "bzj_rule",
    "project_zbr_xbr",
    "zbr_xbr_tel",
    "zbr_pinyin",
    "shell_start_date",
    "shell_end_date",
    "submit_date",
    "platform",
    "service_fee",
    "tender_lx",
    "fund_source_lx",
    "tender_invitation",
    "delivery_location",
]

REWRITE_DEFAULT_ANCHORS = {
    "xjcg": ("第三章  采购需求", "第四章  响应文件有关格式"),
    "gngk": ("第三章 招标内容及要求", "第四章 投标文件有关格式"),
    "gngk_hw_zc": ("第三章 招标内容及要求", "第四章 投标文件有关格式"),
    "gngk_fw_zc": ("第三章 招标内容及要求", "第四章 投标文件有关格式"),
    "gngk_hw_cz": ("第四章  招标需求", "第五章  评标方法与程序"),
    "gngk_fw_cz": ("第三章 招标内容及要求", "第四章 投标文件有关格式"),
    "gngk_zc": ("第三章 招标内容及要求", "第四章 投标文件有关格式"),
    "gngk_cz": ("第四章  招标需求", "第五章  评标方法与程序"),
    "gjgk": ("技术规格及要求", "附件1：投标文件封面（格式）"),
}

TASK_KIND_TO_LLM_NODE = {
    "generate": "generate_polished_text",
    "rewrite": "rewrite_text",
    "comment_supplement": "comment_agent",
}

class _DiscardingWriter:
    """吞掉 Graph 运行期间的 stdout/stderr，避免污染 execution_log。"""

    def write(self, data: str) -> int:
        return len(data or "")

    def flush(self) -> None:
        return None


class _LLMSnapshotRelay:
    """按节流窗口转发全文快照形式的 LLM 输出。"""

    def __init__(
        self,
        task_id: str,
        model_provider: str,
        callback: "SSECallback",
        sse_manager: Optional[Any],
        node: str = "generate_polished_text",
        min_interval_seconds: float = LLM_SNAPSHOT_INTERVAL_SECONDS,
    ):
        self.task_id = task_id
        self.model_provider = model_provider
        self.callback = callback
        self.sse_manager = sse_manager
        self.node = node
        self.min_interval_seconds = min_interval_seconds
        self._latest_content = ""
        self._last_sent_content = ""
        self._last_sent_at = 0.0
        self._completed_content = ""

    def on_snapshot(self, content: str) -> None:
        snapshot = str(content or "")
        if not snapshot:
            return

        self._latest_content = snapshot
        now = time.monotonic()
        if now - self._last_sent_at < self.min_interval_seconds:
            return
        if snapshot == self._last_sent_content:
            return
        self._emit(snapshot, is_complete=False)

    def flush(self, final_content: Optional[str] = None) -> None:
        if final_content is not None:
            self._latest_content = str(final_content or "")
        if not self._latest_content:
            return
        if self._completed_content and self._completed_content == self._latest_content:
            return
        self._emit(self._latest_content, is_complete=True)

    def _emit(self, content: str, is_complete: bool) -> None:
        self.callback.push_llm(
            content=content,
            node=self.node,
            model=self.model_provider,
            is_complete=is_complete,
        )
        if self.sse_manager is not None:
            try:
                self.sse_manager.send_llm_output_threadsafe(
                    task_id=self.task_id,
                    content=content,
                    node=self.node,
                    model=self.model_provider,
                    is_complete=is_complete,
                )
            except Exception:
                pass

        self._last_sent_content = content
        self._last_sent_at = time.monotonic()
        if is_complete:
            self._completed_content = content


# Graph 注册表：表单类型 -> Graph 类
GRAPH_REGISTRY: Dict[str, type] = {}
TASK_SKILL_GRAPH_CLASSES: Dict[str, type] = {}
REWRITE_SKILL_ID = "rewrite"
REWRITE_SKILL_GRAPH_CLASS: Optional[type] = None
COMMENT_SUPPLEMENT_GRAPH_CLASS: Optional[type] = None


def _init_graph_registry():
    """初始化 Graph 注册表（延迟加载）."""
    global GRAPH_REGISTRY, TASK_SKILL_GRAPH_CLASSES, REWRITE_SKILL_GRAPH_CLASS, COMMENT_SUPPLEMENT_GRAPH_CLASS
    if (
        GRAPH_REGISTRY
        and REWRITE_SKILL_GRAPH_CLASS is not None
        and COMMENT_SUPPLEMENT_GRAPH_CLASS is not None
    ):
        return

    try:
        from backend.graphs import (
            CommentSupplementGraph,
            GjgkTenderGraph,
            GngkFwCzTenderGraph,
            GngkFwZcTenderGraph,
            GngkHwCzTenderGraph,
            GngkHwZcTenderGraph,
            SkillGraph,
            XjcgTenderGraph,
        )

        GRAPH_REGISTRY["xjcg_tender"] = XjcgTenderGraph
        GRAPH_REGISTRY["gngk_hw_zc_tender"] = GngkHwZcTenderGraph
        GRAPH_REGISTRY["gngk_hw_cz_tender"] = GngkHwCzTenderGraph
        GRAPH_REGISTRY["gngk_fw_zc_tender"] = GngkFwZcTenderGraph
        GRAPH_REGISTRY["gngk_fw_cz_tender"] = GngkFwCzTenderGraph
        GRAPH_REGISTRY["gjgk_tender"] = GjgkTenderGraph
        TASK_SKILL_GRAPH_CLASSES[REWRITE_SKILL_ID] = SkillGraph.for_skill(REWRITE_SKILL_ID)
        REWRITE_SKILL_GRAPH_CLASS = TASK_SKILL_GRAPH_CLASSES[REWRITE_SKILL_ID]
        COMMENT_SUPPLEMENT_GRAPH_CLASS = CommentSupplementGraph
        logger.info("Graph 注册表初始化完成")
    except ImportError as e:
        logger.error(f"初始化 Graph 注册表失败: {e}")


class SSECallback:
    """SSE 回调管理器.

    用于收集 Graph 执行过程中的事件，供 SSE 流式输出使用。
    """

    def __init__(self, task_id: str):
        """初始化 SSE 回调.

        Args:
            task_id: 任务ID
        """
        self.task_id = task_id
        self._events: List[SSEEvent] = []
        self._lock = threading.Lock()
        self._done = False
        try:
            from backend.core.sse_manager import sse_manager
        except Exception:  # pragma: no cover
            sse_manager = None
        self._sse_manager = sse_manager

    def push_event(self, event: SSEEvent) -> None:
        """推送事件.

        Args:
            event: SSE 事件
        """
        with self._lock:
            self._events.append(event)

    def push_log(
        self, message: str, level: str = "info", node: Optional[str] = None
    ) -> None:
        """推送日志事件.

        Args:
            message: 日志消息
            level: 日志级别
            node: 当前节点名称
        """
        event = SSEEvent(
            event=SSEEventType.LOG,
            data=LogEventData(
                level=level,
                message=message,
                node=node,
            ).model_dump(),
        )
        self.push_event(event)

    def push_llm(
        self,
        content: str,
        node: Optional[str] = None,
        model: Optional[str] = None,
        is_complete: bool = False,
    ) -> None:
        """推送 LLM 输出事件.

        Args:
            content: LLM 输出内容
            node: 当前节点名称
            model: 使用的模型
            is_complete: 是否完成
        """
        event = SSEEvent(
            event=SSEEventType.LLM,
            data=LLMEventData(
                content=content,
                node=node,
                model=model,
                is_complete=is_complete,
                task_id=self.task_id,
            ).model_dump(),
        )
        self.push_event(event)

    def push_progress(self, progress_data: ProgressEventData) -> None:
        """推送进度事件.

        Args:
            progress_data: 进度数据
        """
        event = SSEEvent(
            event=SSEEventType.PROGRESS,
            data=progress_data.model_dump(),
        )
        self.push_event(event)

    def push_agent_step(self, agent_step_data: AgentStepEventData) -> None:
        """推送智能体步骤事件."""
        event = SSEEvent(
            event=SSEEventType.AGENT_STEP,
            data=agent_step_data.model_dump(mode="json"),
        )
        self.push_event(event)
        if self._sse_manager is not None:
            try:
                if getattr(self._sse_manager, "_loop", None) is None:
                    return
                self._sse_manager.send_agent_step_threadsafe(
                    task_id=agent_step_data.task_id,
                    task_kind=agent_step_data.task_kind,
                    step_type=agent_step_data.step_type,
                    round=agent_step_data.round,
                    node=agent_step_data.node,
                    content=agent_step_data.content,
                    findings=[
                        finding.model_dump(mode="json")
                        for finding in agent_step_data.findings
                    ],
                    content_agent=(
                        agent_step_data.content_agent.model_dump(mode="json")
                        if agent_step_data.content_agent is not None
                        else None
                    ),
                    comment_agent=(
                        agent_step_data.comment_agent.model_dump(mode="json")
                        if agent_step_data.comment_agent is not None
                        else None
                    ),
                    is_complete=agent_step_data.is_complete,
                )
            except Exception:
                pass

    def push_done(self, done_data: DoneEventData) -> None:
        """推送完成事件.

        Args:
            done_data: 完成数据
        """
        event = SSEEvent(
            event=SSEEventType.DONE,
            data=done_data.model_dump(),
        )
        self.push_event(event)
        self._done = True

    def push_error(self, error_data: ErrorEventData) -> None:
        """推送错误事件.

        Args:
            error_data: 错误数据
        """
        event = SSEEvent(
            event=SSEEventType.ERROR,
            data=error_data.model_dump(),
        )
        self.push_event(event)
        self._done = True

    def get_events(self) -> List[SSEEvent]:
        """获取所有事件.

        Returns:
            事件列表
        """
        with self._lock:
            return list(self._events)

    def is_done(self) -> bool:
        """检查是否完成.

        Returns:
            是否完成
        """
        return self._done


class DocumentService:
    """文档生成服务.

    封装文档生成的业务逻辑，包括：
    - 任务创建
    - Graph 执行
    - SSE 事件推送
    """

    def __init__(self):
        """初始化文档生成服务."""
        _init_graph_registry()
        self._task_queue = get_task_queue()
        self._conversation_service = get_conversation_service()
        # 任务ID -> SSE 回调的映射
        self._callbacks: Dict[str, SSECallback] = {}
        self._callbacks_lock = threading.Lock()

    def get_callback(self, task_id: str) -> Optional[SSECallback]:
        """获取任务的 SSE 回调.

        Args:
            task_id: 任务ID

        Returns:
            SSE 回调或 None
        """
        with self._callbacks_lock:
            return self._callbacks.get(task_id)

    def create_task(self, request: GenerateRequest) -> GenerateResponse:
        """创建文档生成任务.

        Args:
            request: 生成请求

        Returns:
            生成响应（包含 task_id）
        """
        task_id, callback = self._allocate_task_callback_pair()
        form_type = request.form_type.value
        graph_class = GRAPH_REGISTRY.get(form_type)

        if not graph_class:
            logger.error(f"未知的表单类型: {form_type}")
            return GenerateResponse(
                success=False,
                task_id=task_id,
                message=f"未知的表单类型: {form_type}",
                error=f"Form type '{form_type}' not supported",
            )

        initial_state = self._build_initial_state(request, task_id=task_id)
        return self._submit_graph_task(
            task_id=task_id,
            graph_class=graph_class,
            initial_state=initial_state,
            callback=callback,
            model_provider=request.model.value,
            task_kind="generate",
            conversation_id=initial_state.get("conversation_id"),
            llm_node_name=TASK_KIND_TO_LLM_NODE["generate"],
        )

    async def create_rewrite_task(
        self,
        *,
        conversation_id: str,
        user_prompt: str,
        model_provider: str,
        rewrite_log_path: Optional[str] = None,
        file_path: Optional[str] = None,
        form_type: Optional[FormType] = None,
        insertion_config: Optional[InsertionConfig] = None,
        tender_lx: Optional[int] = None,
        fund_source_lx: Optional[int] = None,
        tender_data_snapshot: Optional[TenderData] = None,
    ) -> GenerateResponse:
        """创建 rewrite 任务（复用文档任务队列 + SSE 三卡片链路）。"""
        normalized_conversation_id = str(conversation_id or "").strip()
        normalized_prompt = str(user_prompt or "").strip()
        normalized_file_path = str(file_path or "").strip()

        task_id, callback = self._allocate_task_callback_pair()
        if not normalized_conversation_id:
            return GenerateResponse(
                success=False,
                task_id=task_id,
                message="conversation_id 不能为空",
                error="REQ_MISSING_FIELD",
            )

        if not normalized_prompt:
            return GenerateResponse(
                success=False,
                task_id=task_id,
                message="修改指令不能为空",
                error="REQ_MISSING_FIELD",
            )

        if not REWRITE_SKILL_GRAPH_CLASS:
            return GenerateResponse(
                success=False,
                task_id=task_id,
                message="Rewrite Skill Graph 未初始化",
                error="REWRITE_TARGET_NOT_RESOLVED",
            )

        if normalized_file_path:
            missing_fields: list[str] = []
            if form_type is None:
                missing_fields.append("form_type")
            if insertion_config is None:
                missing_fields.append("insertion_config")
            else:
                before_text = str(insertion_config.before_text or "").strip()
                after_text = str(insertion_config.after_text or "").strip()
                if not before_text or not after_text:
                    missing_fields.append("insertion_config")
            if tender_lx is None:
                missing_fields.append("tender_lx")
            if fund_source_lx is None:
                missing_fields.append("fund_source_lx")
            if missing_fields:
                return GenerateResponse(
                    success=False,
                    task_id=task_id,
                    message="上传文件重写缺少当前页面上下文",
                    error="REQ_MISSING_FIELD",
                )

            rewrite_initial_state = self._build_uploaded_rewrite_initial_state(
                task_id=task_id,
                conversation_id=normalized_conversation_id,
                user_prompt=normalized_prompt,
                file_path=normalized_file_path,
                form_type=form_type,
                insertion_config=insertion_config,
                tender_lx=int(tender_lx),
                fund_source_lx=int(fund_source_lx),
                tender_data_snapshot=tender_data_snapshot,
            )
        else:
            if not self._conversation_service.has_rewrite_history(normalized_conversation_id):
                return GenerateResponse(
                    success=False,
                    task_id=task_id,
                    message="当前会话没有可用文档，请先完成一次生成",
                    error="REWRITE_NO_DOCUMENT",
                )

            latest_rewrite_state = self._conversation_service.get_latest_rewrite_state(
                normalized_conversation_id
            )
            if not latest_rewrite_state:
                return GenerateResponse(
                    success=False,
                    task_id=task_id,
                    message="当前会话没有可用文档，请先完成一次生成",
                    error="REWRITE_NO_DOCUMENT",
                )

            rewrite_initial_state = self._build_skill_graph_initial_state(
                task_id=task_id,
                skill_id=REWRITE_SKILL_ID,
                conversation_id=normalized_conversation_id,
                user_prompt=normalized_prompt,
                latest_rewrite_state=latest_rewrite_state,
            )

        task_audit_log_path = str(rewrite_log_path or "").strip() or None
        if task_audit_log_path is None and normalized_file_path:
            try:
                task_audit_log_path = create_rewrite_audit_log(task_id)
            except Exception:
                logger.exception(
                    "创建 rewrite audit 日志文件失败: task_id=%s",
                    task_id,
                )

        return self._submit_graph_task(
            task_id=task_id,
            graph_class=REWRITE_SKILL_GRAPH_CLASS,
            initial_state=rewrite_initial_state,
            callback=callback,
            model_provider=model_provider,
            task_kind="rewrite",
            conversation_id=normalized_conversation_id,
            task_user_prompt=normalized_prompt,
            task_audit_log_path=task_audit_log_path,
            rewrite_log_path=task_audit_log_path,
            llm_node_name=TASK_KIND_TO_LLM_NODE["rewrite"],
        )

    async def create_comment_supplement_task(
        self,
        request: CommentSupplementRequest,
    ) -> GenerateResponse:
        """创建独立补充批注任务。"""
        task_id, callback = self._allocate_task_callback_pair()

        normalized_conversation_id = str(request.conversation_id or "").strip()
        normalized_source_file = str(request.source_file or "").strip()
        if not normalized_conversation_id:
            return GenerateResponse(
                success=False,
                task_id=task_id,
                message="conversation_id 不能为空",
                error="REQ_MISSING_FIELD",
            )
        if not normalized_source_file:
            return GenerateResponse(
                success=False,
                task_id=task_id,
                message="source_file 不能为空",
                error="REQ_MISSING_FIELD",
            )

        latest_rewrite_state = self._conversation_service.get_latest_rewrite_state(
            normalized_conversation_id
        )
        if not latest_rewrite_state:
            return GenerateResponse(
                success=False,
                task_id=task_id,
                message="当前会话没有可补充批注的文档，请先完成一次生成",
                error="COMMENT_SUPPLEMENT_NO_DOCUMENT",
            )

        polished_text = str(latest_rewrite_state.get("polished_text") or "").strip()
        if not polished_text:
            return GenerateResponse(
                success=False,
                task_id=task_id,
                message="当前会话缺少可用于补充批注的正文上下文",
                error="COMMENT_SUPPLEMENT_MISSING_CONTEXT",
            )

        latest_prepared_doc_path = str(
            latest_rewrite_state.get("prepared_doc_path") or ""
        ).strip()
        if not latest_prepared_doc_path:
            return GenerateResponse(
                success=False,
                task_id=task_id,
                message="当前会话缺少最新 Word 文件路径",
                error="COMMENT_SUPPLEMENT_NO_DOCUMENT",
            )

        source_path = pathlib.Path(normalized_source_file).expanduser()
        latest_path = pathlib.Path(latest_prepared_doc_path).expanduser()
        if not source_path.is_file():
            return GenerateResponse(
                success=False,
                task_id=task_id,
                message="当前文件不存在，无法补充批注",
                error="COMMENT_SUPPLEMENT_SOURCE_NOT_FOUND",
            )
        if not latest_path.is_file():
            return GenerateResponse(
                success=False,
                task_id=task_id,
                message="会话最新文件不存在，无法补充批注",
                error="COMMENT_SUPPLEMENT_SOURCE_NOT_FOUND",
            )

        resolved_source = source_path.resolve()
        resolved_latest = latest_path.resolve()
        if str(resolved_source).casefold() != str(resolved_latest).casefold():
            return GenerateResponse(
                success=False,
                task_id=task_id,
                message="当前文件不是会话最新文件，请刷新后重试",
                error="COMMENT_SUPPLEMENT_SOURCE_MISMATCH",
            )

        if COMMENT_SUPPLEMENT_GRAPH_CLASS is None:
            return GenerateResponse(
                success=False,
                task_id=task_id,
                message="CommentSupplement Graph 未初始化",
                error="COMMENT_SUPPLEMENT_TARGET_NOT_RESOLVED",
            )

        initial_state = self._build_comment_supplement_initial_state(
            task_id=task_id,
            conversation_id=normalized_conversation_id,
            latest_rewrite_state=latest_rewrite_state,
            source_file=str(resolved_source),
        )

        return self._submit_graph_task(
            task_id=task_id,
            graph_class=COMMENT_SUPPLEMENT_GRAPH_CLASS,
            initial_state=initial_state,
            callback=callback,
            model_provider=request.model.value,
            task_kind="comment_supplement",
            conversation_id=normalized_conversation_id,
            llm_node_name=TASK_KIND_TO_LLM_NODE["comment_supplement"],
        )

    def _allocate_task_callback_pair(self) -> tuple[str, SSECallback]:
        task_id = f"task-{uuid.uuid4().hex[:8]}-{uuid.uuid4().hex[:4]}"
        callback = SSECallback(task_id)
        with self._callbacks_lock:
            self._callbacks[task_id] = callback
        return task_id, callback

    def _submit_graph_task(
        self,
        *,
        task_id: str,
        graph_class: type,
        initial_state: Dict[str, Any],
        callback: SSECallback,
        model_provider: str,
        task_kind: str,
        conversation_id: Optional[str] = None,
        task_user_prompt: Optional[str] = None,
        task_audit_log_path: Optional[str] = None,
        rewrite_log_path: Optional[str] = None,
        llm_node_name: Optional[str] = None,
    ) -> GenerateResponse:
        self._task_queue.add_task(
            task_id=task_id,
            user_session_id=str(initial_state.get("user_session_id") or ""),
            task_kind=task_kind,
        )

        future = _executor.submit(
            self._run_graph,
            task_id,
            graph_class,
            initial_state,
            callback,
            model_provider,
            task_kind,
            conversation_id,
            task_user_prompt,
            task_audit_log_path,
            rewrite_log_path,
            llm_node_name,
        )
        self._task_queue.register_worker_future(task_id, future)

        logger.info(
            "创建文档任务: task_id=%s, task_kind=%s, tender_type=%s",
            task_id,
            task_kind,
            initial_state.get("tender_type"),
        )

        task_snapshot = self._task_queue.get_task(task_id)
        task_status = task_snapshot.status.value if task_snapshot else None
        queue_position = self._task_queue.get_queue_position(task_id)
        waiting_count = self._task_queue.get_waiting_count(task_id)

        return GenerateResponse(
            success=True,
            task_id=task_id,
            message="任务已创建，正在后台执行",
            task_kind=task_kind,
            status=task_status,
            queue_position=queue_position,
            waiting_count=waiting_count,
        )

    def _build_skill_graph_initial_state(
        self,
        *,
        task_id: str,
        skill_id: str,
        conversation_id: str,
        user_prompt: str,
        latest_rewrite_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        initial_state = {
            "task_id": task_id,
            "skill_id": skill_id,
            "conversation_id": conversation_id,
            "user_session_id": conversation_id,
            "rewrite_user_prompt": user_prompt,
            "rewrite_mode": True,
        }
        if latest_rewrite_state is not None and "source_document_path" in latest_rewrite_state:
            initial_state["source_document_path"] = str(
                latest_rewrite_state.get("source_document_path") or ""
            ).strip()
        return initial_state

    def _build_uploaded_rewrite_initial_state(
        self,
        *,
        task_id: str,
        conversation_id: str,
        user_prompt: str,
        file_path: str,
        form_type: FormType,
        insertion_config: InsertionConfig,
        tender_lx: int,
        fund_source_lx: int,
        tender_data_snapshot: Optional[TenderData],
    ) -> Dict[str, Any]:
        tender_type = form_type.value.replace("_tender", "")
        tender_data = tender_data_snapshot
        normalized_conversation_id = str(conversation_id).strip()
        project_number = str(getattr(tender_data, "project_number", "") or "").strip()
        if tender_type == "gjgk":
            project_number = normalize_gjgk_project_number(project_number)

        insertion_before_text = None
        insertion_after_text = None
        if insertion_config:
            insertion_before_text = getattr(insertion_config, "before_text", None)
            insertion_after_text = getattr(insertion_config, "after_text", None)

        default_before_text, default_after_text = get_default_anchor_texts(tender_type)
        if not insertion_before_text or not str(insertion_before_text).strip():
            insertion_before_text = default_before_text
        if not insertion_after_text or not str(insertion_after_text).strip():
            insertion_after_text = default_after_text

        state: Dict[str, Any] = {
            "task_id": task_id,
            "skill_id": REWRITE_SKILL_ID,
            "conversation_id": normalized_conversation_id,
            "user_session_id": normalized_conversation_id,
            "tender_type": tender_type,
            "project_name": str(getattr(tender_data, "project_name", "") or "").strip(),
            "project_number": project_number,
            "project_content": str(getattr(tender_data, "project_content", "") or "").strip(),
            "buyer_name": str(getattr(tender_data, "buyer_name", "") or "").strip(),
            "investment": str(getattr(tender_data, "investment", "") or "").strip(),
            "bzj_rule": str(getattr(tender_data, "bzj_rule", "") or "").strip(),
            "project_zbr_xbr": str(getattr(tender_data, "project_zbr_xbr", "") or "").strip(),
            "zbr_xbr_tel": str(getattr(tender_data, "zbr_xbr_tel", "") or "").strip(),
            "zbr_pinyin": str(getattr(tender_data, "zbr_pinyin", "") or "").strip(),
            "shell_start_date": str(getattr(tender_data, "shell_start_date", "") or "").strip(),
            "shell_end_date": str(getattr(tender_data, "shell_end_date", "") or "").strip(),
            "submit_date": str(getattr(tender_data, "submit_date", "") or "").strip(),
            "platform": str(getattr(tender_data, "platform", "") or "").strip(),
            "service_fee": str(getattr(tender_data, "service_fee", "") or "").strip(),
            "tender_lx": int(tender_lx),
            "fund_source_lx": str(fund_source_lx),
            "rewrite_user_prompt": str(user_prompt).strip(),
            "source_document_path": str(file_path).strip(),
            "rewrite_source": "uploaded_file",
            "rewrite_mode": True,
            "insertion_before_text": str(insertion_before_text),
            "insertion_after_text": str(insertion_after_text),
        }
        if tender_type == "gjgk":
            state["tender_invitation"] = (
                f"项目名称：{state['project_name']}，招标编号：{state['project_number']}"
            )
        return state

    def _build_comment_supplement_initial_state(
        self,
        *,
        task_id: str,
        conversation_id: str,
        latest_rewrite_state: Dict[str, Any],
        source_file: str,
    ) -> Dict[str, Any]:
        state: Dict[str, Any] = {}
        for key, value in latest_rewrite_state.items():
            if isinstance(value, (str, int)):
                state[key] = value
            elif isinstance(value, list):
                state[key] = copy.deepcopy(value)

        state.update(
            {
                "task_id": task_id,
                "conversation_id": conversation_id,
                "user_session_id": conversation_id,
                "task_kind": "comment_supplement",
                "comment_supplement_source_file": source_file,
                "source_prepared_doc_path": source_file,
                "prepared_doc_path": source_file,
                "source_document_path": source_file,
                "polished_text": str(latest_rewrite_state.get("polished_text") or ""),
            }
        )

        tender_type = str(
            state.get("tender_type") or latest_rewrite_state.get("tender_type") or "xjcg"
        ).strip()
        state["tender_type"] = tender_type or "xjcg"
        if not state.get("insertion_before_text") or not state.get("insertion_after_text"):
            default_before, default_after = REWRITE_DEFAULT_ANCHORS.get(
                state["tender_type"],
                REWRITE_DEFAULT_ANCHORS["xjcg"],
            )
            if not state.get("insertion_before_text"):
                state["insertion_before_text"] = default_before
            if not state.get("insertion_after_text"):
                state["insertion_after_text"] = default_after
        return state

    def _build_initial_state(self, request: GenerateRequest, task_id: str) -> Dict[str, Any]:
        """构建 Graph 初始状态.

        Args:
            request: 生成请求

        Returns:
            初始状态字典
        """
        tender_data = request.tender_data
        file_paths = request.file_paths

        # 构建状态
        tender_type = request.form_type.value.replace("_tender", "")
        conversation_id = str(getattr(request, "conversation_id", "") or "").strip()
        generation_style = getattr(request, "generation_style", "template")
        if hasattr(generation_style, "value"):
            generation_style = generation_style.value
        generation_mode = getattr(request, "generation_mode", "workflow")
        if hasattr(generation_mode, "value"):
            generation_mode = generation_mode.value
        comment_generation_mode = getattr(request, "comment_generation_mode", "on")
        if hasattr(comment_generation_mode, "value"):
            comment_generation_mode = comment_generation_mode.value
        style_writeback_mode = getattr(request, "style_writeback_mode", "full")
        if hasattr(style_writeback_mode, "value"):
            style_writeback_mode = style_writeback_mode.value
        project_number = tender_data.project_number or ""
        if tender_type == "gjgk":
            project_number = normalize_gjgk_project_number(project_number)
        state: Dict[str, Any] = {
            # 与队列任务ID保持一致，确保进度、取消、日志链路统一
            "task_id": task_id,
            "conversation_id": conversation_id,
            "user_session_id": conversation_id,
            "tender_type": tender_type,
            "generation_style": str(generation_style or "template"),
            "generation_mode": str(generation_mode or "workflow"),
            "comment_generation_mode": str(comment_generation_mode or "on"),
            "style_writeback_mode": str(style_writeback_mode or "full"),
            # 项目信息
            "project_name": tender_data.project_name or "",
            "project_number": project_number,
            "project_content": tender_data.project_content or "",
            "buyer_name": tender_data.buyer_name or "",
            "investment": tender_data.investment or "",
            "bzj_rule": tender_data.bzj_rule or "",
            "project_zbr_xbr": tender_data.project_zbr_xbr or "",
            "zbr_xbr_tel": tender_data.zbr_xbr_tel or "",
            "zbr_pinyin": tender_data.zbr_pinyin or "",
            "shell_start_date": tender_data.shell_start_date or "",
            "shell_end_date": tender_data.shell_end_date or "",
            "submit_date": tender_data.submit_date or "",
            "platform": tender_data.platform or "",
            "service_fee": tender_data.service_fee or "",
        }
        fund_source_lx = getattr(tender_data, "fund_source_lx", None)
        if fund_source_lx not in (None, ""):
            state["fund_source_lx"] = str(fund_source_lx)
        tender_lx = getattr(tender_data, "tender_lx", None)
        if tender_lx in (0, 1, 2):
            state["tender_lx"] = int(tender_lx)

        insertion_before_text = None
        insertion_after_text = None
        insertion_config = getattr(request, "insertion_config", None)
        if insertion_config:
            insertion_before_text = getattr(insertion_config, "before_text", None)
            insertion_after_text = getattr(insertion_config, "after_text", None)

        default_before_text, default_after_text = get_default_anchor_texts(tender_type)
        if not insertion_before_text or not str(insertion_before_text).strip():
            insertion_before_text = default_before_text
        if not insertion_after_text or not str(insertion_after_text).strip():
            insertion_after_text = default_after_text

        state["insertion_before_text"] = str(insertion_before_text)
        state["insertion_after_text"] = str(insertion_after_text)
        if tender_type == "gjgk":
            state["tender_invitation"] = (
                f"项目名称：{state['project_name']}，招标编号：{state['project_number']}"
            )

        # 文件路径
        state["template_path"] = file_paths.template
        state["tender_param_paths"] = list(file_paths.tender_params)

        return state

    def _run_graph(
        self,
        task_id: str,
        graph_class: type,
        initial_state: Dict[str, Any],
        callback: SSECallback,
        model_provider: str,
        task_kind: str = "generate",
        conversation_id: Optional[str] = None,
        task_user_prompt: Optional[str] = None,
        task_audit_log_path: Optional[str] = None,
        rewrite_log_path: Optional[str] = None,
        llm_node_name: Optional[str] = None,
    ) -> None:
        """在后台线程中执行 Graph.

        Args:
            task_id: 任务ID
            graph_class: Graph 类
            initial_state: 初始状态
            callback: SSE 回调
            model_provider: 模型提供商
            task_kind: 任务类别（generate | rewrite）
            conversation_id: 会话ID
            task_user_prompt: task 用户指令
        """
        import asyncio

        task_label = {
            "generate": "文档生成任务",
            "rewrite": "修改任务",
            "comment_supplement": "补充批注任务",
        }.get(task_kind, "文档任务")
        success_message = {
            "generate": "文档生成完成",
            "rewrite": "修改任务完成",
            "comment_supplement": "补充批注完成",
        }.get(task_kind, "任务完成")
        callback.push_log(f"开始执行{task_label}: {task_id}")
        progress_log.info(f"[Task] 开始执行任务: {task_id}")
        stdout_writer = _DiscardingWriter()
        stderr_writer = _DiscardingWriter()
        rewrite_cleanup_holder: Dict[str, str] = {}

        try:
            # 创建 Graph 实例
            graph_instance: BaseGraph = graph_class()
            try:
                total_nodes = graph_instance.estimate_total_nodes(initial_state)
                self._task_queue.set_total_nodes(task_id, total_nodes)
            except Exception:
                # 总步数估算失败不影响主流程，回退默认值
                pass
            compiled_graph = graph_instance.compile()

            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                with task_log_context(task_id):
                    # 执行 Graph
                    result_state, elapsed_time = loop.run_until_complete(
                        self._invoke_graph_async(
                            compiled_graph,
                            initial_state,
                            task_id,
                            callback,
                            model_provider,
                            task_kind=task_kind,
                            llm_node_name=llm_node_name or TASK_KIND_TO_LLM_NODE.get(task_kind, "generate_polished_text"),
                            task_audit_log_path=task_audit_log_path,
                            rewrite_log_path=rewrite_log_path,
                            rewrite_cleanup_holder=rewrite_cleanup_holder,
                            stdout_writer=stdout_writer,
                            stderr_writer=stderr_writer,
                        )
                    )
                    stdout_writer.flush()
                    stderr_writer.flush()

                # 推送完成事件
                output_file = result_state.get("prepared_doc_path", "")
                output_file_str = str(output_file) if output_file else None

                if conversation_id and isinstance(result_state, dict):
                    try:
                        rewrite_state = self._build_rewrite_state_snapshot(
                            result_state=result_state,
                            initial_state=initial_state,
                        )
                        if task_kind == "rewrite":
                            self._conversation_service.append_rewrite_success(
                                conversation_id=conversation_id,
                                user_prompt=str(task_user_prompt or ""),
                                rewrite_state=rewrite_state,
                                model=model_provider,
                            )
                        elif task_kind == "comment_supplement":
                            self._conversation_service.append_comment_supplement_success(
                                conversation_id=conversation_id,
                                rewrite_state=rewrite_state,
                                model=model_provider,
                            )
                        else:
                            self._conversation_service.seed_generate_success(
                                conversation_id=conversation_id,
                                rewrite_state=rewrite_state,
                                model=model_provider,
                            )
                    except Exception:
                        logger.exception("写入 rewrite 会话历史失败: task_id=%s", task_id)

                if task_kind == "generate":
                    audit_state = dict(initial_state)
                    if isinstance(result_state, dict):
                        audit_state.update(result_state)
                    log_generate_task_success(audit_state)

                completion_result = self._build_task_result_payload(
                    result_state=result_state,
                    initial_state=initial_state,
                    elapsed_time=elapsed_time,
                    model_provider=model_provider,
                )
                self._task_queue.complete_task(task_id, result=completion_result, error=None)
                style_writeback_summary = None
                comment_writeback_summary = None
                if isinstance(completion_result, dict):
                    style_writeback_summary = completion_result.get("style_writeback")
                    comment_writeback_summary = completion_result.get("comment_writeback")

                callback.push_done(
                    DoneEventData(
                        task_id=task_id,
                        task_kind=task_kind,
                        success=True,
                        message=success_message,
                        output_file=output_file_str,
                        file_name=(
                            completion_result.get("file_name")
                            if isinstance(completion_result, dict)
                            else None
                        ),
                        processing_time=elapsed_time,
                        style_writeback=style_writeback_summary,
                        comment_writeback=comment_writeback_summary,
                    )
                )
                progress_log.info(f"[Task] 任务执行完成: {task_id}")

                try:
                    from backend.core.sse_manager import sse_manager

                    sse_manager.send_done_threadsafe(
                        task_id=task_id,
                        task_kind=task_kind,
                        success=True,
                        message=success_message,
                        output_file=output_file_str,
                        file_name=(
                            completion_result.get("file_name")
                            if isinstance(completion_result, dict)
                            else None
                        ),
                        processing_time=elapsed_time,
                        style_writeback=style_writeback_summary,
                        comment_writeback=comment_writeback_summary,
                    )
                except Exception:
                    pass

                logger.info(f"任务 {task_id} 执行完成，耗时 {elapsed_time:.2f}s")

            finally:
                # 清理事件循环
                try:
                    pending = asyncio.all_tasks(loop=loop)
                    for task in pending:
                        task.cancel()

                    if pending:
                        loop.run_until_complete(
                            asyncio.gather(*pending, return_exceptions=True)
                        )

                    if hasattr(loop, "shutdown_asyncgens"):
                        loop.run_until_complete(loop.shutdown_asyncgens())
                    if hasattr(loop, "shutdown_default_executor"):
                        loop.run_until_complete(loop.shutdown_default_executor())
                finally:
                    asyncio.set_event_loop(None)
                loop.close()

        except Exception as e:
            stdout_writer.flush()
            stderr_writer.flush()
            error_msg = str(e)
            tb = traceback.format_exc()
            logger.error(f"任务 {task_id} 执行失败: {error_msg}\n{tb}")

            # 取消属于非致命错误：前端应展示为 cancelled，而非 failed
            is_cancelled = False
            try:
                from backend.graphs.base_graph import TaskCancelledException

                is_cancelled = isinstance(e, TaskCancelledException)
            except Exception:
                is_cancelled = False

            if isinstance(e, asyncio.CancelledError):
                is_cancelled = True

            callback.push_error(
                ErrorEventData(
                    task_id=task_id,
                    task_kind=task_kind,
                    error=error_msg,
                    is_fatal=not is_cancelled,
                )
            )
            if is_cancelled:
                progress_log.warning(f"[Task] 任务已取消: {task_id}")
            else:
                progress_log.error(f"[Task] 任务执行失败: {task_id} - {error_msg}")

            try:
                from backend.core.sse_manager import sse_manager

                sse_manager.send_error_threadsafe(
                    task_id=task_id,
                    task_kind=task_kind,
                    error=error_msg,
                    is_fatal=not is_cancelled,
                )
            except Exception:
                pass

            if task_kind in {"rewrite", "comment_supplement"}:
                self._cleanup_temporary_output(rewrite_cleanup_holder.get("path"))

            # 更新任务队列状态
            self._task_queue.complete_task(task_id, result=None, error=error_msg)

    def _build_rewrite_state_snapshot(
        self, *, result_state: Dict[str, Any], initial_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        snapshot: Dict[str, Any] = {}
        for key in REWRITE_STATE_KEYS:
            value = result_state.get(key)
            if value in (None, ""):
                value = initial_state.get(key)
            if isinstance(value, (str, int)):
                snapshot[key] = value

        tender_type = str(snapshot.get("tender_type") or initial_state.get("tender_type") or "").strip()
        if tender_type:
            snapshot["tender_type"] = tender_type

        if not snapshot.get("prepared_doc_path"):
            fallback_doc = result_state.get("prepared_doc_path") or initial_state.get("prepared_doc_path")
            if isinstance(fallback_doc, str):
                snapshot["prepared_doc_path"] = fallback_doc

        if not snapshot.get("insertion_before_text") or not snapshot.get("insertion_after_text"):
            default_before, default_after = REWRITE_DEFAULT_ANCHORS.get(
                snapshot.get("tender_type") or "xjcg",
                REWRITE_DEFAULT_ANCHORS["xjcg"],
            )
            snapshot.setdefault("insertion_before_text", default_before)
            snapshot.setdefault("insertion_after_text", default_after)

        snapshot.setdefault("polished_text", str(result_state.get("polished_text") or ""))

        generation_mode = result_state.get("generation_mode")
        if generation_mode in (None, ""):
            generation_mode = initial_state.get("generation_mode")
        if isinstance(generation_mode, str) and generation_mode.strip():
            snapshot["generation_mode"] = generation_mode.strip()

        return snapshot

    @staticmethod
    def _build_comment_writeback_payload(result_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raw_payload = result_state.get("comment_writeback_result")
        if isinstance(raw_payload, dict):
            return {
                "summary": str(raw_payload.get("summary") or ""),
                "generated": int(raw_payload.get("generated") or 0),
                "added": int(raw_payload.get("added") or 0),
                "failed": int(raw_payload.get("failed") or 0),
                "skipped": int(raw_payload.get("skipped") or 0),
                "warning": bool(raw_payload.get("warning")),
            }

        if "generated_comment_count" not in result_state:
            return None

        generated_count = result_state.get("generated_comment_count")
        writeback_result = {
            "added": result_state.get("comment_writeback_added"),
            "failed": result_state.get("comment_writeback_failed"),
            "skipped": result_state.get("comment_writeback_skipped"),
        }
        return dict(
            build_comment_writeback_summary_payload(
                generated_count=generated_count,
                writeback_result=writeback_result,
            )
        )

    def _build_task_result_payload(
        self,
        *,
        result_state: Dict[str, Any],
        initial_state: Dict[str, Any],
        elapsed_time: float,
        model_provider: str,
    ) -> Dict[str, Any]:
        output_file_value = result_state.get("prepared_doc_path") or initial_state.get(
            "prepared_doc_path"
        )
        output_file = str(output_file_value or "").strip()
        output_path = pathlib.Path(output_file).expanduser() if output_file else None

        file_name = output_path.name if output_path else ""
        file_size = 0
        if output_path and output_path.exists():
            try:
                file_size = int(output_path.stat().st_size)
            except Exception:
                file_size = 0

        style_writeback = build_style_writeback_summary_payload(
            result_state.get("style_writeback_result"),
            str(result_state.get("style_writeback_summary") or ""),
        )
        comment_writeback = self._build_comment_writeback_payload(result_state)

        payload: Dict[str, Any] = {
            "output_file": output_file,
            "file_name": file_name,
            "file_size": file_size,
            "model_used": model_provider,
            "total_time_seconds": round(float(elapsed_time), 3),
        }
        if style_writeback is not None:
            payload["style_writeback"] = style_writeback
        if comment_writeback is not None:
            payload["comment_writeback"] = comment_writeback
        return payload

    def _cleanup_temporary_output(self, file_path: Optional[str]) -> None:
        target = str(file_path or "").strip()
        if not target:
            return

        try:
            path = pathlib.Path(target)
            if path.is_file():
                path.unlink()
                logger.info("已清理失败任务副本: %s", target)
        except Exception:
            logger.exception("清理任务副本失败: %s", target)

    async def _invoke_graph_async(
        self,
        compiled_graph,
        initial_state: Dict[str, Any],
        task_id: str,
        callback: SSECallback,
        model_provider: str,
        task_kind: str = "generate",
        llm_node_name: str = "generate_polished_text",
        task_audit_log_path: Optional[str] = None,
        rewrite_log_path: Optional[str] = None,
        rewrite_cleanup_holder: Optional[Dict[str, str]] = None,
        stdout_writer: Optional[Any] = None,
        stderr_writer: Optional[Any] = None,
    ) -> tuple:
        """异步执行 Graph.

        Args:
            compiled_graph: 编译后的 Graph
            initial_state: 初始状态
            task_id: 任务ID
            callback: SSE 回调
            model_provider: 模型提供商

        Returns:
            (result_state, elapsed_time)
        """
        from backend.graphs import invoke_with_timing_async
        try:
            from backend.core.sse_manager import sse_manager as _sse_manager
        except Exception:  # pragma: no cover
            _sse_manager = None

        llm_relay = _LLMSnapshotRelay(
            task_id=task_id,
            model_provider=model_provider,
            callback=callback,
            sse_manager=_sse_manager,
            node=llm_node_name,
        )

        resolved_task_audit_log_path = str(
            task_audit_log_path or rewrite_log_path or ""
        ).strip()

        # 配置
        config = {
            "configurable": {
                "task_id": task_id,
                "task_kind": task_kind,
                "llm_stream_callback": llm_relay.on_snapshot,
                "llm_stream_complete_callback": llm_relay.flush,
                "agent_step_callback": callback.push_agent_step,
                "suppress_llm_stdout": True,
                "model_provider": model_provider,
                "task_audit_log_path": resolved_task_audit_log_path,
                "rewrite_log_path": str(
                    rewrite_log_path or resolved_task_audit_log_path
                ).strip(),
                "rewrite_cleanup_holder": rewrite_cleanup_holder
                if rewrite_cleanup_holder is not None
                else {},
                "stdout_writer": stdout_writer,
                "stderr_writer": stderr_writer,
            }
        }

        # 执行
        result, elapsed = await invoke_with_timing_async(
            compiled_graph,
            initial_state,
            verbose=True,
            config=config,
        )
        final_polished_text = None
        if isinstance(result, dict):
            polished_text = result.get("polished_text")
            if polished_text:
                final_polished_text = str(polished_text)
        llm_relay.flush(final_polished_text)

        return result, elapsed


# 全局服务实例
_document_service: Optional[DocumentService] = None


def get_document_service() -> DocumentService:
    """获取文档生成服务实例（单例）."""
    global _document_service
    if _document_service is None:
        _document_service = DocumentService()
    return _document_service
