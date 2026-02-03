# XJCG 模块只保留 prompt 定义
# 所有通用节点已移动到 nodes/common_word_nodes/
from nodes.xjcg_word_nodes.prepare_template import prepare_template
from nodes.xjcg_word_nodes.delete_tender_param import delete_tender_param
from nodes.xjcg_word_nodes.get_replacements import get_replacements
from nodes.xjcg_word_nodes.replace_content import replace_content
from nodes.xjcg_word_nodes.update_word import update_word
from nodes.xjcg_word_nodes.extract_tender_params import extract_tender_params
from nodes.xjcg_word_nodes.generate_polished_text import generate_polished_text

__all__ = [
    "prepare_template",
    "extract_tender_params",
    "delete_tender_param",
    "get_replacements",
    "replace_content",
    "update_word",
    "generate_polished_text",
]