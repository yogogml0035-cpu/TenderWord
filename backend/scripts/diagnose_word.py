"""
Word COM 环境诊断脚本

运行此脚本来检查 Word COM 环境配置是否正确。
使用方法: python diagnose_word.py
"""

import sys
import pathlib
import os

# 添加项目根目录到路径
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from util.word_util import (
    diagnose_word_com_environment,
    format_diagnosis_report,
)

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Word COM 环境诊断工具")
    print("=" * 60)
    print("\n正在检查环境配置...\n")

    try:
        diagnosis = diagnose_word_com_environment()
        report = format_diagnosis_report(diagnosis)
        print(report)

        # 根据诊断结果给出退出码
        if not diagnosis["win32com"]["installed"] or not diagnosis["word"]["installed"]:
            print("\n[警告] 环境配置存在问题，请根据上述建议进行修复。")
            sys.exit(1)
        else:
            print("\n[OK] 环境配置正常，应该可以正常使用 Word COM 接口。")
            sys.exit(0)

    except Exception as e:
        print(f"\n[错误] 诊断过程中发生错误: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
