# XJCG 目录仅保留“带前缀”的差异化节点（xjcg_*）与 prompt。
# 通用节点统一放在 nodes/common_word_nodes 中实现，并在此处 re-export，
# 以保持外部导入路径 `from nodes.xjcg_word_nodes import ...` 不变。

from nodes.common_word_nodes import (
    generate_polished_text,
    prepare_template,
    replace_content,
)

from nodes.xjcg_word_nodes.xjcg_get_replacements import get_replacements
from nodes.xjcg_word_nodes.xjcg_delete_tender_param import delete_tender_param
from nodes.xjcg_word_nodes.xjcg_extract_tender_params import extract_tender_params
from nodes.xjcg_word_nodes.xjcg_update_word import update_word

__all__ = [
    "prepare_template",
    "extract_tender_params",
    "delete_tender_param",
    "get_replacements",
    "replace_content",
    "update_word",
    "generate_polished_text",
]