"""
通用 Word 操作节点模块

本模块包含所有招标类型共享的 Word 文档操作节点函数。
这些节点函数可以被不同的招标类型（XJCG、GNGK 等）复用。

节点列表：
- prepare_template: 准备 Word 模板
- extract_tender_params: 提取招标参数
- delete_tender_param: 删除招标参数
- get_replacements: 获取替换内容
- replace_content: 替换内容
- update_word: 更新 Word 文档
- generate_polished_text: 生成润色文本（根据 tender_type 选择对应的 prompt）
"""

from nodes.common_word_nodes.prepare_template import prepare_template
from nodes.common_word_nodes.delete_tender_param import delete_tender_param
from nodes.common_word_nodes.get_replacements import get_replacements
from nodes.common_word_nodes.replace_content import replace_content
from nodes.common_word_nodes.update_word import update_word
from nodes.common_word_nodes.generate_polished_text import generate_polished_text

__all__ = [
    "prepare_template",
    "delete_tender_param",
    "get_replacements",
    "replace_content",
    "update_word",
    "generate_polished_text",
]
