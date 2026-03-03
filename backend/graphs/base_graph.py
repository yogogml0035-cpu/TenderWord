"""
基础 Graph 类模块

提供通用的 graph 构建逻辑、执行逻辑、锁机制和进度追踪功能。
所有具体的 graph 类都应该继承 BaseGraph 并实现抽象方法。

主要组件：
1. CrossProcessFileLock - 跨进程文件锁，确保 Word COM 操作的并发安全
2. BaseGraph - 基础 Graph 抽象类
3. wrap_node_with_progress - 节点进度追踪包装器
4. invoke_with_timing - 同步执行方法（带计时）
5. invoke_with_timing_async - 异步执行方法（带计时）
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from langgraph.graph import END, START, StateGraph
import contextlib
import time
import pathlib
import os
import tempfile
import asyncio
import threading
from functools import wraps
from typing import Callable, Any, Optional, TextIO, Type, TypedDict

from backend.config.settings import settings
from backend.util.log_util.progress_log import progress_log
from abc import ABC, abstractmethod
from langgraph.graph import END, START, StateGraph
import contextlib
import time
import pathlib
import os
import tempfile
import asyncio
import threading
from functools import wraps
from typing import Callable, Any, Optional, TextIO, Type, TypedDict
from backend.util.log_util.progress_log import progress_log


# ============================================================================
# 任务取消异常
# ============================================================================
class TaskCancelledException(Exception):
    """任务被用户取消时抛出的异常"""
    pass


# ============================================================================
# 跨进程文件锁：确保同一时间只有一个 graph 在执行
# 使用文件锁而不是 threading.Lock，确保多进程/多用户并发访问时的安全性
# ============================================================================

class CrossProcessFileLock:
    """
    跨进程文件锁
    
    使用文件锁实现跨进程互斥，确保多个 Streamlit 进程（或多个用户会话）
    不会同时执行 Word COM 操作。
    
    特点：
    1. 使用 Windows msvcrt.locking 实现文件级锁
    2. 同时使用 threading.Lock 保护同一进程内的并发访问
    3. 支持超时机制，避免死锁
    """
    
    def __init__(self, lock_file_path: str = None):
        """初始化文件锁

        Args:
            lock_file_path: 锁文件路径，默认使用 settings.LOCK_FILE_PATH
        """
        if lock_file_path is None:
            lock_file_path = settings.LOCK_FILE_PATH

        if lock_file_path is None:
            # 使用临时目录，确保所有进程都能访问
            lock_dir = pathlib.Path(tempfile.gettempdir())
            lock_file_path = str(lock_dir / "tender_word_graph_execution.lock")

        self.lock_file_path = lock_file_path
        self._lock_file = None
        self._thread_lock = threading.Lock()  # 同进程内的线程锁
        self._file_lock_acquired = False
        
    def acquire(self, timeout: float = None) -> bool:
        """获取锁（带超时）

        获取顺序：
        1. 先获取线程锁（同进程内互斥）
        2. 再获取文件锁（跨进程互斥）

        Args:
            timeout: 超时时间（秒），默认使用 settings.LOCK_TIMEOUT

        Returns:
            bool: 是否成功获取锁
        """
        if timeout is None:
            timeout = settings.LOCK_TIMEOUT
        self._lock_file = None
        """
        初始化文件锁
        
        Args:
            lock_file_path: 锁文件路径，默认使用临时目录下的固定文件名
        """
        if lock_file_path is None:
            # 使用临时目录，确保所有进程都能访问
            lock_dir = pathlib.Path(tempfile.gettempdir())
            lock_file_path = str(lock_dir / "tender_word_graph_execution.lock")
        
        self.lock_file_path = lock_file_path
        self._lock_file = None
        self._thread_lock = threading.Lock()  # 同进程内的线程锁
        self._file_lock_acquired = False
        
    def acquire(self, timeout: float = 600.0) -> bool:
        """
        获取锁（带超时）
        
        获取顺序：
        1. 先获取线程锁（同进程内互斥）
        2. 再获取文件锁（跨进程互斥）
        
        Args:
            timeout: 超时时间（秒），默认 600 秒（10 分钟）
            
        Returns:
            bool: 是否成功获取锁
        """
        import msvcrt
        
        start_time = time.time()
        
        # 步骤1：获取线程锁（带超时）
        thread_lock_acquired = self._thread_lock.acquire(timeout=timeout)
        if not thread_lock_acquired:
            progress_log.debug("[FileLock] 获取线程锁超时")
            return False
        
        try:
            # 步骤2：获取文件锁（带超时）
            remaining_timeout = timeout - (time.time() - start_time)
            if remaining_timeout <= 0:
                self._thread_lock.release()
                progress_log.debug("[FileLock] 获取文件锁前超时")
                return False
            
            while True:
                try:
                    # 打开或创建锁文件（使用 r+ 模式需要文件存在，所以先确保文件存在）
                    if self._lock_file is None:
                        # 先确保文件存在并有内容（用于锁定）
                        if not os.path.exists(self.lock_file_path):
                            with open(self.lock_file_path, 'w') as f:
                                f.write('L')  # 写入一个字符，确保文件非空
                        self._lock_file = open(self.lock_file_path, 'r+b')  # 二进制模式更可靠
                    
                    # 确保文件位置在开头（msvcrt.locking 从当前位置开始锁定）
                    self._lock_file.seek(0)
                    
                    # 尝试获取独占锁（非阻塞），锁定从位置 0 开始的 1 个字节
                    try:
                        msvcrt.locking(self._lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                        self._file_lock_acquired = True
                        return True
                        
                    except IOError:
                        # 文件锁被其他进程持有
                        pass
                    
                    # 检查是否超时
                    elapsed = time.time() - start_time
                    if elapsed >= timeout:
                        progress_log.warning(f"[FileLock] 获取文件锁超时（等待了 {elapsed:.1f} 秒）")
                        self._thread_lock.release()
                        return False
                    
                    # 等待后重试
                    time.sleep(0.5)
                    
                except Exception as e:
                    progress_log.error(f"[FileLock] 获取文件锁时出错: {e}")
                    self._thread_lock.release()
                    return False
                    
        except Exception as e:
            progress_log.error(f"[FileLock] 获取锁时发生异常: {e}")
            self._thread_lock.release()
            return False
    
    def release(self):
        """释放锁"""
        import msvcrt
        
        try:
            # 步骤1：释放文件锁
            if self._file_lock_acquired and self._lock_file is not None:
                try:
                    # 必须先把文件位置移到锁定的位置（位置 0）
                    self._lock_file.seek(0)
                    msvcrt.locking(self._lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                except Exception as e:
                    progress_log.warning(f"[FileLock] 释放文件锁时出错: {e}")
                finally:
                    self._file_lock_acquired = False
            
            # 关闭文件句柄
            if self._lock_file is not None:
                try:
                    self._lock_file.close()
                except Exception:
                    pass
                finally:
                    self._lock_file = None
                    
        finally:
            # 步骤2：释放线程锁
            try:
                self._thread_lock.release()
            except RuntimeError:
                # 如果线程锁未被持有，忽略错误
                pass
    
    def __enter__(self):
        """上下文管理器入口"""
        if not self.acquire():
            raise RuntimeError("无法获取跨进程执行锁（超时），可能有其他任务正在执行")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.release()
        return False


# ============================================================================
# 进度追踪辅助函数
# ============================================================================
def _check_cancellation(config: dict):
    """
    检查任务是否被取消，如果被取消则抛出异常
    
    Args:
        config: graph 配置字典，包含 task_id
        
    Raises:
        TaskCancelledException: 如果任务已被取消
    """
    if config and "configurable" in config:
        task_id = config["configurable"].get("task_id")
        if task_id:
            # 延迟导入，避免循环依赖
            from backend.task.task_queue_manager import get_task_queue
            queue = get_task_queue()
            if queue.is_task_cancelled(task_id):
                raise TaskCancelledException(f"任务 {task_id} 已被用户取消")


def _update_node_progress(node_name: str, config: dict, completed: bool = True):
    """
    更新节点进度
    
    Args:
        node_name: 节点名称
        config: graph 配置字典，包含 task_id
        completed: 节点是否已完成
    """
    if config and "configurable" in config:
        task_id = config["configurable"].get("task_id")
        if task_id:
            # 延迟导入，避免循环依赖
            from backend.task.task_queue_manager import get_task_queue
            queue = get_task_queue()
            queue.update_progress(task_id, node_name, completed=completed)


def wrap_node_with_progress(node_func: Callable, node_name: str) -> Callable:
    """
    包装节点函数以追踪进度，并在每个节点执行前检查取消状态
    
    Args:
        node_func: 原始节点函数
        node_name: 节点名称
        
    Returns:
        包装后的节点函数
    """
    if asyncio.iscoroutinefunction(node_func):
        @wraps(node_func)
        async def async_wrapper(state, config=None):
            _check_cancellation(config)  # 执行前检查取消
            _update_node_progress(node_name, config, completed=False)
            result = await node_func(state, config)
            _check_cancellation(config)  # 执行后检查取消
            _update_node_progress(node_name, config, completed=True)
            return result
        return async_wrapper
    else:
        @wraps(node_func)
        def sync_wrapper(state, config=None):
            _check_cancellation(config)  # 执行前检查取消
            _update_node_progress(node_name, config, completed=False)
            result = node_func(state, config)
            _check_cancellation(config)  # 执行后检查取消
            _update_node_progress(node_name, config, completed=True)
            return result
        return sync_wrapper


# ============================================================================
# 基础 Graph 类
# ============================================================================

class BaseGraph(ABC):
    """
    基础 Graph 类，提供通用功能
    
    功能：
    1. 跨进程文件锁（CrossProcessFileLock）
    2. 节点进度追踪（wrap_node_with_progress）
    3. 任务取消检查（_check_cancellation）
    4. 同步/异步执行方法
    
    子类必须实现：
    - build_graph(): 构建 graph 结构
    - get_state_class(): 返回使用的 state 类
    
    使用示例：
        class MyGraph(BaseGraph):
            def build_graph(self):
                builder = StateGraph(MyState)
                # 添加节点和边
                return builder
            
            def get_state_class(self):
                return MyState
        
        # 使用
        graph = MyGraph()
        result, elapsed = graph.invoke(initial_state)
    """
    
    def __init__(self):
        """初始化 BaseGraph"""
        self._graph = None
        self._lock = CrossProcessFileLock()
    
    @abstractmethod
    def build_graph(self) -> StateGraph:
        """
        构建 graph 结构（子类必须实现）
        
        Returns:
            StateGraph: 未编译的 StateGraph 实例
        """
        raise NotImplementedError("子类必须实现 build_graph() 方法")
    
    @abstractmethod
    def get_state_class(self) -> Type[TypedDict]:
        """
        返回使用的 state 类（子类必须实现）
        
        Returns:
            Type[TypedDict]: State 类型
        """
        raise NotImplementedError("子类必须实现 get_state_class() 方法")
    
    def compile(self):
        """
        编译 graph
        
        延迟编译：graph 在首次调用 compile() 时才编译，提高启动速度
        
        Returns:
            CompiledGraph: 编译后的 graph 实例
        """
        if self._graph is None:
            self._graph = self.build_graph().compile()
        return self._graph
    
    def invoke(self, initial_state: dict, config=None, verbose: bool = True):
        """
        同步执行 graph（带锁和计时）
        
        Args:
            initial_state: 初始状态字典
            config: 透传给 graph.invoke 的配置（如流式回调）
            verbose: 是否打印时间信息
        
        Returns:
            tuple: (执行结果, 执行时间(秒))
        """
        return invoke_with_timing(
            self.compile(), 
            initial_state, 
            verbose=verbose, 
            config=config,
            lock=self._lock
        )
    
    async def ainvoke(self, initial_state: dict, config=None, verbose: bool = True):
        """
        异步执行 graph（带锁和计时）
        
        Args:
            initial_state: 初始状态字典
            config: 透传给 graph.ainvoke 的配置（如流式回调）
            verbose: 是否打印时间信息
        
        Returns:
            tuple: (执行结果, 执行时间(秒))
        """
        return await invoke_with_timing_async(
            self.compile(), 
            initial_state, 
            verbose=verbose, 
            config=config,
            lock=self._lock
        )
    
    def wrap_node(self, node_name: str, node_func: Callable) -> Callable:
        """
        包装节点函数，添加进度追踪
        
        Args:
            node_name: 节点名称
            node_func: 原始节点函数
        
        Returns:
            Callable: 包装后的节点函数
        """
        return wrap_node_with_progress(node_func, node_name)


class StandardTenderWorkflowGraph(BaseGraph):
    STATE_CLS: Type[TypedDict]

    NODE_PREPARE_TEMPLATE: Callable
    NODE_GET_COMMENTS: Callable
    NODE_COPY_COMMENTS: Callable
    NODE_EXTRACT_TENDER_PARAMS: Callable
    NODE_DELETE_TENDER_PARAM: Callable
    NODE_GET_REPLACEMENTS: Callable
    NODE_REPLACE_CONTENT: Callable
    NODE_GENERATE_POLISHED_TEXT: Callable
    NODE_GENERATE_COMMENTS: Callable
    NODE_UPDATE_WORD: Callable

    def get_state_class(self) -> Type[TypedDict]:
        return self.STATE_CLS

    def estimate_total_nodes(self, initial_state: dict) -> int:
        origin_tender_path = initial_state.get("origin_tender_path")
        has_origin_for_comments = bool(origin_tender_path and str(origin_tender_path).strip())
        return 13 if has_origin_for_comments else 10

    def build_graph(self) -> StateGraph:
        state_cls = self.STATE_CLS
        builder = StateGraph(state_cls)

        node_prepare_template = getattr(type(self), "NODE_PREPARE_TEMPLATE")
        node_get_comments = getattr(type(self), "NODE_GET_COMMENTS")
        node_copy_comments = getattr(type(self), "NODE_COPY_COMMENTS")
        node_extract_tender_params = getattr(type(self), "NODE_EXTRACT_TENDER_PARAMS")
        node_generate_polished_text = getattr(type(self), "NODE_GENERATE_POLISHED_TEXT")
        node_generate_comments = getattr(type(self), "NODE_GENERATE_COMMENTS")
        node_update_word = getattr(type(self), "NODE_UPDATE_WORD")

        def comments_branch_done(state, config):
            return state

        def comments_ready(state, config):
            path = state.get("origin_tender_path")
            has_origin = bool(path and str(path).strip())
            if has_origin:
                return {}
            updates = {
                "comment_plan_detail": [],
                "strikethrough_plan": [],
                "non_black_font_plan": [],
                "copy_comments_log": "未上传送审稿，跳过批注提取与复制",
                "copy_comments_added": 0,
                "copy_comments_unmatched": [],
            }
            if "comment_plan" in getattr(state_cls, "__annotations__", {}):
                updates["comment_plan"] = []
            return updates

        builder.add_node("prepare_template", self.wrap_node("prepare_template", node_prepare_template))
        builder.add_node("get_comments", self.wrap_node("get_comments", node_get_comments))
        builder.add_node("copy_comments", self.wrap_node("copy_comments", node_copy_comments))
        builder.add_node("extract_tender_params", self.wrap_node("extract_tender_params", node_extract_tender_params))
        builder.add_node("comments_ready", self.wrap_node("comments_ready", comments_ready))
        builder.add_node("word_operations_subgraph", self._build_word_operations_subgraph())
        builder.add_node("generate_polished_text", self.wrap_node("generate_polished_text", node_generate_polished_text))
        builder.add_node("comments_branch_done", self.wrap_node("comments_branch_done", comments_branch_done))
        builder.add_node("generate_comments", self.wrap_node("generate_comments", node_generate_comments))
        builder.add_node("update_word", self.wrap_node("update_word", node_update_word))

        builder.add_edge(START, "prepare_template")
        builder.add_edge("prepare_template", "extract_tender_params")

        def _has_origin_for_extract_comments(state) -> str:
            path = state.get("origin_tender_path")
            return "get_comments" if (path and str(path).strip()) else "comments_ready"

        builder.add_conditional_edges(
            "prepare_template",
            _has_origin_for_extract_comments,
            {
                "get_comments": "get_comments",
                "comments_ready": "comments_ready",
            },
        )
        builder.add_edge("get_comments", "copy_comments")
        builder.add_edge("copy_comments", "comments_ready")

        builder.add_edge(["extract_tender_params", "comments_ready"], "word_operations_subgraph")
        builder.add_edge(["extract_tender_params", "comments_ready"], "generate_polished_text")

        def _has_origin_for_comments(state) -> str:
            path = state.get("origin_tender_path")
            return "generate_comments" if (path and str(path).strip()) else "comments_branch_done"

        builder.add_conditional_edges(
            "generate_polished_text",
            _has_origin_for_comments,
            {
                "generate_comments": "generate_comments",
                "comments_branch_done": "comments_branch_done",
            },
        )
        builder.add_edge("generate_comments", "comments_branch_done")
        builder.add_edge(["word_operations_subgraph", "comments_branch_done"], "update_word")
        builder.add_edge("update_word", END)

        return builder

    def _build_word_operations_subgraph(self):
        state_cls = self.STATE_CLS
        subgraph_builder = StateGraph(state_cls)

        node_delete_tender_param = getattr(type(self), "NODE_DELETE_TENDER_PARAM")
        node_get_replacements = getattr(type(self), "NODE_GET_REPLACEMENTS")
        node_replace_content = getattr(type(self), "NODE_REPLACE_CONTENT")

        subgraph_builder.add_node(
            "delete_tender_param",
            self.wrap_node("delete_tender_param", node_delete_tender_param),
        )
        subgraph_builder.add_node(
            "get_replacements",
            self.wrap_node("get_replacements", node_get_replacements),
        )
        subgraph_builder.add_node(
            "replace_content",
            self.wrap_node("replace_content", node_replace_content),
        )
        subgraph_builder.add_edge(START, "delete_tender_param")
        subgraph_builder.add_edge("delete_tender_param", "get_replacements")
        subgraph_builder.add_edge("get_replacements", "replace_content")
        subgraph_builder.add_edge("replace_content", END)
        return subgraph_builder.compile()


# ============================================================================
# Graph 执行函数（带锁和计时）
# ============================================================================

def invoke_with_timing(
    graph_instance, 
    initial_state: dict, 
    verbose: bool = True, 
    config=None,
    lock: CrossProcessFileLock = None
):
    """
    执行 graph 并统计时间（带全局锁，确保并发安全）
    
    Args:
        graph_instance: 编译后的 graph 实例
        initial_state: 初始状态字典
        verbose: 是否打印时间信息
        config: 透传给 graph.invoke 的配置（如流式回调）
        lock: 跨进程文件锁实例（如果为 None，则创建新实例）
    
    Returns:
        tuple: (执行结果, 执行时间(秒))
    """
    if lock is None:
        lock = CrossProcessFileLock()
    
    thread_name = threading.current_thread().name
    
    progress_log.debug(f"[Graph] 线程 {thread_name} 正在等待执行锁...")
    
    with lock:
        progress_log.debug(f"[Graph] 线程 {thread_name} 获取到执行锁，开始执行...")
        
        begin_ts = time.time()
        try:
            result = graph_instance.invoke(initial_state, config=config)
        finally:
            elapsed = time.time() - begin_ts
            progress_log.debug(f"[Graph] 线程 {thread_name} 执行完成，释放锁")
        
        if verbose:
            progress_log.info("=" * 60)
            progress_log.info("Graph 执行完成！")
            progress_log.info(f"总执行时间: {elapsed:.2f} 秒 ({elapsed*1000:.0f} 毫秒)")
            if elapsed >= 60:
                minutes = int(elapsed // 60)
                seconds = elapsed % 60
                progress_log.info(f"总执行时间: {minutes} 分 {seconds:.2f} 秒")
            progress_log.info("=" * 60)
        
        return result, elapsed


async def invoke_with_timing_async(
    graph_instance, 
    initial_state: dict, 
    verbose: bool = True, 
    config=None,
    lock: CrossProcessFileLock = None
):
    """
    异步执行 graph 并统计时间（带公平锁 + 文件锁，确保并发安全且按队列顺序执行）
    
    执行流程：
    1. 首先通过公平锁机制等待轮到自己（按队列顺序）
    2. 然后获取文件锁（保护 Word COM 操作）
    3. 执行 graph
    4. 释放锁并通知下一个任务
    
    Args:
        graph_instance: 编译后的 graph 实例
        initial_state: 初始状态字典
        verbose: 是否打印时间信息
        config: 透传给 graph.ainvoke 的配置
            - task_id: 任务ID，用于进度追踪
            - llm_stream_callback: LLM流式输出回调
            - suppress_llm_stdout: 是否抑制LLM输出到stdout
            - model_provider: 模型提供商
            - stdout_writer: stdout 重定向目标（可选）
            - stderr_writer: stderr 重定向目标（可选）
        lock: 跨进程文件锁实例（如果为 None，则创建新实例）
    
    Returns:
        tuple: (执行结果, 执行时间(秒))
    """
    if lock is None:
        lock = CrossProcessFileLock()
    
    # 延迟导入，避免循环依赖
    from backend.task.task_queue_manager import get_task_queue
    queue = get_task_queue()
    
    # 获取配置参数
    task_id = None
    stdout_writer: Optional[TextIO] = None
    stderr_writer: Optional[TextIO] = None
    
    if config and "configurable" in config:
        task_id = config["configurable"].get("task_id")
        stdout_writer = config["configurable"].get("stdout_writer")
        stderr_writer = config["configurable"].get("stderr_writer")
    
    # ============================================================================
    # 第一步：公平锁 - 等待轮到自己（按队列顺序）
    # ============================================================================
    if task_id:
        waiting_count = queue.get_waiting_count(task_id)
        if waiting_count > 0:
            progress_log.debug(f"[FairLock] 任务 {task_id} 开始排队等待，前面有 {waiting_count} 个任务")
        
        # 阻塞等待，直到轮到自己
        got_turn = queue.wait_for_turn(task_id)
        if not got_turn:
            # 任务被取消或超时
            raise TaskCancelledException(f"任务 {task_id} 在等待执行时被取消或超时")
    
    # ============================================================================
    # 第二步：文件锁 - 保护 Word COM 操作（跨进程互斥）
    # ============================================================================
    # 使用文件锁（因为 COM 操作必须串行，且需要跨进程保护）
    # 重要：stdout/stderr 重定向必须在获取锁之后才设置，否则多线程会互相覆盖
    with lock:
        # 在锁内设置 stdout/stderr 重定向，确保只有正在执行的任务会重定向输出
        stdout_ctx = contextlib.redirect_stdout(stdout_writer) if stdout_writer else contextlib.nullcontext()
        stderr_ctx = contextlib.redirect_stderr(stderr_writer) if stderr_writer else contextlib.nullcontext()
        
        with stdout_ctx, stderr_ctx:
            # 现在可以安全地打印日志了
            progress_log.debug(f"[Graph] 任务 {task_id} 获取到执行锁，开始执行...")
            
            # 标记任务开始
            if task_id:
                queue.start_task(task_id)
            
            begin_ts = time.time()
            error_msg = None
            try:
                result = await graph_instance.ainvoke(initial_state, config=config)
            except Exception as e:
                error_msg = str(e)
                raise
            finally:
                elapsed = time.time() - begin_ts
                progress_log.debug(f"[Graph] 任务 {task_id} 执行完成，释放锁")
                
                # 标记任务完成（这会自动通知下一个等待的任务）
                if task_id:
                    queue.complete_task(task_id, result=None if error_msg else "success", error=error_msg)
            
            if verbose:
                progress_log.info("=" * 60)
                progress_log.info("Graph 异步执行完成！")
                progress_log.info(f"总执行时间: {elapsed:.2f} 秒 ({elapsed*1000:.0f} 毫秒)")
                if elapsed >= 60:
                    minutes = int(elapsed // 60)
                    seconds = elapsed % 60
                    progress_log.info(f"总执行时间: {minutes} 分 {seconds:.2f} 秒")
                progress_log.info("=" * 60)
            
            return result, elapsed
