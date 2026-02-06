"""
测试 XjcgTenderGraph 的 prepare_template -> get_comments -> generate_comments 路径

测试目标：
- 验证 prepare_template 节点能正确准备 Word 模板
- 验证 get_comments 节点能正确从送审稿文件中提取批注（支持按 insertion_before_text /
  insertion_after_text 锚点范围只抽取该范围内的批注）
- 验证 generate_comments 节点能基于给定的 polished_text 和计划列表调用大模型生成 polished_comments

注意：
- 本脚本创建一个只包含 prepare_template、get_comments 和 generate_comments 三个节点的测试子图，
  只执行这三个节点，不执行后续节点。
- 为了稳定可复现，本测试中 generate_comments 所需的 polished_text 直接硬编码为：
  "@253505-细胞电转仪-初稿-20260204-112102.txt (1-15)"

运行方式（在项目根目录执行）：
    python test_xjcg_prepare_get_comments_generate_comments.py
"""

import pathlib
import sys
from pprint import pprint
from pathlib import Path

from langgraph.graph import StateGraph, START, END

# Windows 控制台常见为 GBK，直接 print 含上标等 Unicode 容易触发 UnicodeEncodeError。
# 这里统一将 stdout/stderr 设置为可容忍的编码/错误策略，避免测试脚本中途崩溃。
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 添加项目根目录到 sys.path
ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from states import XjcgTenderGraphState
from nodes.common_word_nodes.prepare_template import prepare_template
from nodes.common_word_nodes.get_comments import get_comments
from nodes.common_word_nodes.generate_comments import generate_comments


def create_test_subgraph():
    """
    创建一个包含 prepare_template -> get_comments -> generate_comments 的测试子图
    """
    builder = StateGraph(XjcgTenderGraphState)

    # 添加节点
    builder.add_node("prepare_template", prepare_template)
    builder.add_node("get_comments", get_comments)
    builder.add_node("generate_comments", generate_comments)

    # 添加边
    builder.add_edge(START, "prepare_template")
    builder.add_edge("prepare_template", "get_comments")
    builder.add_edge("get_comments", "generate_comments")
    builder.add_edge("generate_comments", END)

    return builder.compile()


def _preview_value(v, max_len: int = 800):
    """控制台打印预览：过长字符串截断，避免刷屏。"""
    try:
        if isinstance(v, str) and len(v) > max_len:
            return v[:max_len] + f"...(len={len(v)})"
        return v
    except Exception:
        return v


def _print_list_of_dict_kv(field_name: str, items):
    """打印 list[dict] 中所有字典的键值对（含非 dict 的兜底）。"""
    if items is None:
        print(f"[get_comments] {field_name}: None")
        return
    if not isinstance(items, list):
        print(f"[get_comments] {field_name} 不是 list，而是 {type(items).__name__}: {_preview_value(items)}")
        return

    print(f"[get_comments] {field_name} 数量: {len(items)}")
    for idx, item in enumerate(items, 1):
        print(f"  --- {field_name}[{idx}] ---")
        if isinstance(item, dict):
            # 按 key 排序便于对比
            for k in sorted(item.keys(), key=lambda x: str(x)):
                v = item.get(k)
                print(f"    {k} = {_preview_value(v)!r}")
        else:
            print(f"    (非 dict) {type(item).__name__}: {_preview_value(item)!r}")


def print_get_comments_three_fields(state: dict):
    """
    打印 get_comments 节点后需要获取的三个字段中所有字典键值对：
    - comment_plan_detail
    - strikethrough_plan
    - non_black_font_plan
    """
    print("\n" + "=" * 80)
    print("get_comments 输出 - 三个字段字典键值对（comment_plan_detail / strikethrough_plan / non_black_font_plan）")
    print("=" * 80)
    _print_list_of_dict_kv("comment_plan_detail", state.get("comment_plan_detail"))
    print("-" * 80)
    _print_list_of_dict_kv("strikethrough_plan", state.get("strikethrough_plan"))
    print("-" * 80)
    _print_list_of_dict_kv("non_black_font_plan", state.get("non_black_font_plan"))
    print("=" * 80 + "\n")


def test_prepare_get_comments_generate_comments():
    """
    测试 prepare_template -> get_comments -> generate_comments 路径

    测试文件：
    - origin_tender_path: test_word\\253000-细胞自动计数仪-询价文件-初稿1（审2） - 2.doc
    - clean_draft_path: test_word\\253505-细胞电转仪-询价文件-初稿1.doc
    - tender_param_paths: test_word\\市中医-细胞电转仪招标参数.docx
    """
    # 构建测试文件路径（相对于项目根目录）
    test_word_dir = ROOT / "test_word"
    origin_tender_path = test_word_dir / "253000-细胞自动计数仪-询价文件-初稿1（审2） - 2.doc"
    clean_draft_path = test_word_dir / "253505-细胞电转仪-询价文件-初稿1.doc"
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
        # generate_comments 所需的 polished_text，按需求直接硬编码
        "polished_text": """一、项目概述
1、项目名称及数量：细胞电转仪  壹套
2、交付日期：自合同签订后90天
3、交付地点：采购人指定地点
4、付款方式： 在安装调试验收合格正常使用后，收到发票后90日内进行付款
二、技术要求
★1、可电转的细胞量起码包含 1x10⁴-1x10⁶ ；
★2、细胞类型：可转染难转染的哺乳动物细胞、干细胞、神经细胞、原代细胞等；
3、支持双波形电穿孔系统；
4、配彩色高清触摸屏；
★5、内置转染程序大于100种；
6、最多可存储实验程序数量大于10000种；
7、电转转染过程中的各项参数可见、可调，包括脉冲模式、脉冲电压、时间、脉冲驱动次数等，可通过参数调整以达到最佳转染效率；
8、能提供转染的整体解决方案，耗材通用，并提供耗材报价。
★9、整机原厂保修6年，过保后费率不超过3%。""",
        # 默认值字段（避免节点访问未定义字段时出错）
        "origin_tender_params": "",
        "tender_params": "",
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
    print("创建测试子图（包含 prepare_template -> get_comments -> generate_comments）")
    print("=" * 80)
    test_graph = create_test_subgraph()
    print("测试子图创建成功")
    print()

    # 使用 invoke 执行，得到完整合并后的最终状态
    print("=" * 80)
    print("开始执行测试子图 (prepare_template -> get_comments -> generate_comments)")
    print("=" * 80)
    print("锚点范围（仅抽取该范围内的批注）:")
    print(f"  insertion_before_text: {initial_state['insertion_before_text']}")
    print(f"  insertion_after_text:  {initial_state['insertion_after_text']}")
    print()
    print(f"generate_comments 硬编码 polished_text: {initial_state['polished_text']}")
    print()

    try:
        # 为了能精确拿到 get_comments 节点执行后的状态并打印，
        # 这里按节点顺序手动调用（逻辑等价于子图执行）。
        state_after_prepare = prepare_template(initial_state, config={})
        state_after_get_comments = get_comments(state_after_prepare, config={})

        # 打印 get_comments 节点后三个字段中所有字典键值对
        print_get_comments_three_fields(state_after_get_comments)

        # 继续执行 generate_comments，并将其输出合并回 state
        generate_updates = generate_comments(state_after_get_comments, config={})
        final_state = dict(state_after_get_comments)
        final_state.update(dict(generate_updates))

        print("=" * 80)
        print("执行完成 - generate_comments 输出摘要")
        print("=" * 80)

        polished_comments = final_state.get("polished_comments", [])
        print(f"[generate_comments] polished_comments 数量: {len(polished_comments)}")

        if polished_comments:
            print("polished_comments 预览 (前 5 条):")
            for i, c in enumerate(polished_comments[:5], 1):
                if isinstance(c, dict):
                    ref = str(c.get("reference_text", ""))[:80]
                    comment = str(c.get("comment_text", ""))[:120]
                    print(f"  [{i}] reference_text={ref}... comment_text={comment}...")
                else:
                    # 兼容意外返回的非 dict 结构
                    preview = str(c)
                    if len(preview) > 200:
                        preview = preview[:200] + "..."
                    print(f"  [{i}] {preview}")
        else:
            print("[generate_comments] 未生成任何 polished_comments")

        print("\n" + "-" * 80)
        print("完整 polished_comments 内容：")
        pprint(polished_comments)

        print("\n" + "=" * 80)
        print("测试结果")
        print("=" * 80)
        print("[成功] prepare_template -> get_comments -> generate_comments 三个节点已按顺序执行")
        print(f"[成功] generate_comments 生成 polished_comments 条数: {len(polished_comments)}")

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
    test_prepare_get_comments_generate_comments()

