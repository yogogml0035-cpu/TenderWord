"""
通用 Word 操作节点模块

本模块包含所有招标类型共享的 Word 文档操作节点函数。
这些节点函数可以被不同的招标类型（XJCG、GNGK 等）复用。

节点列表：
- prepare_template: 准备 Word 模板
- replace_content: 替换内容
- generate_polished_text: 生成修改文本（根据 tender_type 选择对应的 prompt）
- host_agent_generate: 使用 DeepAgents 智能体生成修改文本
- get_comments: 从送审稿 Word 文档中提取批注内容
- get_rewrite_comments: 在 rewrite 前提取锚点区间内的原批注
- copy_comments: 从送审稿按内容锚定复制批注到模板
- generate_comments: 基于修改文本与计划使用 LLM 生成批注指令
- extract_tender_params: 提取招标参数内容（从锚点之间）
- delete_tender_param: 删除招标参数内容（从锚点之间）
- update_word: 更新 Word 文档（插入修改文本）
"""

from backend.nodes.common_word_nodes.prepare_template import prepare_template
from backend.nodes.common_word_nodes.replace_content import replace_content
from backend.nodes.common_word_nodes.generate_polished_text import (
    generate_polished_text,
)
from backend.nodes.common_word_nodes.host_agent_generate import host_agent_generate
from backend.nodes.common_word_nodes.get_comments import get_comments
from backend.nodes.common_word_nodes.get_rewrite_comments import get_rewrite_comments
from backend.nodes.common_word_nodes.copy_comments import copy_comments
from backend.nodes.common_word_nodes.generate_comments import generate_comments
from backend.nodes.common_word_nodes.extract_tender_params import extract_tender_params
from backend.nodes.common_word_nodes.delete_tender_param import delete_tender_param
from backend.nodes.common_word_nodes.update_word import update_word
from backend.nodes.common_word_nodes.get_replacements_core import (
    ExtractorSpec,
    ReplacementFieldSpec,
    run_get_replacements,
)

__all__ = [
    "prepare_template",
    "replace_content",
    "generate_polished_text",
    "host_agent_generate",
    "get_comments",
    "get_rewrite_comments",
    "copy_comments",
    "generate_comments",
    "extract_tender_params",
    "delete_tender_param",
    "update_word",
    "ExtractorSpec",
    "ReplacementFieldSpec",
    "run_get_replacements",
]
