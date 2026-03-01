"""
国内公开招标文档生成 Graph 模块

本模块定义了 GngkTenderGraph 类，用于构建和执行国内公开招标文档生成的工作流。

主要功能：
1. 准备 Word 模板
2. 从送审稿文件提取批注
3. 从送审稿复制锚点范围外的批注到模板
4. 提取招标参数
5. 执行 Word 操作子图（删除、获取替换、替换内容）
6. 生成润色文本（LLM 调用）
7. 基于润色文本生成批注指令（LLM 调用，仅在上传送审稿时执行）
8. 更新 Word 文档

工作流结构：
    START
      ↓
    prepare_template
      ↓  (若上传送审稿)         ↓                  ↓(若上传送审稿)
get_comments  extract_tender_params  copy_comments
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
    from backend.graphs import GngkTenderGraph
    
    # 创建 graph 实例
    graph = GngkTenderGraph()
    
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
from backend.states import GngkTenderGraphState
from backend.nodes.common_word_nodes import (
    prepare_template,
    generate_polished_text,
    replace_content,
    get_comments,
    copy_comments,
    generate_comments,
)
from backend.nodes.gngk_word_nodes import (
    get_replacements,
    update_word,
    delete_tender_param,
    extract_tender_params,
)


class GngkTenderGraph(StandardTenderWorkflowGraph):
    """
    国内公开招标文档生成 Graph
    
    继承自 BaseGraph，自动获得以下功能：
    - 跨进程文件锁（保护 Word COM 操作）
    - 节点进度追踪
    - 任务取消检查
    - 同步/异步执行方法
    
    属性：
        无额外属性
    
    方法：
        get_state_class(): 返回 GngkTenderGraphState 类型
        build_graph(): 构建国内公开招标文档生成的工作流
        _build_word_operations_subgraph(): 构建 Word 操作子图（私有方法）
    """
    
    STATE_CLS = GngkTenderGraphState

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
