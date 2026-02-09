from __future__ import annotations

import argparse
import sys
from pathlib import Path

from nodes.common_word_nodes import prepare_template, copy_comments


def _configure_stdio() -> None:
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main() -> int:
    _configure_stdio()

    default_origin = Path(
        r"d:\CompanyProject\TenderWord\test_word\253000-细胞自动计数仪-询价文件-初稿1（审2） - 2.doc"
    )
    default_clean = Path(
        r"d:\CompanyProject\TenderWord\test_word\253000-细胞自动计数仪-询价文件-发售稿 - 副本.doc"
    )

    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", type=str, default=str(default_origin))
    parser.add_argument("--clean", type=str, default=str(default_clean))
    parser.add_argument("--before", type=str, default="第三章  采购需求")
    parser.add_argument("--after", type=str, default="第四章  响应文件有关格式")
    parser.add_argument("--tender-type", type=str, default="xjcg")
    parser.add_argument("--project-number", type=str, default="253000")
    parser.add_argument("--project-name", type=str, default="细胞自动计数仪")
    args = parser.parse_args()

    origin_path = Path(args.origin)
    clean_path = Path(args.clean)

    if not origin_path.exists():
        print(f"找不到送审稿: {origin_path}")
        return 2
    if not clean_path.exists():
        print(f"找不到清洁稿/模板: {clean_path}")
        return 2

    initial_state = {
        "tender_type": args.tender_type,
        "origin_tender_path": str(origin_path.resolve()),
        "clean_draft_path": str(clean_path.resolve()),
        "insertion_before_text": args.before,
        "insertion_after_text": args.after,
        "project_name": args.project_name,
        "project_number": args.project_number,
        "project_content": "",
        "bzj_rule": "",
        "buyer_name": "",
        "project_zbr_xbr": "",
        "zbr_xbr_tel": "",
        "zbr_pinyin": "",
        "shell_start_date": "",
        "shell_end_date": "",
        "submit_date": "",
        "platform": "",
        "service_fee": "",
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

    state_after_prepare = prepare_template(initial_state, config={})
    prepared_doc_path = state_after_prepare.get("prepared_doc_path")
    print(f"prepare_template 输出文件: {prepared_doc_path}")

    copy_updates = copy_comments(state_after_prepare, config={})
    print(f"copy_comments 日志: {copy_updates.get('copy_comments_log')}")
    print(f"copy_comments 成功条数: {copy_updates.get('copy_comments_added')}")
    unmatched = copy_updates.get("copy_comments_unmatched") or []
    print(f"copy_comments 未匹配条数: {len(unmatched)}")

    if unmatched:
        preview = unmatched[:3]
        print("未匹配样例(前 3 条):")
        for item in preview:
            scope = str(item.get("scope_text", ""))[:80]
            comment = str(item.get("comment_text", ""))[:120]
            reason = str(item.get("reason", ""))[:120]
            print(f"- scope_text={scope}... comment_text={comment}... reason={reason}")

    print("完成。请用 Word 打开 prepare_template 输出文件查看批注复制效果。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

