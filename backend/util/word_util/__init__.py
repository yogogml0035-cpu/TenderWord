"""
Word 工具模块

提供 Word COM 操作相关的工具函数和类，包括：
- Word 应用程序管理
- Word COM 并发管理
- Word 文档内容提取
- Word 文档检查
- Word 诊断工具
- Word 常量定义
"""

from backend.util.word_util.word_application_util import (
    create_word_application,
    close_word_application,
    open_document_with_retry,
    save_document_with_retry,
    unprotect_document,
)

from backend.util.word_util.word_com_manager import (
    com_lock,
    is_rpc_error,
    calculate_retry_delay,
    MAX_RETRIES,
    RPC_ERROR_CODES,
    ComLockAcquisitionError,
)

from backend.util.word_util.word_extraction_utils import (
    extract_text_from_word_file,
    extract_content_with_tables,
    extract_table_as_text,
    extract_text_with_list_numbers,
    extract_text_with_superscript_subscript,
)

from backend.util.word_util.word_document_inspector import (
    CommentInfo,
    StrikethroughInfo,
    NonBlackFontInfo,
    DocumentAnalysisResult,
    WordDocumentInspector,
)

from backend.util.word_util.word_diagnostics import (
    check_win32com_installation,
    check_word_installation,
    get_word_version_info,
    diagnose_word_com_environment,
    format_diagnosis_report,
    WIN32COM_AVAILABLE,
)

from backend.util.word_util.word_constants import (
    wdFindStop,
    wdCollapseStart,
    wdCollapseEnd,
    wdGoToPage,
    wdGoToAbsolute,
    wdActiveEndPageNumber,
    wdWithInTable,
    wdLineSpace1pt5,
    wdOutlineLevelBodyText,
)

from backend.util.word_util.anchor_utils import (
    find_anchor_range,
    find_anchor_with_find,
    _iter_paragraph_hits,
    _pick_anchor,
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
    # word_document_inspector
    "CommentInfo",
    "StrikethroughInfo",
    "NonBlackFontInfo",
    "DocumentAnalysisResult",
    "WordDocumentInspector",
    # word_diagnostics
    "check_win32com_installation",
    "check_word_installation",
    "get_word_version_info",
    "diagnose_word_com_environment",
    "format_diagnosis_report",
    "WIN32COM_AVAILABLE",
    # word_constants
    "wdFindStop",
    "wdCollapseStart",
    "wdCollapseEnd",
    "wdGoToPage",
    "wdGoToAbsolute",
    "wdActiveEndPageNumber",
    "wdWithInTable",
    "wdLineSpace1pt5",
    "wdOutlineLevelBodyText",
    # anchor_utils
    "find_anchor_range",
    "find_anchor_with_find",
    "_iter_paragraph_hits",
    "_pick_anchor",
]
