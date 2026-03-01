"""
工具函数模块

包含：
- word_util: Word 相关工具函数和类
- log_util: 日志工具
- common_util: 通用工具（LLM 流式调用、招标数据获取）

向后兼容导出：
以下导出保持与重构前相同的 API，现有代码无需修改即可继续使用。
"""

# Word 工具（向后兼容导出）
from util.word_util import (
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

# 日志工具（向后兼容导出）
from util.log_util import (
    logger,
    log_task_start,
    log_task_end,
)

# 通用工具（向后兼容导出）
from util.common_util import (
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
    "logger",
    "log_task_start",
    "log_task_end",
    # llm_stream_utils
    "LLMTimeoutError",
    "HeartbeatMonitor",
    "StreamCallbacks",
    "stream_llm_completion",
    # fetch_tender_data
    "fetch_tender_data",
]
