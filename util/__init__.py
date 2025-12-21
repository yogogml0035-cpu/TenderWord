"""
工具函数模块

包含：
- word_application_util: Word 应用程序创建和管理工具
- word_com_manager: COM 并发访问管理器
- word_extraction_utils: Word 文档内容提取工具
- llm_stream_utils: LLM 流式响应工具（心跳超时检测）
"""

from util.word_application_util import (
    create_word_application,
    close_word_application,
    open_document_with_retry,
    save_document_with_retry,
)

from util.word_com_manager import (
    com_lock,
    com_session,
    is_rpc_error,
    calculate_retry_delay,
    with_com_retry,
    WordComOperation,
    MAX_RETRIES,
    RPC_ERROR_CODES,
)

from util.word_extraction_utils import (
    extract_text_from_word_file,
    extract_content_with_tables,
    extract_table_as_text,
    extract_text_with_list_numbers,
    extract_text_with_superscript_subscript,
)

from util.llm_stream_utils import (
    LLMTimeoutError,
    HeartbeatMonitor,
    StreamCallbacks,
    stream_llm_completion,
)

__all__ = [
    # word_application_util
    'create_word_application',
    'close_word_application',
    'open_document_with_retry',
    'save_document_with_retry',
    # word_com_manager
    'com_lock',
    'com_session',
    'is_rpc_error',
    'calculate_retry_delay',
    'with_com_retry',
    'WordComOperation',
    'MAX_RETRIES',
    'RPC_ERROR_CODES',
    # word_extraction_utils
    'extract_text_from_word_file',
    'extract_content_with_tables',
    'extract_table_as_text',
    'extract_text_with_list_numbers',
    'extract_text_with_superscript_subscript',
    # llm_stream_utils
    'LLMTimeoutError',
    'HeartbeatMonitor',
    'StreamCallbacks',
    'stream_llm_completion',
]
