"""
测试 XjcgTenderGraph 的 prepare_template -> get_comments 路径

测试目标：
- 验证 prepare_template 节点能正确准备 Word 模板
- 验证 get_comments 节点能正确从送审稿文件中提取批注（支持按 insertion_before_text /
  insertion_after_text 锚点范围只抽取该范围内的批注）

注意：本脚本创建一个只包含 prepare_template 和 get_comments 两个节点的测试子图，
只执行这两个节点，不执行后续节点。

运行方式（在项目根目录执行）：
    python test_xjcg_prepare_get_comments.py
"""

import pathlib
import sys
from pprint import pprint
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
    - clean_draft_path: test_word\253505-细胞电转仪-询价文件-初稿1.doc
    - tender_param_paths: test_word\市中医-细胞电转仪招标参数.docx
    """
    # 构建测试文件路径（相对于项目根目录）
    test_word_dir = ROOT / "test_word"
    origin_tender_path = test_word_dir / "260251-脑电图仪等设备-初稿1 - 审2.docx"
    clean_draft_path = test_word_dir / "260251-脑电图仪等设备-初稿1 - 审2.docx"
    tender_param_path = test_word_dir / "市中医-细胞电转仪招标参数.docx"
    
    # 验证文件是否存在
    print("=" * 80)
    print("测试文件路径验证")
    print("=" * 80)
    print(f"origin_tender_path: {origin_tender_path}")
    print(f"  存在: {origin_tender_path.exists()}")
    print(f"clean_draft_path: {clean_draft_path}")
    print(f"  存在: {clean_draft_path.exists()}")
    print(f"tender_param_path: {tender_param_path}")
    print(f"  存在: {tender_param_path.exists()}")
    print()
    
    if not origin_tender_path.exists():
        print(f"错误: 文件不存在: {origin_tender_path}")
        return
    
    if not clean_draft_path.exists():
        print(f"错误: 文件不存在: {clean_draft_path}")
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
        # 清洁稿文件路径
        "clean_draft_path": str(clean_draft_path.resolve()),
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
    
    # 使用 invoke 执行，得到完整合并后的最终状态
    print("=" * 80)
    print("开始执行测试子图 (prepare_template -> get_comments)")
    print("=" * 80)
    print("锚点范围（仅抽取该范围内的批注）:")
    print(f"  insertion_before_text: {initial_state['insertion_before_text']}")
    print(f"  insertion_after_text:  {initial_state['insertion_after_text']}")
    print()
    
    try:
        final_state = test_graph.invoke(initial_state)
        
        print("=" * 80)
        print("执行完成 - 最终状态摘要")
        print("=" * 80)
        
        prepared_doc_path = final_state.get("prepared_doc_path")
        if prepared_doc_path:
            print(f"[prepare_template] 准备的文档路径: {prepared_doc_path}")
            print(f"  存在: {Path(prepared_doc_path).exists()}")
        else:
            print("[prepare_template] 未得到 prepared_doc_path")
        
        comment_plan = final_state.get("comment_plan", [])
        comment_plan_detail = final_state.get("comment_plan_detail", [])
        strikethrough_plan = final_state.get("strikethrough_plan", [])
        non_black_font_plan = final_state.get("non_black_font_plan", [])
        comment_count = len(comment_plan_detail) if comment_plan_detail else len(comment_plan)
        
        print(f"\n[get_comments] 批注数量（锚点范围内）: {comment_count}")
        if comment_plan_detail:
            print("批注详情 (前 5 条):")
            for i, c in enumerate(comment_plan_detail[:5], 1):
                content = (c.get("content") or "")[:80]
                scope = (c.get("scope_text") or "")[:60]
                print(f"  [{i}] content={content}... scope_text={scope}...")
        elif comment_plan:
            for i, comment in enumerate(comment_plan[:5], 1):
                display_comment = comment[:200] + "..." if len(comment) > 200 else comment
                print(f"  {i}. {display_comment}")
        else:
            print("  无批注（或范围内无批注）")
        
        print(f"\n[get_comments] 删除线段落数量: {len(strikethrough_plan)}")
        if strikethrough_plan:
            for i, s in enumerate(strikethrough_plan[:3], 1):
                para = (s.get("paragraph_text") or "")[:60]
                strike = (s.get("strikethrough_text") or "")[:40]
                print(f"  [{i}] 段落: {para}... 删除线: {strike}")
        
        print(f"\n[get_comments] 非黑色字体数量: {len(non_black_font_plan)}")
        if non_black_font_plan:
            for i, f in enumerate(non_black_font_plan[:3], 1):
                para = (f.get("paragraph_text") or "")[:40]
                font = (f.get("font_text") or "")[:40]
                print(f"  [{i}] paragraph_text={para}... font_text={font}")
        
        print("\n" + "-" * 80)
        print("完整字段 (comment_plan_detail / strikethrough_plan / non_black_font_plan):")
        print("comment_plan_detail:")
        pprint(comment_plan_detail)
        print("strikethrough_plan:")
        pprint(strikethrough_plan)
        print("non_black_font_plan:")
        pprint(non_black_font_plan)
        
        print("\n" + "=" * 80)
        print("测试结果")
        print("=" * 80)
        print("[成功] prepare_template 节点已执行" + (f" -> {prepared_doc_path}" if prepared_doc_path else ""))
        print(f"[成功] get_comments 节点已执行 -> 批注 {comment_count} 条, 删除线 {len(strikethrough_plan)} 条, 非黑字 {len(non_black_font_plan)} 条")
        
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
