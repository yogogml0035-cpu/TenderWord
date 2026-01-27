"""
询价采购文档生成 Graph 模块

本模块定义了 XjcgTenderGraph 类，用于构建和执行询价采购文档生成的工作流。

主要功能：
1. 准备 Word 模板
2. 提取招标参数
3. 执行 Word 操作子图（删除、获取替换、替换内容）
4. 生成润色文本（LLM 调用）
5. 更新 Word 文档

工作流结构：
    START
      ↓
    prepare_template
      ↓
    extract_tender_params
      ↓         ↓
      ↓         ↓
      ↓    generate_polished_text (LLM)
      ↓         ↓
    word_operations_subgraph
    (delete → get → replace)
      ↓         ↓
      ↓         ↓
      └─────→ update_word
                ↓
               END

需求引用：
- 需求 2.1: 作为开发者，我希望能够轻松创建新的 Graph
- 需求 3.3: Graph 定义迁移

使用示例：
    from graphs import XjcgTenderGraph
    
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
from langgraph.graph import END, START, StateGraph
from typing import Type, TypedDict

from graphs.base_graph import BaseGraph
from states import XjcgTenderGraphState
from nodes.xjcg_word_nodes import (
    generate_polished_text,
    update_word,
    prepare_template,
    replace_content,
    get_replacements,
    extract_tender_params,
    delete_tender_param
)


class XjcgTenderGraph(BaseGraph):
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
    
    def get_state_class(self) -> Type[TypedDict]:
        """
        返回使用的 state 类
        
        Returns:
            Type[TypedDict]: XjcgTenderGraphState 类型
        """
        return XjcgTenderGraphState
    
    def build_graph(self) -> StateGraph:
        """
        构建询价采购文档生成的工作流
        
        工作流包含以下节点：
        1. prepare_template: 准备 Word 模板
        2. extract_tender_params: 提取招标参数
        3. word_operations_subgraph: Word 操作子图（子图内部包含 3 个节点）
           - delete_tender_param: 删除招标参数
           - get_replacements: 获取替换内容
           - replace_content: 替换内容
        4. generate_polished_text: 生成润色文本（LLM 调用）
        5. update_word: 更新 Word 文档
        
        并行执行：
        - extract_tender_params 之后，word_operations_subgraph 和 generate_polished_text 并行执行
        - 两个分支在 update_word 汇合
        
        Returns:
            StateGraph: 未编译的 StateGraph 实例
        """
        builder = StateGraph(XjcgTenderGraphState)
        
        # 添加主图节点（使用进度追踪包装）
        builder.add_node("prepare_template", 
                        self.wrap_node("prepare_template", prepare_template))
        builder.add_node("extract_tender_params", 
                        self.wrap_node("extract_tender_params", extract_tender_params))
        # 子图作为一个节点（子图内部已经有进度追踪）
        builder.add_node("word_operations_subgraph", self._build_word_operations_subgraph())
        builder.add_node("generate_polished_text", 
                        self.wrap_node("generate_polished_text", generate_polished_text))
        builder.add_node("update_word", 
                        self.wrap_node("update_word", update_word))
        
        # 主图边
        builder.add_edge(START, "prepare_template")
        builder.add_edge("prepare_template", "extract_tender_params")
        
        # 从 extract_tender_params 扇出到两个并行分支
        builder.add_edge("extract_tender_params", "word_operations_subgraph")
        builder.add_edge("extract_tender_params", "generate_polished_text")
        
        # 两个分支都汇入 update_word（扇入）
        builder.add_edge("word_operations_subgraph", "update_word")
        builder.add_edge("generate_polished_text", "update_word")
        
        builder.add_edge("update_word", END)
        
        return builder
    
    def _build_word_operations_subgraph(self):
        """
        构建 Word 操作子图（私有方法）
        
        子图流程：
        START → delete_tender_param → get_replacements → replace_content → END
        
        子图使用与主图相同的状态类型 XjcgTenderGraphState，
        这样可以直接共享状态，无需状态转换。
        
        Returns:
            CompiledGraph: 编译后的子图实例
        """
        subgraph_builder = StateGraph(XjcgTenderGraphState)
        
        # 添加子图节点（使用进度追踪包装）
        subgraph_builder.add_node("delete_tender_param", 
                                  self.wrap_node("delete_tender_param", delete_tender_param))
        subgraph_builder.add_node("get_replacements", 
                                  self.wrap_node("get_replacements", get_replacements))
        subgraph_builder.add_node("replace_content", 
                                  self.wrap_node("replace_content", replace_content))
        
        # 子图边：串行执行
        subgraph_builder.add_edge(START, "delete_tender_param")
        subgraph_builder.add_edge("delete_tender_param", "get_replacements")
        subgraph_builder.add_edge("get_replacements", "replace_content")
        subgraph_builder.add_edge("replace_content", END)
        
        return subgraph_builder.compile()
