"""
通用工具模块

提供非 Word 相关的通用工具函数，包括：
- LLM 流式调用工具
- 招标数据获取工具
"""

from util.common_util.llm_stream_utils import (
    LLMTimeoutError,
    HeartbeatMonitor,
    StreamCallbacks,
    ModelConfig,
    MODEL_CONFIGS,
    ensure_llm_env,
    stream_llm_completion,
)

from util.common_util.fetch_tender_data import (
    fetch_tender_data,
)

__all__ = [
    # llm_stream_utils
    "LLMTimeoutError",
    "HeartbeatMonitor",
    "StreamCallbacks",
    "ModelConfig",
    "MODEL_CONFIGS",
    "ensure_llm_env",
    "stream_llm_completion",
    # fetch_tender_data
    "fetch_tender_data",
]
