"""
全局任务队列管理器

管理多用户并发请求，按时间顺序执行任务，并提供进度追踪功能。
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class TaskStatus(Enum):
    """任务状态"""
    QUEUED = "queued"        # 排队中
    RUNNING = "running"      # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
    CANCELLED = "cancelled"  # 已取消


class NodeName(Enum):
    """Graph 节点名称（按执行顺序）"""
    PREPARE_TEMPLATE = "prepare_template"
    EXTRACT_TENDER_PARAMS = "extract_tender_params"
    DELETE_TENDER_PARAM = "delete_tender_param"
    GET_REPLACEMENTS = "get_replacements"
    REPLACE_CONTENT = "replace_content"
    GENERATE_POLISHED_TEXT = "generate_polished_text"
    UPDATE_WORD = "update_word"


# 节点显示名称映射
NODE_DISPLAY_NAMES = {
    NodeName.PREPARE_TEMPLATE: "复制原始模板文件",
    NodeName.EXTRACT_TENDER_PARAMS: "提取原始采购需求",
    NodeName.DELETE_TENDER_PARAM: "删除原始采购需求",
    NodeName.GET_REPLACEMENTS: "获取原始项目信息",
    NodeName.REPLACE_CONTENT: "替换最新项目信息",
    NodeName.GENERATE_POLISHED_TEXT: "AI生成采购需求",
    NodeName.UPDATE_WORD: "输出招标文件",
}

# 总节点数
TOTAL_NODES = 7


@dataclass
class TaskProgress:
    """任务进度信息"""
    completed_nodes: List[str] = field(default_factory=list)
    running_nodes: List[str] = field(default_factory=list)  # 支持并行执行的多个节点
    last_completed_node: Optional[str] = None  # 最后完成的节点
    total_nodes: int = TOTAL_NODES
    
    @property
    def completed_count(self) -> int:
        return len(self.completed_nodes)
    
    @property
    def progress_text(self) -> str:
        return f"{self.completed_count}/{self.total_nodes}"
    
    @property
    def progress_percent(self) -> float:
        return self.completed_count / self.total_nodes * 100
    
    def _get_node_display_name(self, node_name: str) -> str:
        """获取节点的显示名称"""
        try:
            node = NodeName(node_name)
            return NODE_DISPLAY_NAMES.get(node, node_name)
        except ValueError:
            return node_name
    
    def get_current_node_display(self) -> str:
        """获取当前节点的显示名称，优先显示正在执行的节点"""
        # 优先显示正在执行的节点
        if self.running_nodes:
            # 如果有多个并行节点，显示第一个（或者可以显示所有）
            display_name = self._get_node_display_name(self.running_nodes[0])
            if len(self.running_nodes) > 1:
                # 多个节点并行执行时，显示所有
                other_names = [self._get_node_display_name(n) for n in self.running_nodes[1:]]
                return f"正在执行: {display_name}（并行: {', '.join(other_names)}）"
            return f"正在执行: {display_name}"
        
        # 没有正在执行的节点，显示最后完成的
        if self.last_completed_node:
            display_name = self._get_node_display_name(self.last_completed_node)
            return f"已完成: {display_name}"
        
        return "等待中"


import queue

@dataclass
class Task:
    """任务信息"""
    task_id: str
    user_session_id: str
    created_at: datetime
    status: TaskStatus = TaskStatus.QUEUED
    progress: TaskProgress = field(default_factory=TaskProgress)
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    # 存储日志队列，以便在页面重载后重新连接
    log_queue: Optional[queue.Queue] = None
    # 心跳时间戳，用于检测用户是否还在页面上
    last_heartbeat: Optional[datetime] = None
    
    @property
    def elapsed_time(self) -> Optional[float]:
        """计算已用时间（秒）"""
        if self.started_at:
            end_time = self.completed_at or datetime.now()
            return (end_time - self.started_at).total_seconds()
        return None
    
    @property
    def heartbeat_age(self) -> Optional[float]:
        """计算距离上次心跳的时间（秒）"""
        if self.last_heartbeat:
            return (datetime.now() - self.last_heartbeat).total_seconds()
        return None


class TaskQueueManager:
    """
    全局任务队列管理器（单例模式）
    
    功能：
    1. 管理任务队列，按提交顺序执行
    2. 追踪每个任务的执行进度
    3. 提供队列状态查询接口
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._tasks: Dict[str, Task] = {}
        self._queue: List[str] = []  # 任务ID队列
        self._current_task_id: Optional[str] = None
        self._data_lock = threading.RLock()
        self._progress_callbacks: Dict[str, Callable] = {}
        self._cancel_events: Dict[str, threading.Event] = {}  # 取消事件
        
        # 心跳超时配置（秒）
        self._heartbeat_timeout = 10.0  # 10秒未收到心跳则认为用户已离开
        self._cleanup_interval = 5.0    # 每5秒检查一次超时任务
        
        # 启动后台清理线程
        self._cleanup_thread_stop = threading.Event()
        self._cleanup_thread = threading.Thread(
            target=self._heartbeat_cleanup_loop,
            daemon=True,
            name="TaskHeartbeatCleanup"
        )
        self._cleanup_thread.start()
    
    def create_task(self, user_session_id: str) -> Task:
        """
        创建新任务并加入队列
        
        Args:
            user_session_id: 用户会话ID
            
        Returns:
            创建的任务对象
        """
        with self._data_lock:
            task_id = str(uuid.uuid4())[:8]
            task = Task(
                task_id=task_id,
                user_session_id=user_session_id,
                created_at=datetime.now(),
                last_heartbeat=datetime.now()  # 初始化心跳时间
            )
            self._tasks[task_id] = task
            self._queue.append(task_id)
            self._cancel_events[task_id] = threading.Event()  # 创建取消事件
            return task
    
    def update_heartbeat(self, task_id: str) -> bool:
        """
        更新任务的心跳时间
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功更新（任务存在且未完成）
        """
        with self._data_lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            
            # 只有排队中或运行中的任务才更新心跳
            if task.status in (TaskStatus.QUEUED, TaskStatus.RUNNING):
                task.last_heartbeat = datetime.now()
                return True
            return False
    
    def _heartbeat_cleanup_loop(self):
        """
        后台线程：定期检查并清理心跳超时的任务
        """
        while not self._cleanup_thread_stop.is_set():
            try:
                self._check_and_cancel_timeout_tasks()
            except Exception as e:
                # 后台线程不能崩溃，静默处理错误
                print(f"[TaskQueue] 心跳检测线程出错: {e}")
            
            # 等待下一次检查
            self._cleanup_thread_stop.wait(self._cleanup_interval)
    
    def _check_and_cancel_timeout_tasks(self):
        """
        检查并取消心跳超时的任务
        """
        with self._data_lock:
            now = datetime.now()
            tasks_to_cancel = []
            
            for task_id, task in self._tasks.items():
                # 只检查排队中或运行中的任务
                if task.status not in (TaskStatus.QUEUED, TaskStatus.RUNNING):
                    continue
                
                # 检查心跳是否超时
                if task.last_heartbeat:
                    age = (now - task.last_heartbeat).total_seconds()
                    if age > self._heartbeat_timeout:
                        tasks_to_cancel.append((task_id, age))
        
        # 在锁外执行取消操作（cancel_task 会自己获取锁）
        for task_id, age in tasks_to_cancel:
            print(f"[TaskQueue] 任务 {task_id} 心跳超时 ({age:.1f}秒)，自动取消")
            self.cancel_task(task_id)
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务信息"""
        with self._data_lock:
            return self._tasks.get(task_id)
    
    def get_queue_position(self, task_id: str) -> int:
        """
        获取任务在队列中的位置
        
        Returns:
            位置（从1开始），0表示正在执行，-1表示不在队列中
        """
        with self._data_lock:
            if self._current_task_id == task_id:
                return 0
            try:
                # 计算前面还有多少个等待中的任务
                position = 0
                for tid in self._queue:
                    if tid == task_id:
                        return position
                    task = self._tasks.get(tid)
                    if task and task.status == TaskStatus.QUEUED:
                        position += 1
                return -1
            except ValueError:
                return -1
    
    def get_waiting_count(self, task_id: str) -> int:
        """
        获取指定任务前面等待的任务数量（包括正在执行的任务）
        
        Returns:
            等待数量
        """
        with self._data_lock:
            # 如果是正在执行的任务，返回0
            if self._current_task_id == task_id:
                return 0
            
            # 检查任务是否在队列中
            if task_id not in self._queue:
                return 0
            
            # 计算队列中在此任务前面的等待任务数
            queue_position = 0
            for tid in self._queue:
                if tid == task_id:
                    break
                task = self._tasks.get(tid)
                if task and task.status == TaskStatus.QUEUED:
                    queue_position += 1
            
            # 如果有正在执行的任务，需要加1（因为执行中的任务已从队列移除）
            if self._current_task_id is not None:
                queue_position += 1
            
            return queue_position
    
    def get_total_queued(self) -> int:
        """获取队列中等待的任务总数"""
        with self._data_lock:
            count = 0
            for tid in self._queue:
                task = self._tasks.get(tid)
                if task and task.status == TaskStatus.QUEUED:
                    count += 1
            return count
    
    def get_current_running_task(self) -> Optional[Task]:
        """获取当前正在执行的任务"""
        with self._data_lock:
            if self._current_task_id:
                return self._tasks.get(self._current_task_id)
            return None
    
    def start_task(self, task_id: str) -> bool:
        """
        标记任务开始执行
        
        Returns:
            是否成功开始
        """
        with self._data_lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            self._current_task_id = task_id
            
            # 从队列中移除
            if task_id in self._queue:
                self._queue.remove(task_id)
            
            return True
    
    def update_progress(self, task_id: str, node_name: str, completed: bool = True):
        """
        更新任务进度
        
        Args:
            task_id: 任务ID
            node_name: 节点名称
            completed: 是否已完成该节点
        """
        with self._data_lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            
            if completed:
                # 节点完成：从运行列表移除，加入完成列表
                if node_name in task.progress.running_nodes:
                    task.progress.running_nodes.remove(node_name)
                if node_name not in task.progress.completed_nodes:
                    task.progress.completed_nodes.append(node_name)
                task.progress.last_completed_node = node_name
            else:
                # 节点开始：加入运行列表
                if node_name not in task.progress.running_nodes:
                    task.progress.running_nodes.append(node_name)
            
            # 调用进度回调
            callback = self._progress_callbacks.get(task_id)
            if callback:
                try:
                    callback(task.progress)
                except Exception:
                    pass
    
    def complete_task(self, task_id: str, result: Any = None, error: str = None):
        """
        标记任务完成
        
        Args:
            task_id: 任务ID
            result: 执行结果
            error: 错误信息（如果有）
        """
        with self._data_lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            
            # 如果任务已经被取消，不要覆盖状态
            if task.status == TaskStatus.CANCELLED:
                # 只清理当前任务ID（如果正在执行的话）
                if self._current_task_id == task_id:
                    self._current_task_id = None
                return
            
            task.completed_at = datetime.now()
            task.result = result
            task.error = error
            task.status = TaskStatus.COMPLETED if not error else TaskStatus.FAILED
            
            if self._current_task_id == task_id:
                self._current_task_id = None
            
            # 清理进度回调和取消事件
            self._progress_callbacks.pop(task_id, None)
            self._cancel_events.pop(task_id, None)
    
    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功取消（True: 成功取消, False: 任务不存在或已完成）
        """
        with self._data_lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            
            # 如果任务已完成或已失败，无法取消
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                return False
            
            # 设置取消事件
            cancel_event = self._cancel_events.get(task_id)
            if cancel_event:
                cancel_event.set()
            
            # 如果任务在排队中，直接从队列移除
            if task.status == TaskStatus.QUEUED:
                if task_id in self._queue:
                    self._queue.remove(task_id)
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                task.error = "用户取消"
                # 清理
                self._progress_callbacks.pop(task_id, None)
                self._cancel_events.pop(task_id, None)
                return True
            
            # 如果任务正在运行，标记为取消（线程会检查并退出）
            if task.status == TaskStatus.RUNNING:
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                task.error = "用户取消"
                if self._current_task_id == task_id:
                    self._current_task_id = None
                # 清理
                self._progress_callbacks.pop(task_id, None)
                return True
            
            return False
    
    def is_task_cancelled(self, task_id: str) -> bool:
        """
        检查任务是否被取消
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否被取消
        """
        with self._data_lock:
            cancel_event = self._cancel_events.get(task_id)
            if cancel_event:
                return cancel_event.is_set()
            # 如果没有取消事件，检查任务状态
            task = self._tasks.get(task_id)
            if task:
                return task.status == TaskStatus.CANCELLED
            return False
    
    def get_cancel_event(self, task_id: str) -> Optional[threading.Event]:
        """
        获取任务的取消事件
        
        Args:
            task_id: 任务ID
            
        Returns:
            取消事件对象
        """
        with self._data_lock:
            return self._cancel_events.get(task_id)
    
    def register_progress_callback(self, task_id: str, callback: Callable[[TaskProgress], None]):
        """注册进度更新回调"""
        with self._data_lock:
            self._progress_callbacks[task_id] = callback
    
    def unregister_progress_callback(self, task_id: str):
        """取消注册进度更新回调"""
        with self._data_lock:
            self._progress_callbacks.pop(task_id, None)
    
    def cleanup_old_tasks(self, max_age_seconds: int = 3600):
        """清理超过指定时间的已完成任务"""
        with self._data_lock:
            now = datetime.now()
            to_remove = []
            for task_id, task in self._tasks.items():
                if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                    if task.completed_at:
                        age = (now - task.completed_at).total_seconds()
                        if age > max_age_seconds:
                            to_remove.append(task_id)
            
            for task_id in to_remove:
                del self._tasks[task_id]
    
    def get_queue_status_text(self, task_id: str) -> str:
        """
        获取队列状态的显示文本
        
        Args:
            task_id: 任务ID
            
        Returns:
            状态文本
        """
        with self._data_lock:
            task = self._tasks.get(task_id)
            if not task:
                return "任务不存在"
            
            if task.status == TaskStatus.RUNNING:
                return "🚀 正在执行中..."
            elif task.status == TaskStatus.COMPLETED:
                return "✅ 已完成"
            elif task.status == TaskStatus.FAILED:
                return f"❌ 执行失败: {task.error or '未知错误'}"
            else:
                waiting = self.get_waiting_count(task_id)
                if waiting == 0:
                    return "⏳ 即将开始执行..."
                else:
                    return f"⏳ 排队中，前面还有 {waiting} 位用户"


# 全局实例（模块内部使用）
_task_queue = TaskQueueManager()


def get_task_queue() -> TaskQueueManager:
    """获取全局任务队列管理器实例"""
    return _task_queue

