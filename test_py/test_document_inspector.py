"""
Word 文档内容检测测试脚本

测试功能：
- 文档保护状态检测
- 批注检测（内容和位置）
- 删除线段落检测
- 非黑色字体文字检测

使用方法: python test_document_inspector.py
"""

import sys
import os
import logging

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from util.word_document_inspector import WordDocumentInspector, DocumentAnalysisResult
from util.word_application_util import (
    create_word_application,
    close_word_application,
    open_document_with_retry,
)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    test_file_path = r"D:\CompanyProject\TenderWord\test_word\253505-细胞电转仪-询价文件-初稿1.doc"

    if not os.path.exists(test_file_path):
        print(f"[错误] 测试文件不存在: {test_file_path}")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("Word 文档内容检测测试")
    print("=" * 70)
    print(f"\n测试文件: {test_file_path}")
    print("")

    word_app = None
    doc = None
    com_initialized = False

    try:
        logger.info("开始测试 Word 文档内容检测功能")

        logger.info("创建 Word 应用程序...")
        word_app, com_initialized = create_word_application(
            initial_delay=1.0,
            post_init_delay=0.5,
            use_existing=False,
            node_name="文档检测测试"
        )

        logger.info(f"打开文档: {test_file_path}")
        doc = open_document_with_retry(
            word_app,
            test_file_path,
            read_only=True,
            node_name="文档检测测试"
        )

        inspector = WordDocumentInspector(
            word_app=word_app,
            doc=doc,
            node_name="文档检测测试"
        )

        print("\n开始分析文档...\n")

        result = inspector.analyze_document()

        report = inspector.format_analysis_report(result)
        print(report)

        print("\n" + "-" * 70)
        print("测试结果摘要:")
        print("-" * 70)
        print(f"  文档保护状态: {'受保护' if result.is_protected else '无保护'}")
        print(f"  批注数量: {result.total_comments}")
        print(f"  删除线段落数量: {result.total_strikethroughs}")
        print(f"  非黑色字体段落数量: {result.total_non_black_fonts}")
        print("-" * 70)

        if result.comments:
            print("\n批注详情:")
            for i, comment in enumerate(result.comments, 1):
                print(f"  [{i}] 作者: {comment.author}, 日期: {comment.date}")
                print(f"      批注范围: {comment.scope_text}")
                print(f"      内容: {comment.content}")

        if result.strikethroughs:
            print("\n删除线段落详情:")
            for i, strikethrough in enumerate(result.strikethroughs, 1):
                print(f"  [{i}] 删除线所在段落: {strikethrough.paragraph_text}")
                print(f"      删除线内容: {strikethrough.strikethrough_text}")

        if result.non_black_fonts:
            print("\n非黑色字体详情:")
            for i, font_info in enumerate(result.non_black_fonts, 1):
                print(f"  [{i}] 非黑色字体所在段落: {font_info.paragraph_text}")
                print(f"      非黑色字体: {font_info.font_text}")
                print(f"      颜色: {font_info.color_name}")

        print("\n" + "=" * 70)
        print("测试完成")
        print("=" * 70 + "\n")

    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        logger.info("清理资源...")
        if doc is not None:
            try:
                doc.Close(SaveChanges=False)
                logger.info("文档已关闭")
            except Exception as e:
                logger.warning(f"关闭文档时出错: {e}")

        if word_app is not None:
            try:
                word_app.Quit()
                logger.info("Word 应用程序已关闭")
            except Exception as e:
                logger.warning(f"关闭 Word 时出错: {e}")

        if com_initialized:
            try:
                import pythoncom
                pythoncom.CoUninitialize()
                logger.info("COM 资源已清理")
            except Exception as e:
                logger.warning(f"清理 COM 时出错: {e}")


if __name__ == "__main__":
    main()
