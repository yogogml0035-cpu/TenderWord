"""SSE 连接管理器.

提供 Server-Sent Events (SSE) 连接管理和事件广播功能。
支持多客户端连接、事件存储和断线重连。
"""

import asyncio
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional, Set

from backend.config.settings import settings
from backend.models.sse import SSEEvent, SSEEventType

logger = logging.getLogger(__name__)


@dataclass
class SSEClient:
    """SSE 客户端信息.

    Attributes:
        client_id: 客户端唯一标识
        task_id: 订阅的任务ID
        connected_at: 连接时间
        last_event_id: 最后接收的事件ID
        event_queue: 事件队列
    """

    client_id: str
    task_id: str
    connected_at: float = field(default_factory=time.time)
    last_event_id: Optional[int] = None
    event_queue: asyncio.Queue = field(default_factory=asyncio.Queue)

    def __hash__(self) -> int:
        return hash(self.client_id)


class SSEManager:
    """SSE 连接管理器.

    管理 SSE 连接的生命周期、事件广播和事件存储。
    支持 Last-Event-ID 断线重连机制。

    Attributes:
        max_events_per_task: 每个任务最大存储事件数
        event_ttl: 事件过期时间（秒）
        heartbeat_interval: 心跳间隔（秒）
    """
    def __init__(
        self,
        max_events_per_task: int = None,
        event_ttl: int = None,
        heartbeat_interval: int = None,
    ):
        """初始化 SSE 管理器.

        Args:
            max_events_per_task: 每个任务最大存储事件数，默认使用 settings.SSE_MAX_EVENTS_PER_TASK
            event_ttl: 事件过期时间（秒），默认使用 settings.SSE_EVENT_TTL
            heartbeat_interval: 心跳间隔（秒），默认使用 settings.SSE_HEARTBEAT_INTERVAL
        """
        self.max_events_per_task = max_events_per_task or settings.SSE_MAX_EVENTS_PER_TASK
        self.event_ttl = event_ttl or settings.SSE_EVENT_TTL
        self.heartbeat_interval = heartbeat_interval or settings.SSE_HEARTBEAT_INTERVAL

        # 任务 -> 客户端集合
        self._clients: Dict[str, Set[SSEClient]] = defaultdict(set)

        # 任务 -> 事件列表（用于断线重连）
        self._events: Dict[str, List[SSEEvent]] = defaultdict(list)

        # 事件ID计数器
        self._event_counters: Dict[str, int] = defaultdict(int)
    def __init__(
        self,
        max_events_per_task: int = 1000,
        event_ttl: int = 3600,  # 1 hour
        heartbeat_interval: int = 15,  # 15 seconds
    ):
        """初始化 SSE 管理器.

        Args:
            max_events_per_task: 每个任务最大存储事件数
            event_ttl: 事件过期时间（秒）
            heartbeat_interval: 心跳间隔（秒）
        """
        self.max_events_per_task = max_events_per_task
        self.event_ttl = event_ttl
        self.heartbeat_interval = heartbeat_interval

        # 任务 -> 客户端集合
        self._clients: Dict[str, Set[SSEClient]] = defaultdict(set)

        # 任务 -> 事件列表（用于断线重连）
        self._events: Dict[str, List[SSEEvent]] = defaultdict(list)

        # 事件ID计数器
        self._event_counters: Dict[str, int] = defaultdict(int)

        # 客户端ID -> 客户端
        self._client_map: Dict[str, SSEClient] = {}

        # 锁
        self._lock = asyncio.Lock()

        logger.info(
            "SSEManager initialized",
            extra={
                "max_events_per_task": max_events_per_task,
                "event_ttl": event_ttl,
                "heartbeat_interval": heartbeat_interval,
            },
        )

    async def connect(
        self,
        task_id: str,
        client_id: str,
        last_event_id: Optional[int] = None,
    ) -> SSEClient:
        """建立 SSE 连接.

        Args:
            task_id: 任务ID
            client_id: 客户端ID
            last_event_id: 客户端最后接收的事件ID（用于断线重连）

        Returns:
            SSEClient 客户端实例
        """
        async with self._lock:
            client = SSEClient(
                client_id=client_id,
                task_id=task_id,
                last_event_id=last_event_id,
            )

            self._clients[task_id].add(client)
            self._client_map[client_id] = client

            logger.info(
                f"SSE client connected: {client_id}",
                extra={
                    "task_id": task_id,
                    "client_id": client_id,
                    "last_event_id": last_event_id,
                    "total_clients": len(self._clients[task_id]),
                },
            )

            return client

    async def disconnect(self, client_id: str) -> None:
        """断开 SSE 连接.

        Args:
            client_id: 客户端ID
        """
        async with self._lock:
            client = self._client_map.pop(client_id, None)
            if client:
                self._clients[client.task_id].discard(client)
                logger.info(
                    f"SSE client disconnected: {client_id}",
                    extra={
                        "task_id": client.task_id,
                        "client_id": client_id,
                        "remaining_clients": len(self._clients[client.task_id]),
                    },
                )

    async def broadcast(
        self,
        task_id: str,
        event_type: SSEEventType,
        data: Any,
    ) -> int:
        """广播事件到所有订阅该任务的客户端.

        Args:
            task_id: 任务ID
            event_type: 事件类型
            data: 事件数据

        Returns:
            事件ID
        """
        async with self._lock:
            # 生成事件ID
            event_id = self._event_counters[task_id] + 1
            self._event_counters[task_id] = event_id

            # 创建事件
            event = SSEEvent(
                id=str(event_id),
                event=event_type,
                data=data,
            )

            # 存储事件（用于断线重连）
            self._events[task_id].append(event)

            # 限制存储的事件数量
            if len(self._events[task_id]) > self.max_events_per_task:
                self._events[task_id] = self._events[task_id][
                    -self.max_events_per_task :
                ]

            # 发送到所有客户端队列
            client_count = 0
            for client in self._clients[task_id]:
                try:
                    client.event_queue.put_nowait(event)
                    client_count += 1
                except asyncio.QueueFull:
                    logger.warning(
                        f"Client queue full: {client.client_id}",
                        extra={"task_id": task_id, "client_id": client.client_id},
                    )

            logger.debug(
                f"Event broadcast: {event_type.value}",
                extra={
                    "task_id": task_id,
                    "event_id": event_id,
                    "event_type": event_type.value,
                    "clients_notified": client_count,
                },
            )

            return event_id

    async def get_missed_events(
        self,
        task_id: str,
        last_event_id: int,
    ) -> List[SSEEvent]:
        """获取客户端断线期间错过的事件.

        Args:
            task_id: 任务ID
            last_event_id: 客户端最后接收的事件ID

        Returns:
            错过的事件列表
        """
        async with self._lock:
            events = self._events.get(task_id, [])
            missed = [e for e in events if e.id and int(e.id) > last_event_id]

            logger.debug(
                f"Retrieved missed events for reconnection",
                extra={
                    "task_id": task_id,
                    "last_event_id": last_event_id,
                    "missed_count": len(missed),
                },
            )

            return missed

    async def event_stream(
        self,
        task_id: str,
        client_id: str,
        last_event_id: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """生成 SSE 事件流.

        Args:
            task_id: 任务ID
            client_id: 客户端ID
            last_event_id: 最后接收的事件ID（断线重连）

        Yields:
            SSE 格式的事件字符串
        """
        client = await self.connect(task_id, client_id, last_event_id)

        try:
            # 发送连接成功事件
            yield self._format_event(
                SSEEvent(
                    event=SSEEventType.LOG,
                    data={
                        "task_id": task_id,
                        "message": "SSE连接已建立",
                        "timestamp": datetime.now().isoformat(),
                    },
                )
            )

            # 如果有断线重连，发送错过的事件
            if last_event_id is not None:
                missed_events = await self.get_missed_events(task_id, last_event_id)
                for event in missed_events:
                    yield self._format_event(event)

            # 持续发送事件
            heartbeat_task = asyncio.create_task(self._heartbeat_loop(client))

            try:
                while True:
                    try:
                        # 等待事件，超时后发送心跳
                        event = await asyncio.wait_for(
                            client.event_queue.get(),
                            timeout=self.heartbeat_interval,
                        )
                        yield self._format_event(event)

                        # 如果是 done 或 error 事件，结束流
                        if event.event in (SSEEventType.DONE, SSEEventType.ERROR):
                            break

                    except asyncio.TimeoutError:
                        # 发送心跳（作为注释，不触发客户端事件处理器）
                        yield f": heartbeat {datetime.now().isoformat()}\n\n"

            finally:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

        finally:
            await self.disconnect(client_id)

    async def _heartbeat_loop(self, client: SSEClient) -> None:
        """心跳循环.

        Args:
            client: 客户端实例
        """
        while True:
            await asyncio.sleep(self.heartbeat_interval)
            # 心跳通过主循环的超时机制处理

    def _format_event(self, event: SSEEvent) -> str:
        """格式化事件为 SSE 字符串.

        Args:
            event: SSE 事件

        Returns:
            SSE 格式的字符串
        """
        lines = []

        # 事件ID
        if event.id:
            lines.append(f"id: {event.id}")

        # 事件类型
        lines.append(f"event: {event.event.value}")

        # 事件数据
        if isinstance(event.data, dict):
            data_str = json.dumps(event.data, ensure_ascii=False)
        else:
            data_str = str(event.data)

        # SSE 数据可以有多行
        for line in data_str.split("\n"):
            lines.append(f"data: {line}")

        # 重试时间（可选）
        if event.retry:
            lines.append(f"retry: {event.retry}")

        # 空行表示事件结束
        lines.append("")

        return "\n".join(lines) + "\n"

    async def send_log(
        self,
        task_id: str,
        message: str,
        level: str = "info",
        node: Optional[str] = None,
    ) -> int:
        """发送日志事件.

        Args:
            task_id: 任务ID
            message: 日志消息
            level: 日志级别
            node: 当前节点

        Returns:
            事件ID
        """
        return await self.broadcast(
            task_id,
            SSEEventType.LOG,
            {
                "level": level,
                "message": message,
                "node": node,
                "timestamp": datetime.now().isoformat(),
            },
        )

    async def send_llm_output(
        self,
        task_id: str,
        content: str,
        node: Optional[str] = None,
        model: Optional[str] = None,
        is_complete: bool = False,
    ) -> int:
        """发送 LLM 输出事件.

        Args:
            task_id: 任务ID
            content: LLM 输出内容
            node: 当前节点
            model: 使用的模型
            is_complete: 是否完成

        Returns:
            事件ID
        """
        return await self.broadcast(
            task_id,
            SSEEventType.LLM,
            {
                "content": content,
                "node": node,
                "model": model,
                "is_complete": is_complete,
                "timestamp": datetime.now().isoformat(),
            },
        )

    async def send_progress(
        self,
        task_id: str,
        completed_count: int,
        total_nodes: int,
        current_node: Optional[str] = None,
        current_node_display: Optional[str] = None,
    ) -> int:
        """发送进度事件.

        Args:
            task_id: 任务ID
            completed_count: 已完成节点数
            total_nodes: 总节点数
            current_node: 当前节点
            current_node_display: 当前节点显示名

        Returns:
            事件ID
        """
        progress_percent = (
            (completed_count / total_nodes * 100) if total_nodes > 0 else 0
        )

        return await self.broadcast(
            task_id,
            SSEEventType.PROGRESS,
            {
                "task_id": task_id,
                "status": "running",
                "completed_count": completed_count,
                "total_nodes": total_nodes,
                "progress_text": f"{completed_count}/{total_nodes}",
                "progress_percent": round(progress_percent, 2),
                "current_node": current_node,
                "current_node_display": current_node_display,
            },
        )

    async def send_done(
        self,
        task_id: str,
        success: bool = True,
        message: str = "任务完成",
        output_file: Optional[str] = None,
        download_url: Optional[str] = None,
        processing_time: Optional[float] = None,
    ) -> int:
        """发送完成事件.

        Args:
            task_id: 任务ID
            success: 是否成功
            message: 消息
            output_file: 输出文件路径
            download_url: 下载链接
            processing_time: 处理时间

        Returns:
            事件ID
        """
        return await self.broadcast(
            task_id,
            SSEEventType.DONE,
            {
                "task_id": task_id,
                "success": success,
                "message": message,
                "output_file": output_file,
                "download_url": download_url,
                "processing_time": processing_time,
            },
        )

    async def send_error(
        self,
        task_id: str,
        error: str,
        node: Optional[str] = None,
        is_fatal: bool = True,
    ) -> int:
        """发送错误事件.

        Args:
            task_id: 任务ID
            error: 错误信息
            node: 发生错误的节点
            is_fatal: 是否致命错误

        Returns:
            事件ID
        """
        return await self.broadcast(
            task_id,
            SSEEventType.ERROR,
            {
                "task_id": task_id,
                "error": error,
                "node": node,
                "is_fatal": is_fatal,
            },
        )

    async def cleanup_task(self, task_id: str) -> None:
        """清理任务相关资源.

        Args:
            task_id: 任务ID
        """
        async with self._lock:
            # 断开所有客户端
            clients = self._clients.pop(task_id, set())
            for client in clients:
                self._client_map.pop(client.client_id, None)

            # 清理事件存储
            self._events.pop(task_id, None)
            self._event_counters.pop(task_id, None)

            logger.info(
                f"Cleaned up SSE resources for task",
                extra={
                    "task_id": task_id,
                    "disconnected_clients": len(clients),
                },
            )

    def get_client_count(self, task_id: str) -> int:
        """获取任务的客户端数量.

        Args:
            task_id: 任务ID

        Returns:
            客户端数量
        """
        return len(self._clients.get(task_id, set()))


# 全局 SSE 管理器实例
sse_manager = SSEManager()
