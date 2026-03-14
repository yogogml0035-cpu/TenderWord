"""
工具函数模块

包含：
- word_util: Word 相关工具函数和类
- log_util: 日志工具
- common_util: 通用工具（LLM 流式调用、招标数据获取）

对外导出：
仅保留当前仓库仍支持的工具函数入口。
"""

# Word 工具（向后兼容导出）
from backend.util.word_util import (
    # word_application_util
    create_word_application,
    close_word_application,
    open_document_with_retry,
    save_document_with_retry,
    unprotect_document,
    # word_com_manager
    com_lock,
    is_rpc_error,
    calculate_retry_delay,
    MAX_RETRIES,
    RPC_ERROR_CODES,
    ComLockAcquisitionError,
    # word_extraction_utils
    extract_text_from_word_file,
    extract_content_with_tables,
    extract_table_as_text,
    extract_text_with_list_numbers,
    extract_text_with_superscript_subscript,
)

# 日志工具导出
from backend.util.log_util import (
    log_generate_task_success,
)

# 通用工具（向后兼容导出）
from backend.util.common_util import (
    # llm_stream_utils
    LLMTimeoutError,
    HeartbeatMonitor,
    StreamCallbacks,
    stream_llm_completion,
    # fetch_tender_data
    fetch_tender_data,
)

__all__ = [
    # word_application_util
    "create_word_application",
    "close_word_application",
    "open_document_with_retry",
    "save_document_with_retry",
    "unprotect_document",
    # word_com_manager
    "com_lock",
    "is_rpc_error",
    "calculate_retry_delay",
    "MAX_RETRIES",
    "RPC_ERROR_CODES",
    "ComLockAcquisitionError",
    # word_extraction_utils
    "extract_text_from_word_file",
    "extract_content_with_tables",
    "extract_table_as_text",
    "extract_text_with_list_numbers",
    "extract_text_with_superscript_subscript",
    # log_util
    "log_generate_task_success",
    # llm_stream_utils
    "LLMTimeoutError",
    "HeartbeatMonitor",
    "StreamCallbacks",
    "stream_llm_completion",
    # fetch_tender_data
    "fetch_tender_data",
]
