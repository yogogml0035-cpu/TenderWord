"""
Word COM 诊断工具

用于检测 Word 安装、版本和 COM 接口可用性，帮助排查问题。
"""

from __future__ import annotations

import logging
import sys
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

try:
    import win32com.client as win32
    import win32com
    import pythoncom

    WIN32COM_AVAILABLE = True
except ImportError:
    WIN32COM_AVAILABLE = False
    win32 = None
    win32com = None
    pythoncom = None


def check_win32com_installation() -> Dict[str, Any]:
    """
    检查 pywin32 是否已安装

    返回:
        Dict: 包含检查结果的字典
    """
    result = {"installed": WIN32COM_AVAILABLE, "error": None, "version": None}

    if not WIN32COM_AVAILABLE:
        result["error"] = "pywin32 未安装。请运行: pip install pywin32"
        return result

    try:
        # 尝试获取版本信息
        if hasattr(win32com, "__version__"):
            result["version"] = win32com.__version__
        else:
            result["version"] = "已安装（版本未知）"
    except Exception as e:
        result["error"] = f"获取 pywin32 版本信息失败: {e}"

    return result


def check_word_installation() -> Dict[str, Any]:
    """
    检查 Word 是否已安装

    返回:
        Dict: 包含检查结果的字典
    """
    result = {
        "installed": False,
        "version": None,
        "name": None,
        "path": None,
        "error": None,
        "com_progid": None,
    }

    if not WIN32COM_AVAILABLE:
        result["error"] = "pywin32 未安装，无法检查 Word"
        return result

    # 尝试多种方式检测 Word
    word_progids = [
        "Word.Application",  # Microsoft Word
        "WPS.Application",  # WPS Office
        "KWPS.Application",  # 金山 WPS
    ]

    for progid in word_progids:
        try:
            # 尝试创建对象（不实际启动）
            pythoncom.CoInitialize()
            try:
                word_app = win32.DispatchEx(progid)
                word_app.Visible = False

                # 获取版本信息
                try:
                    result["version"] = word_app.Version
                except:
                    pass

                # 获取名称
                try:
                    result["name"] = word_app.Name
                except:
                    result["name"] = progid

                # 获取路径
                try:
                    result["path"] = word_app.Path
                except:
                    pass

                result["installed"] = True
                result["com_progid"] = progid

                # 关闭实例
                try:
                    word_app.Quit(SaveChanges=False)
                except:
                    pass

                pythoncom.CoUninitialize()
                return result

            except Exception as e:
                pythoncom.CoUninitialize()
                continue

        except Exception as e:
            continue

    result["error"] = (
        "未检测到 Word 或 WPS 安装。请确保已安装 Microsoft Word 或 WPS Office。"
    )
    return result


def get_word_version_info() -> Optional[Dict[str, Any]]:
    """
    获取 Word 版本详细信息

    返回:
        Dict: 包含版本信息的字典，如果失败返回 None
    """
    if not WIN32COM_AVAILABLE:
        return None

    word_info = check_word_installation()
    if not word_info.get("installed"):
        return None

    try:
        pythoncom.CoInitialize()
        try:
            word_app = win32.DispatchEx(word_info["com_progid"])
            word_app.Visible = False

            info = {
                "name": word_info.get("name", "Unknown"),
                "version": word_info.get("version", "Unknown"),
                "path": word_info.get("path", "Unknown"),
                "progid": word_info.get("com_progid", "Unknown"),
            }

            # 尝试获取更多信息
            try:
                info["build"] = word_app.Build
            except:
                pass

            try:
                info["language"] = word_app.Language
            except:
                pass

            # 关闭实例
            try:
                word_app.Quit(SaveChanges=False)
            except:
                pass

            pythoncom.CoUninitialize()
            return info

        except Exception as e:
            pythoncom.CoUninitialize()
            return None
    except Exception as e:
        return None


def diagnose_word_com_environment() -> Dict[str, Any]:
    """
    全面诊断 Word COM 环境

    返回:
        Dict: 包含所有诊断结果的字典
    """
    diagnosis = {
        "platform": sys.platform,
        "python_version": sys.version,
        "win32com": check_win32com_installation(),
        "word": check_word_installation(),
        "recommendations": [],
    }

    # 生成建议
    if not diagnosis["win32com"]["installed"]:
        diagnosis["recommendations"].append("请安装 pywin32: pip install pywin32")

    if not diagnosis["word"]["installed"]:
        diagnosis["recommendations"].append("请安装 Microsoft Word 或 WPS Office")
        diagnosis["recommendations"].append(
            "如果已安装但检测不到，可能需要修复 Office 安装或重新注册 COM 组件"
        )
    else:
        word_name = diagnosis["word"].get("name", "Word")
        word_version = diagnosis["word"].get("version", "Unknown")
        diagnosis["recommendations"].append(
            f"检测到 {word_name} (版本: {word_version})，COM 接口应该可用"
        )

        # 检查是否为 WPS
        if "WPS" in word_name.upper():
            diagnosis["recommendations"].append(
                "注意：检测到 WPS Office。某些功能可能与 Microsoft Word 有差异"
            )

    return diagnosis


def format_diagnosis_report(diagnosis: Dict[str, Any]) -> str:
    """
    格式化诊断报告为可读的字符串

    参数:
        diagnosis: 诊断结果字典

    返回:
        str: 格式化的报告字符串
    """
    lines = []
    lines.append("=" * 60)
    lines.append("Word COM 环境诊断报告")
    lines.append("=" * 60)
    lines.append("")

    lines.append(f"平台: {diagnosis['platform']}")
    lines.append(f"Python 版本: {diagnosis['python_version'].split()[0]}")
    lines.append("")

    # pywin32 检查
    lines.append("【pywin32 检查】")
    win32com_info = diagnosis["win32com"]
    if win32com_info["installed"]:
        lines.append(f"  [OK] 已安装 (版本: {win32com_info.get('version', 'Unknown')})")
    else:
        lines.append(f"  [X] 未安装")
        if win32com_info.get("error"):
            lines.append(f"    错误: {win32com_info['error']}")
    lines.append("")

    # Word 检查
    lines.append("【Word 安装检查】")
    word_info = diagnosis["word"]
    if word_info["installed"]:
        lines.append(f"  [OK] 已安装")
        lines.append(f"    名称: {word_info.get('name', 'Unknown')}")
        lines.append(f"    版本: {word_info.get('version', 'Unknown')}")
        lines.append(f"    路径: {word_info.get('path', 'Unknown')}")
        lines.append(f"    COM ProgID: {word_info.get('com_progid', 'Unknown')}")
    else:
        lines.append(f"  [X] 未安装或无法访问")
        if word_info.get("error"):
            lines.append(f"    错误: {word_info['error']}")
    lines.append("")

    # 建议
    if diagnosis["recommendations"]:
        lines.append("【建议】")
        for i, rec in enumerate(diagnosis["recommendations"], 1):
            lines.append(f"  {i}. {rec}")
    else:
        lines.append("【建议】")
        lines.append("  [OK] 环境配置正常，应该可以正常使用")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


if __name__ == "__main__":
    # 命令行诊断工具
    print("\n正在诊断 Word COM 环境...\n")
    diagnosis = diagnose_word_com_environment()
    report = format_diagnosis_report(diagnosis)
    print(report)
