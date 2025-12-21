from __future__ import annotations
from langgraph.graph import END, START, StateGraph
import contextlib
import time
import pathlib
import sys
import asyncio
import threading
import os
import tempfile
from functools import wraps
from typing import Callable, Any, Optional, TextIO


ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nodes.xjcg_word_nodes import (
    generate_polished_text,
    update_word,
    prepare_template,
    replace_content,
    get_replacements,
    extract_tender_params,
    delete_tender_param
)
from state import XjcgTenderGraphState, TextFormatState
from task.task_queue_manager import get_task_queue


# ============================================================================
# 跨进程文件锁：确保同一时间只有一个 graph 在执行
# 使用文件锁而不是 threading.Lock，因为 Streamlit 可能运行在多进程模式
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
            print("[FileLock] 获取线程锁超时")
            return False
        
        try:
            # 步骤2：获取文件锁（带超时）
            remaining_timeout = timeout - (time.time() - start_time)
            if remaining_timeout <= 0:
                self._thread_lock.release()
                print("[FileLock] 获取文件锁前超时")
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
                        print(f"[FileLock] 获取文件锁超时（等待了 {elapsed:.1f} 秒）")
                        self._thread_lock.release()
                        return False
                    
                    # 等待后重试
                    time.sleep(0.5)
                    
                except Exception as e:
                    print(f"[FileLock] 获取文件锁时出错: {e}")
                    self._thread_lock.release()
                    return False
                    
        except Exception as e:
            print(f"[FileLock] 获取锁时发生异常: {e}")
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
                    print(f"[FileLock] 释放文件锁时出错: {e}")
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


# 创建全局文件锁实例
_graph_execution_lock = CrossProcessFileLock()


# ============================================================================
# 任务取消异常
# ============================================================================
class TaskCancelledException(Exception):
    """任务被用户取消时抛出的异常"""
    pass


# ============================================================================
# 进度追踪：包装节点函数以报告进度
# ============================================================================
def _check_cancellation(config: dict):
    """检查任务是否被取消，如果被取消则抛出异常"""
    if config and "configurable" in config:
        task_id = config["configurable"].get("task_id")
        if task_id:
            queue = get_task_queue()
            if queue.is_task_cancelled(task_id):
                raise TaskCancelledException(f"任务 {task_id} 已被用户取消")


def _update_node_progress(node_name: str, config: dict, completed: bool = True):
    """更新节点进度"""
    if config and "configurable" in config:
        task_id = config["configurable"].get("task_id")
        if task_id:
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
# 子图：Word 操作流程
# ============================================================================
def build_word_operations_subgraph():
    """
    构建 Word 操作子图。
    
    子图流程：
    START → delete_tender_param → get_replacements → replace_content → END
    
    子图使用与主图相同的状态类型 XjcgTenderGraphState，
    这样可以直接共享状态，无需状态转换。
    """
    subgraph_builder = StateGraph(XjcgTenderGraphState)
    
    # 添加子图节点（使用进度追踪包装）
    subgraph_builder.add_node("delete_tender_param", 
                              wrap_node_with_progress(delete_tender_param, "delete_tender_param"))
    subgraph_builder.add_node("get_replacements", 
                              wrap_node_with_progress(get_replacements, "get_replacements"))
    subgraph_builder.add_node("replace_content", 
                              wrap_node_with_progress(replace_content, "replace_content"))
    
    # 子图边：串行执行
    subgraph_builder.add_edge(START, "delete_tender_param")
    subgraph_builder.add_edge("delete_tender_param", "get_replacements")
    subgraph_builder.add_edge("get_replacements", "replace_content")
    subgraph_builder.add_edge("replace_content", END)
    
    return subgraph_builder.compile()


# 编译子图（作为一个可调用的节点）
word_operations_subgraph = build_word_operations_subgraph()


# ============================================================================
# 主图
# ============================================================================
def build_graph():
    """
    构建主图。
    
    主图流程：
    
                        extract_tender_params
                              /          \\
                             /            \\
                            ▼              ▼
              word_operations_subgraph    generate_polished_text
              (子图: delete→get→replace)        (LLM 调用)
                            \\              /
                             \\            /
                              ▼          ▼
                              update_word
                                   │
                                  END
    
    两个分支并行执行：
    - 左分支：word_operations_subgraph（子图，内部串行执行 3 个节点）
    - 右分支：generate_polished_text（单个异步节点）
    
    最后在 update_word 汇合。
    """
    builder = StateGraph(XjcgTenderGraphState)
    
    # 添加主图节点（使用进度追踪包装）
    builder.add_node("prepare_template", 
                     wrap_node_with_progress(prepare_template, "prepare_template"))
    builder.add_node("extract_tender_params", 
                     wrap_node_with_progress(extract_tender_params, "extract_tender_params"))
    # 子图作为一个节点（子图内部已经有进度追踪）
    builder.add_node("word_operations_subgraph", word_operations_subgraph)
    builder.add_node("generate_polished_text", 
                     wrap_node_with_progress(generate_polished_text, "generate_polished_text"))
    builder.add_node("update_word", 
                     wrap_node_with_progress(update_word, "update_word"))
    
    # 主图边
    builder.add_edge(START, "prepare_template")
    builder.add_edge("prepare_template", "extract_tender_params")
    
    # 从 extract_tender_params 扇出到两个并行分支
    builder.add_edge("extract_tender_params", "word_operations_subgraph")
    builder.add_edge("extract_tender_params", "generate_polished_text")
    
    # 两个分支都汇入 update_word（扇入）
    builder.add_edge("word_operations_subgraph", "update_word")
    builder.add_edge("generate_polished_text", "update_word")
    
    builder.add_edge("update_word", END)

    return builder.compile()



graph = build_graph()


def invoke_with_timing(graph_instance, initial_state: dict, verbose: bool = True, config=None):
    """
    执行 graph 并统计时间（带全局锁，确保并发安全）
    
    Args:
        graph_instance: 编译后的 graph 实例
        initial_state: 初始状态字典
        verbose: 是否打印时间信息
        config: 透传给 graph.invoke 的配置（如流式回调）
    
    Returns:
        tuple: (执行结果, 执行时间(秒))
    """
    # 获取全局锁，确保同一时间只有一个 graph 在执行
    # 这是解决多用户并发 COM 冲突的关键
    thread_name = threading.current_thread().name
    
    print(f"[Graph] 线程 {thread_name} 正在等待执行锁...")
    
    with _graph_execution_lock:
        print(f"[Graph] 线程 {thread_name} 获取到执行锁，开始执行...")
        
        begin_ts = time.time()
        try:
            result = graph_instance.invoke(initial_state, config=config)
        finally:
            elapsed = time.time() - begin_ts
            print(f"[Graph] 线程 {thread_name} 执行完成，释放锁")
        
        if verbose:
            print("=" * 60)
            print(f"Graph 执行完成！")
            print(f"总执行时间: {elapsed:.2f} 秒 ({elapsed*1000:.0f} 毫秒)")
            if elapsed >= 60:
                minutes = int(elapsed // 60)
                seconds = elapsed % 60
                print(f"总执行时间: {minutes} 分 {seconds:.2f} 秒")
            print("=" * 60)
        
        return result, elapsed


async def invoke_with_timing_async(graph_instance, initial_state: dict, verbose: bool = True, config=None):
    """
    异步执行 graph 并统计时间（带公平锁 + 文件锁，确保并发安全且按队列顺序执行）
    
    执行流程：
    1. 首先通过公平锁机制等待轮到自己（按队列顺序）
    2. 然后获取文件锁（保护 Word COM 操作）
    3. 执行 graph
    4. 释放锁并通知下一个任务
    
    Config 参数说明：
        - task_id: 任务ID，用于进度追踪
        - llm_stream_callback: LLM流式输出回调
        - suppress_llm_stdout: 是否抑制LLM输出到stdout
        - model_provider: 模型提供商
        - stdout_writer: stdout 重定向目标（可选）
        - stderr_writer: stderr 重定向目标（可选）
    """
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
            print(f"[FairLock] 任务 {task_id} 开始排队等待，前面有 {waiting_count} 个任务")
        
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
    with _graph_execution_lock:
        # 在锁内设置 stdout/stderr 重定向，确保只有正在执行的任务会重定向输出
        stdout_ctx = contextlib.redirect_stdout(stdout_writer) if stdout_writer else contextlib.nullcontext()
        stderr_ctx = contextlib.redirect_stderr(stderr_writer) if stderr_writer else contextlib.nullcontext()
        
        with stdout_ctx, stderr_ctx:
            # 现在可以安全地打印日志了
            print(f"[Graph] 任务 {task_id} 获取到执行锁，开始执行...")
            
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
                print(f"[Graph] 任务 {task_id} 执行完成，释放锁")
                
                # 标记任务完成（这会自动通知下一个等待的任务）
                if task_id:
                    queue.complete_task(task_id, result=None if error_msg else "success", error=error_msg)
            
            if verbose:
                print("=" * 60)
                print(f"Graph 异步执行完成！")
                print(f"总执行时间: {elapsed:.2f} 秒 ({elapsed*1000:.0f} 毫秒)")
                if elapsed >= 60:
                    minutes = int(elapsed // 60)
                    seconds = elapsed % 60
                    print(f"总执行时间: {minutes} 分 {seconds:.2f} 秒")
                print("=" * 60)
            
            return result, elapsed


if __name__ == "__main__":
    begin_ts = time.time()
    initial_state = {
        # 文件路径配置
        "tender_param_path": "TenderFile/技术参数.docx",
        "origin_tender_path": "TenderFile/252699-原位杂交仪-询价文件-初稿1.doc",
        "insertion_before_text": "第三章  采购需求",  # 插入位置的前置文本
        "insertion_after_text": "第四章  响应文件有关格式",  # 插入位置的后置文本
        "project_name": "测试项目名称",
        "project_number": "测试项目编号",
        "project_content": """第1包：恒温暖柜               贰台
                              第2包：数字化手术吸引系统      壹套
                              第3包：止血带系统             壹套""",
        "bzj_rule": """第1包：人民币4000元整；
                       第2包：人民币16000元整；
                       第3包：人民币2000元整""",
        "buyer_name": "上海市中医医院",
        "project_zbr_xbr": "徐旭东、任彧晟",
        "zbr_xbr_tel": "8605、8625",
        "zbr_pinyin": "xuxudong"
    }
    result = graph.invoke(initial_state)
    elapsed = time.time() - begin_ts
    print(f"Graph run finished in {elapsed:.2f}s ({elapsed*1000:.0f} ms)")
