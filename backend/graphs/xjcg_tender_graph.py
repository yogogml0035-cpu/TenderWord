"""
询价采购文档生成 Graph 模块

本模块定义了 XjcgTenderGraph 类，用于构建和执行询价采购文档生成的工作流。

主要功能：
1. 准备 Word 模板
2. 提取招标参数
3. 执行 Word 操作子图（删除、获取替换、替换内容）
4. 生成修改文本（LLM 调用）
5. 更新 Word 文档

工作流结构：
    START
      ↓
    prepare_template
      ↓           ↓                  ↓
    get_comments (若上传送审稿)  extract_tender_params  copy_comments (若上传送审稿)
      ↓           ↓                  ↓
      └───────────┴──────────────────┴───────────┐
                              ↓         ↓
                  word_operations_subgraph   generate_polished_text (LLM)
                              ↓         ↓
                              ↓    (若上传送审稿)
                              ↓   generate_comments (LLM)
                              ↓         ↓ (否则跳过)
                              └─────────┴──→ update_word
                                            ↓
                                           END

需求引用：
- 需求 2.1: 作为开发者，我希望能够轻松创建新的 Graph
- 需求 3.3: Graph 定义迁移

使用示例：
    from backend.graphs import XjcgTenderGraph

    # 创建 graph 实例
    graph = XjcgTenderGraph()

    # 准备初始状态
    initial_state = {
        "origin_tender_path": "path/to/template.doc",
        "tender_param_path": "path/to/params.docx",
        "project_name": "项目名称",
        # ... 其他字段
    }

    # 同步执行
    result, elapsed = graph.invoke(initial_state)

    # 异步执行
    result, elapsed = await graph.ainvoke(initial_state, config={
        "configurable": {
            "task_id": "task_123",
            "model_provider": "deepseek"
        }
    })
"""

from __future__ import annotations
from typing import Callable

from backend.graphs.base_graph import StandardTenderWorkflowGraph
from backend.states import XjcgTenderGraphState
from backend.nodes.common_word_nodes import (
    prepare_template,
    generate_polished_text,
    replace_content,
    get_comments,
    copy_comments,
    generate_comments,
    delete_tender_param,
    update_word,
)
from backend.nodes.common_word_nodes import extract_tender_params
from backend.nodes.xjcg_word_nodes import get_replacements


class XjcgTenderGraph(StandardTenderWorkflowGraph):
    """
    询价采购文档生成 Graph

    继承自 BaseGraph，自动获得以下功能：
    - 跨进程文件锁（保护 Word COM 操作）
    - 节点进度追踪
    - 任务取消检查
    - 同步/异步执行方法

    属性：
        无额外属性

    方法：
        get_state_class(): 返回 XjcgTenderGraphState 类型
        build_graph(): 构建询价采购文档生成的工作流
        _build_word_operations_subgraph(): 构建 Word 操作子图（私有方法）
    """

    STATE_CLS = XjcgTenderGraphState

    NODE_PREPARE_TEMPLATE: Callable = prepare_template
    NODE_GET_COMMENTS: Callable = get_comments
    NODE_COPY_COMMENTS: Callable = copy_comments
    NODE_EXTRACT_TENDER_PARAMS: Callable = extract_tender_params
    NODE_DELETE_TENDER_PARAM: Callable = delete_tender_param
    NODE_GET_REPLACEMENTS: Callable = get_replacements
    NODE_REPLACE_CONTENT: Callable = replace_content
    NODE_GENERATE_POLISHED_TEXT: Callable = generate_polished_text
    NODE_GENERATE_COMMENTS: Callable = generate_comments
    NODE_UPDATE_WORD: Callable = update_word
