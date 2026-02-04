"""
测试 XjcgTenderGraph 的 prepare_template -> get_comments 路径

测试目标：
- 验证 prepare_template 节点能正确准备 Word 模板
- 验证 get_comments 节点能正确从送审稿文件中提取批注

注意：本脚本创建一个只包含 prepare_template 和 get_comments 两个节点的测试子图，
只执行这两个节点，不执行后续节点。
"""

import pathlib
import sys
from pathlib import Path
from langgraph.graph import StateGraph, START, END

# 添加项目根目录到 sys.path
ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from graphs.xjcg_tender_graph import XjcgTenderGraph
from states import XjcgTenderGraphState
from nodes.common_word_nodes import prepare_template, get_comments


def create_test_subgraph():
    """
    创建一个只包含 prepare_template 和 get_comments 的测试子图
    """
    builder = StateGraph(XjcgTenderGraphState)
    
    # 添加节点
    builder.add_node("prepare_template", prepare_template)
    builder.add_node("get_comments", get_comments)
    
    # 添加边
    builder.add_edge(START, "prepare_template")
    builder.add_edge("prepare_template", "get_comments")
    builder.add_edge("get_comments", END)
    
    return builder.compile()


def test_prepare_template_and_get_comments():
    """
    测试 prepare_template -> get_comments 路径
    
    测试文件：
    - origin_tender_path: test_word\253505-细胞电转仪-询价文件-初稿1.doc
    - review_draft_path: test_word\253505-细胞电转仪-询价文件-初稿1.doc
    - tender_param_paths: test_word\市中医-细胞电转仪招标参数.docx
    """
    # 构建测试文件路径（相对于项目根目录）
    test_word_dir = ROOT / "test_word"
    origin_tender_path = test_word_dir / "253505-细胞电转仪-询价文件-初稿1.doc"
    review_draft_path = test_word_dir / "253505-细胞电转仪-询价文件-初稿1.doc"
    tender_param_path = test_word_dir / "市中医-细胞电转仪招标参数.docx"
    
    # 验证文件是否存在
    print("=" * 80)
    print("测试文件路径验证")
    print("=" * 80)
    print(f"origin_tender_path: {origin_tender_path}")
    print(f"  存在: {origin_tender_path.exists()}")
    print(f"review_draft_path: {review_draft_path}")
    print(f"  存在: {review_draft_path.exists()}")
    print(f"tender_param_path: {tender_param_path}")
    print(f"  存在: {tender_param_path.exists()}")
    print()
    
    if not origin_tender_path.exists():
        print(f"错误: 文件不存在: {origin_tender_path}")
        return
    
    if not review_draft_path.exists():
        print(f"错误: 文件不存在: {review_draft_path}")
        return
    
    if not tender_param_path.exists():
        print(f"错误: 文件不存在: {tender_param_path}")
        return
    
    # 准备初始状态（最小化字段，只包含必需的）
    initial_state = {
        # 招标类型标识符
        "tender_type": "xjcg",
        # 上传文件路径
        "origin_tender_path": str(origin_tender_path.resolve()),
        "tender_param_paths": [str(tender_param_path.resolve())],
        # 送审稿文件路径
        "review_draft_path": str(review_draft_path.resolve()),
        # 固定参数（与 graph.py 中保持一致）
        "insertion_before_text": "第三章  采购需求",
        "insertion_after_text": "第四章  响应文件有关格式",
        # 项目信息（使用测试值）
        "project_name": "测试项目",
        "project_number": "TEST-001",
        "project_content": "测试项目内容",
        "bzj_rule": "测试保证金规则",
        "buyer_name": "测试采购人",
        "project_zbr_xbr": "测试负责人/协助人",
        "zbr_xbr_tel": "12345678901",
        "zbr_pinyin": "ceshi",
        "shell_start_date": "2025-01-01",
        "shell_end_date": "2025-01-31",
        "submit_date": "2025-01-15",
        "platform": "测试平台",
        "service_fee": "0",
        # 默认值字段（避免节点访问未定义字段时出错）
        "origin_tender_params": "",
        "tender_params": "",
        "polished_text": "",
        "replacements": [],
        "placeholder_mapping": {},
        "comment_plan": [],
        "comment_plan_detail": [],
        "strikethrough_plan": [],
        "non_black_font_plan": [],
        "insertion_log": "",
        "replacement_log": "",
        "generate_polished_done": False,
        "replace_content_done": False,
    }
    
    print("=" * 80)
    print("创建测试子图（只包含 prepare_template -> get_comments）")
    print("=" * 80)
    test_graph = create_test_subgraph()
    print("测试子图创建成功")
    print()
    
    # 使用流式执行
    print("=" * 80)
    print("开始执行测试子图")
    print("=" * 80)
    
    nodes_executed = []
    final_state = None
    
    try:
        for event in test_graph.stream(initial_state):
            # event 是一个字典，key 是节点名称，value 是节点执行后的状态
            for node_name, state_update in event.items():
                nodes_executed.append(node_name)
                print(f"\n[节点执行] {node_name}")
                print("-" * 80)
                
                # 如果是 get_comments 节点，显示批注/删除线/非黑字提取结果
                if node_name == "get_comments":
                    comment_plan = state_update.get("comment_plan", [])
                    comment_plan_detail = state_update.get("comment_plan_detail", [])
                    strikethrough_plan = state_update.get("strikethrough_plan", [])
                    non_black_font_plan = state_update.get("non_black_font_plan", [])
                    print(f"批注数量: {len(comment_plan)}")
                    if comment_plan_detail:
                        print("批注详情:")
                        for i, c in enumerate(comment_plan_detail[:5], 1):
                            print(f"  [{i}] 作者={c.get('author','')}, 内容={(c.get('content') or '')[:80]}...")
                    elif comment_plan:
                        for i, comment in enumerate(comment_plan[:5], 1):
                            display_comment = comment[:200] + "..." if len(comment) > 200 else comment
                            print(f"  {i}. {display_comment}")
                    else:
                        print("  无批注")
                    print(f"删除线段落数量: {len(strikethrough_plan)}")
                    if strikethrough_plan:
                        for i, s in enumerate(strikethrough_plan[:3], 1):
                            print(f"  [{i}] 段落: {(s.get('paragraph_text') or '')[:60]}... 删除线: {(s.get('strikethrough_text') or '')[:40]}")
                    print(f"非黑色字体数量: {len(non_black_font_plan)}")
                    if non_black_font_plan:
                        for i, f in enumerate(non_black_font_plan[:3], 1):
                            print(f"  [{i}] 颜色={f.get('color_name','')}, 文字: {(f.get('font_text') or '')[:40]}")
                
                # 如果是 prepare_template 节点，显示准备结果
                elif node_name == "prepare_template":
                    prepared_doc_path = state_update.get("prepared_doc_path")
                    if prepared_doc_path:
                        print(f"准备的文档路径: {prepared_doc_path}")
                        print(f"文档是否存在: {Path(prepared_doc_path).exists()}")
                
                # 保存最终状态
                final_state = state_update
                
        print("\n" + "=" * 80)
        print("执行完成")
        print("=" * 80)
        print(f"执行的节点顺序: {' -> '.join(nodes_executed)}")
        print()
        
        # 验证节点执行情况
        if "prepare_template" in nodes_executed:
            print("[成功] prepare_template 节点已成功执行")
            if final_state:
                prepared_doc_path = final_state.get("prepared_doc_path")
                if prepared_doc_path:
                    print(f"  - 准备的文档路径: {prepared_doc_path}")
        else:
            print("[失败] prepare_template 节点未执行")
        
        if "get_comments" in nodes_executed:
            print("[成功] get_comments 节点已成功执行")
            if final_state:
                comment_plan = final_state.get("comment_plan", [])
                strikethrough_plan = final_state.get("strikethrough_plan", [])
                non_black_font_plan = final_state.get("non_black_font_plan", [])
                print(f"  - 批注: {len(comment_plan)} 条")
                print(f"  - 删除线段落: {len(strikethrough_plan)} 条")
                print(f"  - 非黑色字体: {len(non_black_font_plan)} 条")
        else:
            print("[失败] get_comments 节点未执行")
        
    except Exception as e:
        print("\n" + "=" * 80)
        print("执行出错")
        print("=" * 80)
        print(f"错误类型: {type(e).__name__}")
        print(f"错误信息: {str(e)}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)


if __name__ == "__main__":
    test_prepare_template_and_get_comments()
