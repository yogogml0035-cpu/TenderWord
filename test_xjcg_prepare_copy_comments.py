"""
测试 XjcgTenderGraph 的 prepare_template -> copy_comments 路径

运行方式（在项目根目录执行）：
    python test_xjcg_prepare_copy_comments.py
"""

import pathlib
import sys
from pprint import pprint
from pathlib import Path

ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nodes.common_word_nodes import prepare_template, copy_comments


def main():
    # Windows 控制台常见为 GBK，直接 print 含上标等 Unicode 容易触发 UnicodeEncodeError。
    # 这里统一将 stdout/stderr 设置为可容忍的编码/错误策略，避免脚本中途崩溃。
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    test_word_dir = ROOT / "test_word"
    origin_tender_path = test_word_dir / "253000-细胞自动计数仪-询价文件-初稿1（审2） - 2.doc"
    clean_draft_path = test_word_dir / "253000-细胞自动计数仪-询价文件-发售稿 - 副本.doc"

    print("=" * 80)
    print("测试文件路径验证")
    print("=" * 80)
    print(f"origin_tender_path: {origin_tender_path}")
    print(f"  存在: {origin_tender_path.exists()}")
    print(f"clean_draft_path: {clean_draft_path}")
    print(f"  存在: {clean_draft_path.exists()}")
    print()

    if not origin_tender_path.exists():
        print(f"错误: 文件不存在: {origin_tender_path.resolve()}")
        return
    if not clean_draft_path.exists():
        print(f"错误: 文件不存在: {clean_draft_path.resolve()}")
        return

    initial_state = {
        "tender_type": "xjcg",
        "origin_tender_path": str(origin_tender_path.resolve()),
        "clean_draft_path": str(clean_draft_path.resolve()),
        "insertion_before_text": "第三章  采购需求",
        "insertion_after_text": "第四章  响应文件有关格式",
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
    print("开始执行 (prepare_template -> copy_comments)")
    print("=" * 80)

    state_after_prepare = prepare_template(initial_state, config={})
    state_after_copy = copy_comments(state_after_prepare, config={})

    print("=" * 80)
    print("copy_comments 输出字段预览")
    print("=" * 80)
    pprint(
        {
            "prepared_doc_path": state_after_prepare.get("prepared_doc_path"),
            "copy_comments_log": state_after_copy.get("copy_comments_log"),
            "copy_comments_added": state_after_copy.get("copy_comments_added"),
            "unmatched_count": len(state_after_copy.get("copy_comments_unmatched") or []),
        }
    )

    if state_after_copy.get("copy_comments_unmatched"):
        print("未匹配样例(前 3 条):")
        for item in (state_after_copy.get("copy_comments_unmatched") or [])[:3]:
            pprint(item)

    print("\n完成。用 Word 打开 prepared_doc_path 查看批注是否已复制。")


if __name__ == "__main__":
    main()
