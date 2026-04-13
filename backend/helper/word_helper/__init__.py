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
    scan_protected_fields_in_range,
    collect_protected_fields,
    refresh_protected_fields,
    validate_required_protected_fields,
    resolve_block_flow,
    refind_protected_paragraph,
    insert_prefix_before_keyword,
    update_protected_field,
)

from backend.helper.word_helper.content_ops import (
    apply_standard_insert_format,
    insert_content_with_formatting,
    insert_table_with_formatting,
    insert_items_inline_at_end_of_paragraph,
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
    "scan_protected_fields_in_range",
    "collect_protected_fields",
    "refresh_protected_fields",
    "validate_required_protected_fields",
    "resolve_block_flow",
    "refind_protected_paragraph",
    "insert_prefix_before_keyword",
    "update_protected_field",
    # content_ops
    "apply_standard_insert_format",
    "insert_content_with_formatting",
    "insert_table_with_formatting",
    "insert_items_inline_at_end_of_paragraph",
    # cleanup_ops
    "normalize_cleanup_text",
    "is_effectively_empty_text",
    "row_is_empty",
    "trim_table_trailing_empty_rows",
    "cleanup_blank_paragraphs",
    "cleanup_empty_tables",
    "multi_pass_cleanup",
]
