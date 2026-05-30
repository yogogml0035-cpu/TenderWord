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
from backend.nodes.common_word_nodes.comment_agent import comment_agent_writeback
from backend.nodes.common_word_nodes.content_agent_generate import content_agent_generate
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


NODE_GENERATE_POLISHED_TEXT = "generate_polished_text"
NODE_CONTENT_AGENT = "content_agent"
NODE_COMMENT_AGENT = "comment_agent"


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
TRACKED_PROGRESS_NODES = {
    "prepare_template",
    "get_comments",
    "copy_comments",
    "extract_tender_params",
    "resolve_edit_target",
    "resolve_rewrite_target",
    "extract_edit_context",
    "get_rewrite_comments",
    "delete_section",
    "delete_tender_param",
    "get_replacements",
    "replace_content",
    "edit_text",
    "rewrite_text",
    NODE_GENERATE_POLISHED_TEXT,
    NODE_CONTENT_AGENT,
    "generate_comments",
    NODE_COMMENT_AGENT,
    "prepare_comment_supplement",
    "finalize_comment_supplement",
    "update_word",
}


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
    if node_name not in TRACKED_PROGRESS_NODES:
        return

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

    def estimate_total_nodes(self, initial_state: dict) -> int:
        """
        估算任务总节点数（用于前端进度条）。

        子类可按流程分支覆写，默认回退到配置值。
        """
        return max(1, int(settings.TASK_TOTAL_NODES))
    
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
    NODE_EXTRACT_TENDER_PARAMS: Callable
    NODE_DELETE_TENDER_PARAM: Callable
    NODE_GET_REPLACEMENTS: Callable
    NODE_REPLACE_CONTENT: Callable
    NODE_GENERATE_POLISHED_TEXT: Callable
    NODE_CONTENT_AGENT_GENERATE: Callable = content_agent_generate
    NODE_GENERATE_COMMENTS: Callable
    NODE_UPDATE_WORD: Callable
    NODE_COMMENT_AGENT: Callable = comment_agent_writeback

    def get_state_class(self) -> Type[TypedDict]:
        return self.STATE_CLS

    def get_word_operation_steps(self) -> tuple[tuple[str, Callable], ...]:
        return (
            ("delete_tender_param", getattr(type(self), "NODE_DELETE_TENDER_PARAM")),
            ("get_replacements", getattr(type(self), "NODE_GET_REPLACEMENTS")),
            ("replace_content", getattr(type(self), "NODE_REPLACE_CONTENT")),
        )

    def get_post_update_steps(self) -> tuple[tuple[str, Callable], ...]:
        return ()

    def estimate_total_nodes(self, initial_state: dict) -> int:
        generation_mode = str(initial_state.get("generation_mode") or "workflow").strip()
        generation_node = NODE_CONTENT_AGENT if generation_mode == "agent" else NODE_GENERATE_POLISHED_TEXT
        base_nodes = {
            "prepare_template",
            "extract_tender_params",
            generation_node,
            "update_word",
        }
        if generation_mode == "agent":
            base_nodes.add(NODE_COMMENT_AGENT)
        else:
            base_nodes.add("generate_comments")
        base_nodes.update(
            node_name
            for node_name, _node_func in self.get_word_operation_steps()
            if node_name in TRACKED_PROGRESS_NODES
        )
        base_nodes.update(
            node_name
            for node_name, _node_func in self.get_post_update_steps()
            if node_name in TRACKED_PROGRESS_NODES
        )
        return len(base_nodes)

    def build_graph(self) -> StateGraph:
        state_cls = self.STATE_CLS
        builder = StateGraph(state_cls)

        node_prepare_template = getattr(type(self), "NODE_PREPARE_TEMPLATE")
        node_extract_tender_params = getattr(type(self), "NODE_EXTRACT_TENDER_PARAMS")
        node_generate_polished_text = getattr(type(self), "NODE_GENERATE_POLISHED_TEXT")
        node_content_agent_generate = getattr(type(self), "NODE_CONTENT_AGENT_GENERATE")
        node_generate_comments = getattr(type(self), "NODE_GENERATE_COMMENTS")
        node_update_word = getattr(type(self), "NODE_UPDATE_WORD")
        node_comment_agent = getattr(type(self), "NODE_COMMENT_AGENT")

        def comments_branch_done(state, config):
            return {
                "suppress_ai_comment_writeback": state.get("generation_mode") == "agent",
            }

        def generation_mode_gate(state, config):
            return {}

        builder.add_node("prepare_template", self.wrap_node("prepare_template", node_prepare_template))
        builder.add_node("extract_tender_params", self.wrap_node("extract_tender_params", node_extract_tender_params))
        builder.add_node("word_operations_subgraph", self._build_word_operations_subgraph())
        builder.add_node("generation_mode_gate", self.wrap_node("generation_mode_gate", generation_mode_gate))
        builder.add_node(NODE_GENERATE_POLISHED_TEXT, self.wrap_node(NODE_GENERATE_POLISHED_TEXT, node_generate_polished_text))
        builder.add_node(NODE_CONTENT_AGENT, self.wrap_node(NODE_CONTENT_AGENT, node_content_agent_generate))
        builder.add_node("comments_branch_done", self.wrap_node("comments_branch_done", comments_branch_done))
        builder.add_node("generate_comments", self.wrap_node("generate_comments", node_generate_comments))
        builder.add_node("update_word", self.wrap_node("update_word", node_update_word))
        builder.add_node(NODE_COMMENT_AGENT, self.wrap_node(NODE_COMMENT_AGENT, node_comment_agent))
        post_update_steps = self.get_post_update_steps()
        for node_name, node_func in post_update_steps:
            builder.add_node(node_name, self.wrap_node(node_name, node_func))

        builder.add_edge(START, "prepare_template")
        builder.add_edge("prepare_template", "extract_tender_params")
        builder.add_edge("extract_tender_params", "word_operations_subgraph")
        builder.add_edge("extract_tender_params", "generation_mode_gate")
        builder.add_conditional_edges(
            "generation_mode_gate",
            self._select_generation_node,
            {
                NODE_GENERATE_POLISHED_TEXT: NODE_GENERATE_POLISHED_TEXT,
                NODE_CONTENT_AGENT: NODE_CONTENT_AGENT,
            },
        )
        builder.add_edge(NODE_GENERATE_POLISHED_TEXT, "generate_comments")
        builder.add_edge(NODE_CONTENT_AGENT, "comments_branch_done")
        builder.add_edge("generate_comments", "comments_branch_done")
        builder.add_edge(["word_operations_subgraph", "comments_branch_done"], "update_word")
        after_update_target = post_update_steps[0][0] if post_update_steps else END
        builder.add_conditional_edges(
            "update_word",
            self._select_after_update_node,
            {
                NODE_COMMENT_AGENT: NODE_COMMENT_AGENT,
                "after_update": after_update_target,
            },
        )
        builder.add_edge(NODE_COMMENT_AGENT, after_update_target)
        if post_update_steps:
            first_post_node = post_update_steps[0][0]
            for current_step, next_step in zip(post_update_steps, post_update_steps[1:]):
                builder.add_edge(current_step[0], next_step[0])
            builder.add_edge(post_update_steps[-1][0], END)

        return builder

    @staticmethod
    def _select_generation_node(state) -> str:
        return NODE_CONTENT_AGENT if state.get("generation_mode") == "agent" else NODE_GENERATE_POLISHED_TEXT

    @staticmethod
    def _select_after_update_node(state) -> str:
        return NODE_COMMENT_AGENT if state.get("generation_mode") == "agent" else "after_update"

    def _build_word_operations_subgraph(self):
        state_cls = self.STATE_CLS
        subgraph_builder = StateGraph(state_cls)
        steps = self.get_word_operation_steps()
        if not steps:
            raise ValueError("word_operations_subgraph 至少需要一个节点")

        for node_name, node_func in steps:
            subgraph_builder.add_node(node_name, self.wrap_node(node_name, node_func))

        subgraph_builder.add_edge(START, steps[0][0])
        for current_step, next_step in zip(steps, steps[1:]):
            subgraph_builder.add_edge(current_step[0], next_step[0])
        subgraph_builder.add_edge(steps[-1][0], END)
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
                queue.register_running_async_context(
                    task_id,
                    asyncio.get_running_loop(),
                    asyncio.current_task(),
                )
                if queue.is_task_cancelled(task_id):
                    raise TaskCancelledException(f"任务 {task_id} 已被用户取消")
            
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
                    queue.clear_running_async_context(task_id)
                    task_result = None
                    if error_msg is None:
                        try:
                            if isinstance(result, dict):
                                prepared = result.get("prepared_doc_path") or result.get("output_file")
                                if prepared:
                                    task_result = str(prepared)
                        except Exception:
                            task_result = None

                    queue.complete_task(
                        task_id,
                        result=(task_result or "success") if error_msg is None else None,
                        error=error_msg,
                    )
            
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
