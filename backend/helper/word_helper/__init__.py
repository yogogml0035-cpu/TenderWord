"""
word_helper — 面向多节点共享的 Word 文档业务操作层。

与 backend.util.word_util（纯技术工具：COM 封装、常量、底层 API）不同，
本包封装了从各 delete_tender_param / update_word 节点中提取的可复用业务逻辑。
"""

from backend.helper.word_helper.range_utils import (
    is_range_locked,
    is_locked_exception,
    range_overlaps,
    is_protected_range,
    find_editable_insertion_pos,
    find_next_editable_pos,
    find_next_editable_pos_bounded,
    find_prev_editable_pos,
    find_prev_editable_pos_bounded,
    ensure_editable_insert_range,
    find_safe_insert_position,
)

from backend.helper.word_helper.text_parsing import (
    is_table_separator_line,
    parse_table_row,
    looks_like_table_row,
    parse_table_block,
    convert_lines_to_items,
    split_text_by_keywords,
)

from backend.helper.word_helper.protected_fields import (
    canonicalize_protected_field_marker,
    extract_protected_field_name,
    normalize_protected_field_markers,
    match_protected_field_line,
    normalize_protected_field_line,
    normalize_protected_field_text,
    find_suspicious_protected_field_lines,
    collect_suspicious_protected_field_hits,
    format_missing_protected_field_error,
    build_protected_field_scan_ranges,
    normalize_protected_field_paragraphs,
    scan_protected_fields_in_range,
    collect_protected_fields,
    refresh_protected_fields,
    validate_required_protected_fields,
    validate_profile_required_protected_fields,
    collect_profile_protected_fields,
    refresh_profile_protected_fields,
    resolve_block_flow,
    refind_protected_paragraph,
    insert_prefix_before_keyword,
    update_protected_field,
)

from backend.helper.word_helper.content_ops import (
    GENERATED_TEXT_FONT_RESET_VERSION,
    reset_generated_text_font_format,
    apply_standard_insert_format,
    insert_content_with_formatting,
    insert_table_with_formatting,
    insert_items_inline_at_end_of_paragraph,
)

from backend.helper.word_helper.paragraph_boundary_ops import (
    uses_wide_scan_window,
    find_paragraph_containing_any,
    find_first_visible_insert_offset,
    insert_paragraph_break_before_paragraph,
    ensure_paragraph_break_after_paragraph,
)

from backend.helper.word_helper.cleanup_ops import (
    normalize_cleanup_text,
    is_effectively_empty_text,
    row_is_empty,
    trim_table_trailing_empty_rows,
    cleanup_blank_paragraphs,
    cleanup_empty_tables,
    multi_pass_cleanup,
)
from backend.helper.word_helper.semantic_matcher import (
    clean_semantic_text,
    normalize_semantic_text,
    semantic_similarity,
    semantic_similarity_norm,
)
from backend.helper.word_helper.inline_style_ops import (
    InlineStyleFlags,
    InlineStyleContainerLocator,
    InlineStyleFragment,
    InlineStyleWritebackIssue,
    InlineStyleWritebackResult,
    build_inline_style_fragments_from_text_runs,
    build_inline_style_extraction_logs,
    extract_inline_style_fragments,
    apply_inline_style_fragments,
    summarize_style_writeback_result,
    build_style_writeback_summary_payload,
)

__all__ = [
    # range_utils
    "is_range_locked",
    "is_locked_exception",
    "range_overlaps",
    "is_protected_range",
    "find_editable_insertion_pos",
    "find_next_editable_pos",
    "find_next_editable_pos_bounded",
    "find_prev_editable_pos",
    "find_prev_editable_pos_bounded",
    "ensure_editable_insert_range",
    "find_safe_insert_position",
    # text_parsing
    "is_table_separator_line",
    "parse_table_row",
    "looks_like_table_row",
    "parse_table_block",
    "convert_lines_to_items",
    "split_text_by_keywords",
    # protected_fields
    "canonicalize_protected_field_marker",
    "extract_protected_field_name",
    "normalize_protected_field_markers",
    "match_protected_field_line",
    "normalize_protected_field_line",
    "normalize_protected_field_text",
    "find_suspicious_protected_field_lines",
    "collect_suspicious_protected_field_hits",
    "format_missing_protected_field_error",
    "build_protected_field_scan_ranges",
    "normalize_protected_field_paragraphs",
    "scan_protected_fields_in_range",
    "collect_protected_fields",
    "refresh_protected_fields",
    "validate_required_protected_fields",
    "validate_profile_required_protected_fields",
    "collect_profile_protected_fields",
    "refresh_profile_protected_fields",
    "resolve_block_flow",
    "refind_protected_paragraph",
    "insert_prefix_before_keyword",
    "update_protected_field",
    # content_ops
    "GENERATED_TEXT_FONT_RESET_VERSION",
    "reset_generated_text_font_format",
    "apply_standard_insert_format",
    "insert_content_with_formatting",
    "insert_table_with_formatting",
    "insert_items_inline_at_end_of_paragraph",
    # paragraph_boundary_ops
    "uses_wide_scan_window",
    "find_paragraph_containing_any",
    "find_first_visible_insert_offset",
    "insert_paragraph_break_before_paragraph",
    "ensure_paragraph_break_after_paragraph",
    # cleanup_ops
    "normalize_cleanup_text",
    "is_effectively_empty_text",
    "row_is_empty",
    "trim_table_trailing_empty_rows",
    "cleanup_blank_paragraphs",
    "cleanup_empty_tables",
    "multi_pass_cleanup",
    # semantic_matcher
    "clean_semantic_text",
    "normalize_semantic_text",
    "semantic_similarity",
    "semantic_similarity_norm",
    # inline_style_ops
    "InlineStyleFlags",
    "InlineStyleContainerLocator",
    "InlineStyleFragment",
    "InlineStyleWritebackIssue",
    "InlineStyleWritebackResult",
    "build_inline_style_fragments_from_text_runs",
    "build_inline_style_extraction_logs",
    "extract_inline_style_fragments",
    "apply_inline_style_fragments",
    "summarize_style_writeback_result",
    "build_style_writeback_summary_payload",
]
