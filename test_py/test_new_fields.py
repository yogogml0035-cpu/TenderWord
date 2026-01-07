"""
测试新增字段提取功能

测试功能：
- 测试5个新增字段的提取和替换：
  1. shell_start_date (售标开始时间)
  2. shell_end_date (售标结束时间)
  3. submit_date (递交文件时间)
  4. platform (发布平台)
  5. service_fee (服务费)

使用方法: python test_new_fields.py
"""

import sys
import os
import pathlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from state import XjcgTenderGraphState
from nodes.xjcg_word_nodes.get_replacements import get_replacements


def main():
    test_doc_path = r"D:\PythonProject\TenderWord\253505-细胞电转仪-询价文件-初稿1.doc"
    
    if not os.path.exists(test_doc_path):
        print(f"[错误] 测试文件不存在: {test_doc_path}")
        print("请确保测试文档存在于指定路径。")
        sys.exit(1)
    
    print("\n" + "=" * 70)
    print("新增字段提取功能测试")
    print("=" * 70)
    print(f"\n测试文件: {test_doc_path}")
    print("")
    
    test_state: XjcgTenderGraphState = {
        "origin_tender_path": test_doc_path,
        "project_number": "253505",  
        "project_name": "细胞电转仪", 
        "project_content": "项目名称及数量：细胞电转仪   壹套",
        "bzj_rule": "项目预算的2%",
        "buyer_name": "复旦大学附属中山医院",
        "project_zbr_xbr": "徐旭东、任彧晟",
        "zbr_xbr_tel": "8605、8625",
        "zbr_pinyin": "xuxudong",
        "shell_start_date": "测试数据",
        "shell_end_date": "测试数据",
        "submit_date": "测试数据",
        "platform": "测试数据",
        "service_fee": "测试数据",
    }
    
    print("测试状态中的新增字段:")
    print("-" * 70)
    new_fields = [
        ("shell_start_date", "售标开始时间"),
        ("shell_end_date", "售标结束时间"),
        ("submit_date", "递交文件时间"),
        ("platform", "发布平台"),
        ("service_fee", "服务费"),
    ]
    
    for field_name, field_desc in new_fields:
        print(f"  {field_name:20s} ({field_desc}): {test_state[field_name]}")
    
    print("\n" + "=" * 70)
    print("开始测试...")
    print("=" * 70)
    print()
    
    try:
        result_state = get_replacements(test_state, config=None)
        
        print("\n" + "=" * 70)
        print("测试结果")
        print("=" * 70)
        
        placeholder_mapping = result_state.get("placeholder_mapping", {})
        
        print(f"\n找到的占位符总数: {len(placeholder_mapping)}")
        print()
        
        print("\n新增字段提取结果:")
        print("-" * 70)
        for field_name, field_desc in new_fields:
            if field_name in placeholder_mapping:
                value = placeholder_mapping[field_name]
                print(f"  [成功] {field_name:20s} ({field_desc}): {repr(value)}")
            else:
                print(f"  [失败] {field_name:20s} ({field_desc}): 未找到")
        
        print("\n" + "=" * 70)
        print("测试完成")
        print("=" * 70)
        
        
    except Exception as e:
        print(f"\n[错误] 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
