"""
通用工具模块

提供非 Word 相关的通用工具函数，包括：
- LLM 流式调用工具
- 招标数据获取工具
"""

from backend.util.common_util.llm_stream_utils import (
    LLMTimeoutError,
    HeartbeatMonitor,
    StreamCallbacks,
    ModelConfig,
    MODEL_CONFIGS,
    ensure_llm_env,
    get_llm_timeout_seconds,
    stream_llm_completion,
)

from backend.util.common_util.fetch_tender_data import (
    fetch_tender_data,
)
from backend.util.common_util.template_candidates import (
    OLD_TEMPLATE_MESSAGE,
    INVALID_TEMPLATE_YEAR_MESSAGE,
    TemplateDownloadTooLargeError,
    build_template_download_name,
    derive_template_blocked_reason,
    extract_template_year,
    fetch_template_candidates,
    fetch_template_file,
    infer_remote_filename,
    iter_response_content,
    read_template_response_content,
    validate_template_download_url,
)
from backend.util.common_util.upload_storage import (
    ensure_upload_dir,
    generate_unique_filename,
    persist_file_bytes,
    validate_file_extension,
    validate_file_size,
)

__all__ = [
    # llm_stream_utils
    "LLMTimeoutError",
    "HeartbeatMonitor",
    "StreamCallbacks",
    "ModelConfig",
    "MODEL_CONFIGS",
    "ensure_llm_env",
    "get_llm_timeout_seconds",
    "stream_llm_completion",
    # fetch_tender_data
    "fetch_tender_data",
    # template_candidates
    "OLD_TEMPLATE_MESSAGE",
    "INVALID_TEMPLATE_YEAR_MESSAGE",
    "TemplateDownloadTooLargeError",
    "build_template_download_name",
    "derive_template_blocked_reason",
    "extract_template_year",
    "fetch_template_candidates",
    "fetch_template_file",
    "infer_remote_filename",
    "iter_response_content",
    "read_template_response_content",
    "validate_template_download_url",
    # upload_storage
    "ensure_upload_dir",
    "generate_unique_filename",
    "persist_file_bytes",
    "validate_file_extension",
    "validate_file_size",
]
