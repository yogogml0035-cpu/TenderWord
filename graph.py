from __future__ import annotations
from langgraph.graph import END, START, StateGraph
import time
import pathlib
import sys
import asyncio


ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nodes.xjcg_word_nodes import (
    generate_polished_text,
    update_word,
    prepare_template,
    replace_content,
    get_replacements,
    extract_tender_params,
    delete_tender_param
)
from state import TenderGraphState, TextFormatState


# ============================================================================
# 子图：Word 操作流程
# ============================================================================
def build_word_operations_subgraph():
    """
    构建 Word 操作子图。
    
    子图流程：
    START → delete_tender_param → get_replacements → replace_content → END
    
    子图使用与主图相同的状态类型 TenderGraphState，
    这样可以直接共享状态，无需状态转换。
    """
    subgraph_builder = StateGraph(TenderGraphState)
    
    # 添加子图节点
    subgraph_builder.add_node("delete_tender_param", delete_tender_param)
    subgraph_builder.add_node("get_replacements", get_replacements)
    subgraph_builder.add_node("replace_content", replace_content)
    
    # 子图边：串行执行
    subgraph_builder.add_edge(START, "delete_tender_param")
    subgraph_builder.add_edge("delete_tender_param", "get_replacements")
    subgraph_builder.add_edge("get_replacements", "replace_content")
    subgraph_builder.add_edge("replace_content", END)
    
    return subgraph_builder.compile()


# 编译子图（作为一个可调用的节点）
word_operations_subgraph = build_word_operations_subgraph()


# ============================================================================
# 主图
# ============================================================================
def build_graph():
    """
    构建主图。
    
    主图流程：
    
                        extract_tender_params
                              /          \
                             /            \
                            ▼              ▼
              word_operations_subgraph    generate_polished_text
              (子图: delete→get→replace)        (LLM 调用)
                            \              /
                             \            /
                              ▼          ▼
                              update_word
                                   │
                                  END
    
    两个分支并行执行：
    - 左分支：word_operations_subgraph（子图，内部串行执行 3 个节点）
    - 右分支：generate_polished_text（单个异步节点）
    
    最后在 update_word 汇合。
    """
    builder = StateGraph(TenderGraphState)
    
    # 添加主图节点
    builder.add_node("prepare_template", prepare_template)
    builder.add_node("extract_tender_params", extract_tender_params)
    # 子图作为一个节点（LangGraph 会将编译后的子图视为一个可调用对象）
    builder.add_node("word_operations_subgraph", word_operations_subgraph)
    builder.add_node("generate_polished_text", generate_polished_text)
    builder.add_node("update_word", update_word)
    
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

    return builder.compile()



graph = build_graph()


def invoke_with_timing(graph_instance, initial_state: dict, verbose: bool = True, config=None):
    """
    执行 graph 并统计时间
    
    Args:
        graph_instance: 编译后的 graph 实例
        initial_state: 初始状态字典
        verbose: 是否打印时间信息
        config: 透传给 graph.invoke 的配置（如流式回调）
    
    Returns:
        tuple: (执行结果, 执行时间(秒))
    """
    begin_ts = time.time()
    result = graph_instance.invoke(initial_state, config=config)
    elapsed = time.time() - begin_ts
    
    if verbose:
        print("=" * 60)
        print(f"Graph 执行完成！")
        print(f"总执行时间: {elapsed:.2f} 秒 ({elapsed*1000:.0f} 毫秒)")
        if elapsed >= 60:
            minutes = int(elapsed // 60)
            seconds = elapsed % 60
            print(f"总执行时间: {minutes} 分 {seconds:.2f} 秒")
        print("=" * 60)
    
    return result, elapsed


async def invoke_with_timing_async(graph_instance, initial_state: dict, verbose: bool = True, config=None):
    """
    异步执行 graph 并统计时间
    """
    begin_ts = time.time()
    result = await graph_instance.ainvoke(initial_state, config=config)
    elapsed = time.time() - begin_ts
    
    if verbose:
        print("=" * 60)
        print(f"Graph 异步执行完成！")
        print(f"总执行时间: {elapsed:.2f} 秒 ({elapsed*1000:.0f} 毫秒)")
        if elapsed >= 60:
            minutes = int(elapsed // 60)
            seconds = elapsed % 60
            print(f"总执行时间: {minutes} 分 {seconds:.2f} 秒")
        print("=" * 60)
    
    return result, elapsed


if __name__ == "__main__":
    begin_ts = time.time()
    initial_state = {
        # 文件路径配置
        "tender_param_path": "TenderFile/技术参数.docx",
        "origin_tender_path": "TenderFile/252699-原位杂交仪-询价文件-初稿1.doc",
        "insertion_before_text": "第三章  采购需求",  # 插入位置的前置文本
        "insertion_after_text": "第四章  响应文件有关格式",  # 插入位置的后置文本
        "project_name": "测试项目名称",
        "project_number": "测试项目编号",
        "project_content": """第1包：恒温暖柜               贰台
                              第2包：数字化手术吸引系统      壹套
                              第3包：止血带系统             壹套""",
        "bzj_rule": """第1包：人民币4000元整；
                       第2包：人民币16000元整；
                       第3包：人民币2000元整""",
        "buyer_name": "上海市中医医院",
        "project_zbr_xbr": "徐旭东、任彧晟",
        "zbr_xbr_tel": "8605、8625",
        "zbr_pinyin": "xuxudong"
    }
    result = graph.invoke(initial_state)
    elapsed = time.time() - begin_ts
    print(f"Graph run finished in {elapsed:.2f}s ({elapsed*1000:.0f} ms)")