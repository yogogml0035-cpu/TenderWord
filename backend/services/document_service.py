"""文档生成服务模块.

封装文档生成的业务逻辑，集成 LangGraph 工作流。
"""

from __future__ import annotations

import asyncio
import logging
import pathlib
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Union

from backend.models import (
    DoneEventData,
    ErrorEventData,
    GenerateRequest,
    GenerateResponse,
    LLMEventData,
    LogEventData,
    ProgressEventData,
    SSEEvent,
    SSEEventType,
)
from backend.services.conversation_service import get_conversation_service
from backend.services.user_routing_service import get_user_routing_service
from backend.task.task_queue_manager import get_task_queue
from backend.util.common_util import LLMTimeoutError
from backend.util.log_util.execution_log import logger as execution_logger
from backend.util.log_util.progress_log import progress_log
from backend.util.log_util.sse_log_handler import task_log_context

if TYPE_CHECKING:
    from backend.graphs.base_graph import BaseGraph

logger = logging.getLogger(__name__)

# 线程池执行器
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="doc_gen_")


LLM_SNAPSHOT_INTERVAL_SECONDS = 0.25

REWRITE_STATE_KEYS = [
    "tender_type",
    "prepared_doc_path",
    "polished_text",
    "insertion_before_text",
    "insertion_after_text",
    "project_name",
    "project_number",
    "project_content",
    "buyer_name",
    "bzj_rule",
    "project_zbr_xbr",
    "zbr_xbr_tel",
    "zbr_pinyin",
    "shell_start_date",
    "shell_end_date",
    "submit_date",
    "platform",
    "service_fee",
]

REWRITE_DEFAULT_ANCHORS = {
    "xjcg": ("第三章  采购需求", "第四章  响应文件有关格式"),
    "gngk": ("第三章 招标内容及要求", "第四章 投标文件有关格式"),
}

TASK_KIND_TO_LLM_NODE = {
    "generate": "generate_polished_text",
    "rewrite": "rewrite_text",
}

class _BufferedLoggerWriter:
    """将 stdout/stderr 文本按行转发到执行日志。"""

    def __init__(self, level: str = "info"):
        self._level = level.lower()
        self._buffer = ""

    def write(self, data: str) -> int:
        if not data:
            return 0
        self._buffer += data
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._emit(line)
        return len(data)

    def flush(self) -> None:
        if self._buffer:
            self._emit(self._buffer)
            self._buffer = ""

    def _emit(self, line: str) -> None:
        text = line.strip()
        if not text:
            return
        if self._level == "error":
            execution_logger.error(text)
        else:
            execution_logger.info(text)


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
REWRITE_GRAPH_CLASS: Optional[type] = None


def _init_graph_registry():
    """初始化 Graph 注册表（延迟加载）."""
    global GRAPH_REGISTRY, REWRITE_GRAPH_CLASS
    if GRAPH_REGISTRY and REWRITE_GRAPH_CLASS is not None:
        return

    try:
        from backend.graphs import GngkTenderGraph, RewriteGraph, XjcgTenderGraph

        GRAPH_REGISTRY["xjcg_tender"] = XjcgTenderGraph
        GRAPH_REGISTRY["gngk_tender"] = GngkTenderGraph
        REWRITE_GRAPH_CLASS = RewriteGraph
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
        self._user_routing_service = get_user_routing_service()
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
        skip_prompt_validation: bool = False,
    ) -> GenerateResponse:
        """创建 rewrite 任务（复用文档任务队列 + SSE 三卡片链路）。"""
        normalized_conversation_id = str(conversation_id or "").strip()
        normalized_prompt = str(user_prompt or "").strip()

        task_id, callback = self._allocate_task_callback_pair()
        if not normalized_conversation_id:
            return GenerateResponse(
                success=False,
                task_id=task_id,
                message="conversation_id 不能为空",
                error="REWRITE_HISTORY_NOT_FOUND",
            )

        if not normalized_prompt:
            return GenerateResponse(
                success=False,
                task_id=task_id,
                message="修改指令不能为空",
                error="REWRITE_PROMPT_INVALID",
            )

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

        if not skip_prompt_validation:
            try:
                is_related = await self._user_routing_service.is_rewrite_prompt_related(
                    prompt=normalized_prompt,
                    model_provider=model_provider,
                    latest_rewrite_state=latest_rewrite_state,
                )
            except LLMTimeoutError:
                logger.exception("rewrite 指令相关性校验超时: conversation_id=%s", normalized_conversation_id)
                return GenerateResponse(
                    success=False,
                    task_id=task_id,
                    message="修改指令校验超时，请稍后重试",
                    error="LLM_TIMEOUT",
                )
            except Exception:
                logger.exception("rewrite 指令相关性校验失败: conversation_id=%s", normalized_conversation_id)
                return GenerateResponse(
                    success=False,
                    task_id=task_id,
                    message="修改指令校验失败，请稍后重试",
                    error="LLM_SERVICE_ERROR",
                )

            if not is_related:
                return GenerateResponse(
                    success=False,
                    task_id=task_id,
                    message="当前输入不属于可执行的修改指令",
                    error="REWRITE_PROMPT_INVALID",
                )

        if not REWRITE_GRAPH_CLASS:
            return GenerateResponse(
                success=False,
                task_id=task_id,
                message="Rewrite Graph 未初始化",
                error="REWRITE_TARGET_NOT_RESOLVED",
            )

        rewrite_initial_state = self._build_rewrite_graph_initial_state(
            task_id=task_id,
            conversation_id=normalized_conversation_id,
            user_prompt=normalized_prompt,
        )

        return self._submit_graph_task(
            task_id=task_id,
            graph_class=REWRITE_GRAPH_CLASS,
            initial_state=rewrite_initial_state,
            callback=callback,
            model_provider=model_provider,
            task_kind="rewrite",
            conversation_id=normalized_conversation_id,
            rewrite_user_prompt=normalized_prompt,
            llm_node_name=TASK_KIND_TO_LLM_NODE["rewrite"],
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
        rewrite_user_prompt: Optional[str] = None,
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
            rewrite_user_prompt,
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

    def _resolve_rewrite_target_state(
        self, *, conversation_id: str, user_prompt: str
    ) -> Optional[Dict[str, Any]]:
        candidates = self._conversation_service.list_rewrite_states(conversation_id)
        if not candidates:
            return None

        prompt = user_prompt.strip()
        if len(candidates) >= 2 and any(token in prompt for token in ("上一版", "前一版", "上个版本")):
            return dict(candidates[-2])
        if any(token in prompt for token in ("第一版", "最初版本", "初稿")):
            return dict(candidates[0])
        return dict(candidates[-1])

    def _build_rewrite_initial_state(
        self,
        *,
        task_id: str,
        conversation_id: str,
        user_prompt: str,
        target_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        tender_type = str(target_state.get("tender_type") or "").strip() or "xjcg"
        prepared_doc_path = str(target_state.get("prepared_doc_path") or "").strip()
        if not prepared_doc_path:
            raise ValueError("rewrite 目标文档路径不存在")

        default_before, default_after = REWRITE_DEFAULT_ANCHORS.get(
            tender_type, REWRITE_DEFAULT_ANCHORS["xjcg"]
        )

        state: Dict[str, Any] = {
            "task_id": task_id,
            "conversation_id": conversation_id,
            "user_session_id": conversation_id,
            "tender_type": tender_type,
            "origin_tender_path": prepared_doc_path,
            "clean_draft_path": prepared_doc_path,
            "insertion_before_text": str(
                target_state.get("insertion_before_text") or default_before
            ),
            "insertion_after_text": str(
                target_state.get("insertion_after_text") or default_after
            ),
            "rewrite_mode": True,
            "rewrite_user_prompt": user_prompt,
            "rewrite_base_text": str(target_state.get("polished_text") or ""),
        }

        for key in REWRITE_STATE_KEYS:
            if key in {"prepared_doc_path", "tender_type", "insertion_before_text", "insertion_after_text"}:
                continue
            value = target_state.get(key)
            if isinstance(value, str):
                state[key] = value

        return state

    def _build_rewrite_graph_initial_state(
        self,
        *,
        task_id: str,
        conversation_id: str,
        user_prompt: str,
    ) -> Dict[str, Any]:
        return {
            "task_id": task_id,
            "conversation_id": conversation_id,
            "user_session_id": conversation_id,
            "rewrite_user_prompt": user_prompt,
            "rewrite_mode": True,
        }

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
        state: Dict[str, Any] = {
            # 与队列任务ID保持一致，确保进度、取消、日志链路统一
            "task_id": task_id,
            "conversation_id": conversation_id,
            "user_session_id": conversation_id,
            "tender_type": tender_type,
            # 项目信息
            "project_name": tender_data.project_name or "",
            "project_number": tender_data.project_number or "",
            "project_content": tender_data.project_content or "",
            "buyer_name": tender_data.buyer_name or "",
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

        insertion_before_text = None
        insertion_after_text = None
        insertion_config = getattr(request, "insertion_config", None)
        if insertion_config:
            insertion_before_text = getattr(insertion_config, "before_text", None)
            insertion_after_text = getattr(insertion_config, "after_text", None)

        if not insertion_before_text or not str(insertion_before_text).strip():
            insertion_before_text = "第三章  采购需求" if tender_type == "xjcg" else "第三章 采购需求"
        if not insertion_after_text or not str(insertion_after_text).strip():
            insertion_after_text = (
                "第四章  响应文件有关格式" if tender_type == "xjcg" else "第四章 投标文件有关格式"
            )

        state["insertion_before_text"] = str(insertion_before_text)
        state["insertion_after_text"] = str(insertion_after_text)

        # 文件路径
        # origin_tender_path: 送审稿（可选）
        origin_tender = file_paths.get("origin_tender") or file_paths.get("template")
        if origin_tender and isinstance(origin_tender, str):
            state["origin_tender_path"] = origin_tender

        # clean_draft_path: 清洁稿（可选）
        clean_draft = file_paths.get("clean_draft") or file_paths.get("clean_draft_path")
        if clean_draft and isinstance(clean_draft, str):
            state["clean_draft_path"] = clean_draft

        # tender_param_paths: 技术参数文件（支持多文件）
        params = file_paths.get("tender_params") or file_paths.get("params") or []
        if isinstance(params, str):
            params = [params]
        state["tender_param_paths"] = params if isinstance(params, list) else []

        # template: 模板文件（必需）
        template = file_paths.get("template")
        if template and isinstance(template, str):
            # 保存模板路径，后续 prepare_template 节点会处理
            state["template_path"] = template

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
        rewrite_user_prompt: Optional[str] = None,
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
            rewrite_user_prompt: rewrite 用户指令
        """
        import asyncio

        task_label = "修改任务" if task_kind == "rewrite" else "文档生成任务"
        success_message = "修改任务完成" if task_kind == "rewrite" else "文档生成完成"
        callback.push_log(f"开始执行{task_label}: {task_id}")
        progress_log.info(f"[Task] 开始执行任务: {task_id}")
        stdout_writer = _BufferedLoggerWriter(level="info")
        stderr_writer = _BufferedLoggerWriter(level="error")
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
                            llm_node_name=llm_node_name or TASK_KIND_TO_LLM_NODE.get(task_kind, "generate_polished_text"),
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
                                user_prompt=str(rewrite_user_prompt or ""),
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

                callback.push_done(
                    DoneEventData(
                        task_id=task_id,
                        task_kind=task_kind,
                        success=True,
                        message=success_message,
                        output_file=output_file_str,
                        processing_time=elapsed_time,
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
                        processing_time=elapsed_time,
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

            if task_kind == "rewrite":
                self._cleanup_rewrite_output(rewrite_cleanup_holder.get("path"))

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
            if isinstance(value, str):
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
        return snapshot

    def _cleanup_rewrite_output(self, file_path: Optional[str]) -> None:
        target = str(file_path or "").strip()
        if not target:
            return

        try:
            path = pathlib.Path(target)
            if path.is_file():
                path.unlink()
                logger.info("已清理 rewrite 失败副本: %s", target)
        except Exception:
            logger.exception("清理 rewrite 副本失败: %s", target)

    async def _invoke_graph_async(
        self,
        compiled_graph,
        initial_state: Dict[str, Any],
        task_id: str,
        callback: SSECallback,
        model_provider: str,
        llm_node_name: str = "generate_polished_text",
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

        # 配置
        config = {
            "configurable": {
                "task_id": task_id,
                "llm_stream_callback": llm_relay.on_snapshot,
                "llm_stream_complete_callback": llm_relay.flush,
                "suppress_llm_stdout": True,
                "model_provider": model_provider,
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
