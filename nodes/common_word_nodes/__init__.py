"""
通用 Word 操作节点模块

本模块包含所有招标类型共享的 Word 文档操作节点函数。
这些节点函数可以被不同的招标类型（XJCG、GNGK 等）复用。

节点列表：
- prepare_template: 准备 Word 模板
- replace_content: 替换内容
- generate_polished_text: 生成润色文本（根据 tender_type 选择对应的 prompt）
- get_comments: 从送审稿 Word 文档中提取批注内容
"""

from nodes.common_word_nodes.prepare_template import prepare_template
from nodes.common_word_nodes.replace_content import replace_content
from nodes.common_word_nodes.generate_polished_text import generate_polished_text
from nodes.common_word_nodes.get_comments import get_comments

__all__ = [
    "prepare_template",
    "replace_content",
    "generate_polished_text",
    "get_comments",
]
