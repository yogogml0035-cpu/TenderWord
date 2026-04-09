from __future__ import annotations

import asyncio
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from backend.config.settings import settings
from backend.util.log_util.progress_log import progress_log


ENV_SETUP_HINT = (
    "请在系统环境变量或 backend/.env 中补齐后重试（可参考 backend/.env.example）。"
)


def get_llm_timeout_seconds(timeout_seconds: Optional[int] = None) -> int:
    """返回有效的 LLM 流式超时时间（秒）。"""
    effective_timeout = (
        settings.LLM_STREAM_TIMEOUT_SECONDS
        if timeout_seconds is None
        else timeout_seconds
    )
    return max(int(effective_timeout), 1)


class LLMTimeoutError(Exception):
    """大模型响应超时异常"""

    def __init__(self, model_name: str, timeout_seconds: int):
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"大模型响应超时失败（{model_name} 在 {timeout_seconds} 秒内未响应），请尝试其他模型或者重新生成"
        )


class HeartbeatMonitor:
    """心跳监控器：用于检测流式响应是否超时

    工作原理：
    1. 启动一个后台线程，每隔 check_interval 秒检查一次心跳
    2. 每次收到新的 chunk 时调用 beat() 更新心跳时间
    3. 如果超过 timeout_seconds 秒没有收到新心跳，则标记为超时
    """

    def __init__(
        self, model_name: str, timeout_seconds: int = 10, check_interval: float = 3.0
    ):
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self.check_interval = check_interval
        self._last_heartbeat = time.time()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._timeout_occurred = False
        self._monitor_thread: Optional[threading.Thread] = None

    def beat(self):
        """更新心跳时间（每次收到新 chunk 时调用）"""
        with self._lock:
            self._last_heartbeat = time.time()

    def start(self):
        """启动心跳检测线程"""
        self._stop_event.clear()
        self._timeout_occurred = False
        self._last_heartbeat = time.time()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def stop(self):
        """停止心跳检测"""
        self._stop_event.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=3.0)

    def _monitor_loop(self):
        """心跳检测循环：每隔 check_interval 秒检查一次"""
        while not self._stop_event.is_set():
            # 等待 check_interval 秒或者被停止
            if self._stop_event.wait(self.check_interval):
                break  # 被停止了

            # 检查心跳间隔
            with self._lock:
                elapsed = time.time() - self._last_heartbeat

            if elapsed > self.timeout_seconds:
                progress_log.warning(
                    f"{self.model_name} 流式响应超时（{elapsed:.1f}秒未收到新响应）"
                )
                self._timeout_occurred = True
                break

    @property
    def is_timeout(self) -> bool:
        """检查是否发生超时"""
        return self._timeout_occurred

    def check_and_raise(self):
        """检查是否超时，如果超时则抛出异常"""
        if self._timeout_occurred:
            raise LLMTimeoutError(self.model_name, self.timeout_seconds)


@dataclass
class StreamCallbacks:
    """流式调用的回调函数集合"""

    on_chunk: Optional[Callable[[str], None]] = (
        None  # 收到新 chunk 时的回调（用于日志输出）
    )
    on_update: Optional[Callable[[str], None]] = (
        None  # 内容更新时的回调（用于流式推送完整内容）
    )
    on_request_messages: Optional[Callable[[list[dict[str, Any]]], None]] = (
        None  # 请求 messages 已组装完成时的回调
    )


@dataclass
class ModelConfig:
    """模型配置"""

    display_name: str  # 显示名称
    api_key_env: str  # API Key 环境变量名
    base_url_env: str  # Base URL 环境变量名
    model_env: str  # 模型名称环境变量名
    extra_params: dict[str, Any] = field(
        default_factory=dict
    )  # 额外参数 (max_tokens, temperature 等)
    extra_body: dict[str, Any] = field(default_factory=dict)  # extra_body 参数
    stream_options: dict[str, Any] = field(default_factory=dict)  # stream_options 参数


# 模型配置映射
MODEL_CONFIGS: dict[str, ModelConfig] = {
    "doubao": ModelConfig(
        display_name="豆包 (Doubao)",
        api_key_env="ARK_API_KEY",
        base_url_env="ARK_BASE_URL",
        model_env="DOUBAO_MODEL",
        extra_params={"max_tokens": 32768, "temperature": 0.1},
        extra_body={"thinking": {"type": "disabled"}},
    ),
    "qwen": ModelConfig(
        display_name="千问 (Qwen)",
        api_key_env="DASHSCOPE_API_KEY",
        base_url_env="DASHSCOPE_BASE_URL",
        model_env="QWEN_MODEL",
        stream_options={"include_usage": True},
        extra_params={"max_tokens": 32768, "temperature": 0.1},
        extra_body={"enable_thinking": False},
    ),
    "deepseek": ModelConfig(
        display_name="深度求索 (DeepSeek)",
        api_key_env="DEEPSEEK_API_KEY",
        base_url_env="DEEPSEEK_BASE_URL",
        model_env="DEEPSEEK_MODEL",
        extra_params={"max_tokens": 8192, "temperature": 0.1},
    ),
}


def ensure_llm_env(model_provider: str) -> None:
    """检查 LLM 配置是否完整。"""
    config = MODEL_CONFIGS.get(model_provider, MODEL_CONFIGS["deepseek"])
    llm_config = settings.get_llm_config(model_provider)
    missing: list[str] = []
    
    if not llm_config.get("api_key"):
        missing.append(config.api_key_env)
    if not llm_config.get("base_url"):
        missing.append(config.base_url_env)
    if not llm_config.get("model"):
        missing.append(config.model_env)
        
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(
            f"{config.display_name} 配置缺失：{missing_text} 未设置。"
            f"{ENV_SETUP_HINT}"
        )


async def stream_llm_completion(
    model_provider: str,
    prompt: Optional[str] = None,
    system_prompt: Optional[str] = None,
    user_prompt: Optional[str] = None,
    callbacks: Optional[StreamCallbacks] = None,
    model_override: Optional[str] = None,
    extra_params_override: Optional[dict[str, Any]] = None,
    timeout_seconds: Optional[int] = None,
    check_interval: float = 3.0,
) -> str:
    """
    统一的 LLM 流式调用接口

    Args:
        model_provider: 模型提供商，支持 "doubao", "qwen", "deepseek"
        prompt: 用户提示词（兼容旧版本，如果提供则忽略 system_prompt 和 user_prompt）
        system_prompt: 系统提示词（可选）
        user_prompt: 用户提示词（可选）
        callbacks: 回调函数集合
        timeout_seconds: 超时时间（秒），未传时读取配置
        check_interval: 心跳检查间隔（秒），默认 3 秒

    Returns:
        生成的完整文本内容

    Raises:
        LLMTimeoutError: 响应超时
        ValueError: 配置错误（如 API Key 未设置）
        Exception: 其他调用错误
    """
    # 获取模型配置，默认使用 deepseek
    config = MODEL_CONFIGS.get(model_provider, MODEL_CONFIGS["deepseek"])
    ensure_llm_env(model_provider)
    effective_timeout_seconds = get_llm_timeout_seconds(timeout_seconds)

    callbacks = callbacks or StreamCallbacks()
    display_name = config.display_name
    if model_override:
        display_name = f"{display_name} ({model_override})"
    heartbeat = HeartbeatMonitor(
        display_name,
        timeout_seconds=effective_timeout_seconds,
        check_interval=check_interval,
    )

    content_parts: list[str] = []

    def _on_chunk_received(chunk_text: str):
        """处理收到的 chunk"""
        content_parts.append(chunk_text)
        if callbacks.on_chunk:
            callbacks.on_chunk(chunk_text)
        if callbacks.on_update:
            callbacks.on_update("".join(content_parts))

    try:
        heartbeat.start()
        content = await _stream_openai_compatible(
            model_provider=model_provider,
            prompt=prompt,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            config=config,
            model_override=model_override,
            extra_params_override=extra_params_override,
            timeout_seconds=effective_timeout_seconds,
            heartbeat=heartbeat,
            on_chunk=_on_chunk_received,
            on_request_messages=callbacks.on_request_messages,
        )
        progress_log.debug("LLM 流式响应完成")
        return content

    except LLMTimeoutError:
        raise
    except Exception as e:
        progress_log.error(f"{config.display_name} 流式调用失败: {e}")
        raise
    finally:
        heartbeat.stop()


async def _stream_openai_compatible(
    model_provider: str,
    config: ModelConfig,
    model_override: Optional[str],
    extra_params_override: Optional[dict[str, Any]],
    timeout_seconds: int,
    heartbeat: HeartbeatMonitor,
    on_chunk: Callable[[str], None],
    on_request_messages: Optional[Callable[[list[dict[str, Any]]], None]],
    prompt: Optional[str] = None,
    system_prompt: Optional[str] = None,
    user_prompt: Optional[str] = None,
) -> str:
    """OpenAI 兼容接口的通用流式调用实现"""
    from openai import AsyncOpenAI
    from openai import (
        APIConnectionError,
        APITimeoutError,
        InternalServerError,
        RateLimitError,
    )
    import httpx

    llm_config = settings.get_llm_config(model_provider)
    api_key = llm_config.get("api_key")
    base_url = llm_config.get("base_url")
    model_name = llm_config.get("model")

    missing: list[str] = []
    if not api_key or not str(api_key).strip():
        missing.append(config.api_key_env)
    if not base_url or not str(base_url).strip():
        missing.append(config.base_url_env)
    if not model_name or not str(model_name).strip():
        missing.append(config.model_env)
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(
            f"{config.display_name} 配置缺失：{missing_text} 未设置。"
            f"{ENV_SETUP_HINT}"
        )

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=httpx.Timeout(timeout_seconds, connect=10.0),
        max_retries=0,
    )

    # 构建消息列表
    messages = []

    # 如果提供了 prompt，则只使用 prompt 作为 user 消息
    if prompt:
        messages.append({"role": "user", "content": prompt})
    else:
        # 分别处理 system_prompt 和 user_prompt
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if user_prompt:
            messages.append({"role": "user", "content": user_prompt})

        # 如果两者都没有提供，抛出错误
        if not messages:
            raise ValueError(
                "必须提供 prompt 或者 system_prompt/user_prompt 中的至少一个"
            )

    if on_request_messages:
        try:
            on_request_messages([dict(message) for message in messages])
        except Exception as callback_error:
            progress_log.debug(f"请求 messages 回调失败: {callback_error}")

    # 构建请求参数
    create_params: dict[str, Any] = {
        "model": model_override or model_name,
        "messages": messages,
        "stream": True,
        **config.extra_params,  # max_tokens, temperature 等
    }
    if extra_params_override:
        create_params.update(extra_params_override)

    # 添加可选参数
    if config.stream_options:
        create_params["stream_options"] = config.stream_options
    if config.extra_body:
        create_params["extra_body"] = config.extra_body

    max_attempts = 3
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        parts: list[str] = []
        try:
            completion = await client.chat.completions.create(**create_params)

            async for chunk in completion:
                heartbeat.check_and_raise()
                heartbeat.beat()

                if hasattr(chunk, "choices") and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, "content") and delta.content:
                        chunk_text = delta.content
                        parts.append(chunk_text)
                        on_chunk(chunk_text)

            return "".join(parts)

        except (httpx.ReadTimeout, APITimeoutError) as e:
            last_error = e
            if attempt >= max_attempts:
                raise LLMTimeoutError(heartbeat.model_name, timeout_seconds) from e
        except (
            httpx.RemoteProtocolError,
            httpx.ReadError,
            httpx.WriteError,
            httpx.ConnectError,
            httpx.ConnectTimeout,
            APIConnectionError,
            InternalServerError,
            RateLimitError,
        ) as e:
            last_error = e
            if attempt >= max_attempts:
                raise
        except Exception as e:
            last_error = e
            raise

        await asyncio.sleep(min(2 ** (attempt - 1), 8) + random.random() * 0.25)

    raise last_error or RuntimeError("streaming failed")
