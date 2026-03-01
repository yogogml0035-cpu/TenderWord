"""文档生成服务模块.

封装文档生成的业务逻辑，集成 LangGraph 工作流。
"""

from __future__ import annotations

import asyncio
import logging
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Union

from backend.models import (
    DoneEventData,
    ErrorEventData,
    FormType,
    GenerateRequest,
    GenerateResponse,
    GenerateResult,
    LLMEventData,
    LogEventData,
    ProgressEventData,
    SSEEvent,
    SSEEventType,
)
from backend.models.tender import TenderData
from backend.task.task_queue_manager import get_task_queue

if TYPE_CHECKING:
    from backend.graphs.base_graph import BaseGraph

logger = logging.getLogger(__name__)

# 线程池执行器
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="doc_gen_")


# Graph 注册表：表单类型 -> Graph 类
GRAPH_REGISTRY: Dict[str, type] = {}


def _init_graph_registry():
    """初始化 Graph 注册表（延迟加载）."""
    global GRAPH_REGISTRY
    if GRAPH_REGISTRY:
        return

    try:
        from backend.graphs import XjcgTenderGraph, GngkTenderGraph

        GRAPH_REGISTRY["xjcg_tender"] = XjcgTenderGraph
        GRAPH_REGISTRY["gngk_tender"] = GngkTenderGraph
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
        # 生成任务ID
        task_id = f"task-{uuid.uuid4().hex[:8]}-{uuid.uuid4().hex[:4]}"

        # 创建 SSE 回调
        callback = SSECallback(task_id)
        with self._callbacks_lock:
            self._callbacks[task_id] = callback

        # 获取 Graph 类
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

        # 准备初始状态
        initial_state = self._build_initial_state(request)

        # 在任务队列中注册任务
        self._task_queue.add_task(
            task_id=task_id,
            user_session_id=initial_state.get("user_session_id", ""),
        )

        # 在后台线程中执行
        future = _executor.submit(
            self._run_graph,
            task_id,
            graph_class,
            initial_state,
            callback,
            request.model.value,
        )

        logger.info(f"创建文档生成任务: task_id={task_id}, form_type={form_type}")

        return GenerateResponse(
            success=True,
            task_id=task_id,
            message="任务已创建，正在后台执行",
        )

    def _build_initial_state(self, request: GenerateRequest) -> Dict[str, Any]:
        """构建 Graph 初始状态.

        Args:
            request: 生成请求

        Returns:
            初始状态字典
        """
        tender_data = request.tender_data
        file_paths = request.file_paths

        # 构建状态
        state: Dict[str, Any] = {
            "task_id": f"task-{uuid.uuid4().hex[:8]}-{uuid.uuid4().hex[:4]}",
            "tender_type": request.form_type.value.replace("_tender", ""),
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

        # 文件路径
        # origin_tender_path: 送审稿（可选）
        origin_tender = file_paths.get("origin_tender") or file_paths.get("template")
        if origin_tender and isinstance(origin_tender, str):
            state["origin_tender_path"] = origin_tender

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
    ) -> None:
        """在后台线程中执行 Graph.

        Args:
            task_id: 任务ID
            graph_class: Graph 类
            initial_state: 初始状态
            callback: SSE 回调
            model_provider: 模型提供商
        """
        import asyncio

        callback.push_log(f"开始执行文档生成任务: {task_id}")

        try:
            # 创建 Graph 实例
            graph_instance: BaseGraph = graph_class()
            compiled_graph = graph_instance.compile()

            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # 执行 Graph
                result_state, elapsed_time = loop.run_until_complete(
                    self._invoke_graph_async(
                        compiled_graph,
                        initial_state,
                        task_id,
                        callback,
                        model_provider,
                    )
                )

                # 推送完成事件
                output_file = result_state.get("prepared_doc_path", "")
                callback.push_done(
                    DoneEventData(
                        task_id=task_id,
                        success=True,
                        message="文档生成完成",
                        output_file=output_file,
                        processing_time=elapsed_time,
                    )
                )

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
            error_msg = str(e)
            tb = traceback.format_exc()
            logger.error(f"任务 {task_id} 执行失败: {error_msg}\n{tb}")

            callback.push_error(
                ErrorEventData(
                    task_id=task_id,
                    error=error_msg,
                    is_fatal=True,
                )
            )

            # 更新任务队列状态
            self._task_queue.complete_task(task_id, result=None, error=error_msg)

    async def _invoke_graph_async(
        self,
        compiled_graph,
        initial_state: Dict[str, Any],
        task_id: str,
        callback: SSECallback,
        model_provider: str,
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

        # LLM 流式回调
        def llm_stream_callback(content: str):
            callback.push_llm(content=content, model=model_provider)

        # 配置
        config = {
            "configurable": {
                "task_id": task_id,
                "llm_stream_callback": llm_stream_callback,
                "suppress_llm_stdout": True,
                "model_provider": model_provider,
            }
        }

        # 执行
        result, elapsed = await invoke_with_timing_async(
            compiled_graph,
            initial_state,
            verbose=True,
            config=config,
        )

        return result, elapsed


# 全局服务实例
_document_service: Optional[DocumentService] = None


def get_document_service() -> DocumentService:
    """获取文档生成服务实例（单例）."""
    global _document_service
    if _document_service is None:
        _document_service = DocumentService()
    return _document_service
