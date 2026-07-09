"""
获取替换内容核心数据结构模块。

定义 ExtractorSpec 和 ReplacementFieldSpec 数据结构，用于配置化的字段提取和替换逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass
import inspect
from typing import Any, Callable, List, Optional, Tuple, Union


@dataclass
class ExtractorSpec:
    """
    提取器规范，定义如何从文档中提取特定字段。

    每个字段对应一个 ExtractorSpec，包含字段名、启用条件和提取函数。
    支持单值返回和多值返回（如 extract_contact_fields 返回 3 个值）。

    Attributes:
        name: 字段名称，如 "project_number", "project_name" 等
        enabled_if: 接收 state 返回 bool 的可调用对象，用于判断该提取器是否启用
        extract_callable: 提取函数，接收可变参数，返回 Optional[str] 或 Tuple
        output_field_names: 可选，当 extract_callable 返回元组时，用于映射每个返回值到对应的字段名
                           如果为 None，则使用 name 作为单值字段名

    Example (单值):
        ```python
        spec = ExtractorSpec(
            name="project_number",
            enabled_if=lambda state: state.get("project_number") is not None,
            extract_callable=extract_project_number
        )
        ```

    Example (多值):
        ```python
        spec = ExtractorSpec(
            name="contact_fields",  # 用于日志标识
            enabled_if=lambda state: state.get("project_zbr_xbr") or state.get("zbr_xbr_tel") or state.get("zbr_pinyin"),
            extract_callable=extract_contact_fields,
            output_field_names=["project_zbr_xbr", "zbr_xbr_tel", "zbr_pinyin"]
        )
        ```
    """

    name: str
    enabled_if: Callable[[Any], bool]
    extract_callable: Callable[..., Union[Optional[str], Tuple[Optional[str], ...]]]
    output_field_names: Optional[List[str]] = None

@dataclass
class ReplacementFieldSpec:
    """
    替换字段规范，定义字段替换的行为规则。

    控制字段替换时的行为，如是否跳过相等的值、是否使用备用字段等。

    Attributes:
        field_name: 字段名称
        skip_if_equal: 如果旧值等于新值，是否跳过替换（默认 True）
        fallback_fields: 备用字段列表，当主字段值为空时按顺序尝试使用这些字段
        new_value_formatter: 可选的新值格式化函数，用于字段级规范化后再生成替换对

    Example:
        ```python
        spec = ReplacementFieldSpec(
            field_name="project_content",
            skip_if_equal=True,
            fallback_fields=["project_summary"]
        )
        ```
    """

    field_name: str
    skip_if_equal: bool = True
    fallback_fields: Optional[List[str]] = None
    new_value_formatter: Optional[Callable[[Any], Any]] = None


# --- Word COM 工具导入 ---
import os
import logging

from backend.util.word_util import (
    create_word_application,
    close_word_application,
    open_document_with_retry,
    unprotect_document,
)

from backend.states import TenderGraphStateBase

logger = logging.getLogger(__name__)


def _replacement_priority(field_name: str) -> tuple[int, str]:
    """Lower tuple sorts earlier and wins replacement conflicts."""
    if field_name == "project_number":
        return (0, field_name)
    if field_name == "project_name":
        return (1, field_name)
    if field_name == "project_content":
        return (10, field_name)
    if field_name.startswith("project_content_"):
        return (20, field_name)
    return (30, field_name)

def run_get_replacements(
    state: TenderGraphStateBase,
    config: Any,
    extractors: List[ExtractorSpec],
    replacement_fields: List[ReplacementFieldSpec],
) -> TenderGraphStateBase:
    """
    执行字段提取和替换内容获取的核心逻辑。

    根据提取器规范从文档中提取字段值，
    然后根据替换字段规范生成替换映射。

    Args:
        state: 当前图状态，包含所有已提取的字段和文档路径
        config: LangGraph 配置对象（包含 runnable config）
        extractors: 提取器规范列表，定义如何提取各字段
        replacement_fields: 替换字段规范列表，定义替换行为

    Returns:
        更新后的状态对象，包含以下字段：
        - placeholder_mapping: 文档中找到的占位符映射
        - replacements: 待执行的替换对列表
        - replacement_log: 替换操作日志
    """
    # ========== 1. 路径校验 ==========
    prepared_doc_path = state.get("prepared_doc_path")

    if not prepared_doc_path:
        raise ValueError("需要 prepared_doc_path 来获取替换内容")

    # 确保路径是绝对路径（Word COM 对象需要绝对路径）
    if not os.path.isabs(prepared_doc_path):
        prepared_doc_path = os.path.abspath(prepared_doc_path)

    # 检查文件是否存在
    if not os.path.exists(prepared_doc_path):
        raise FileNotFoundError(f"未找到模板文档: {prepared_doc_path}")

    # 检查文件是否可读
    if not os.access(prepared_doc_path, os.R_OK):
        raise PermissionError(f"无法读取模板文档: {prepared_doc_path}")

    # ========== 2. Word COM 生命周期 ==========
    word = None
    doc = None
    com_initialized = False
    doc_content = ""
    first_page_header = ""

    try:
        # 创建 Word 应用程序实例
        word, com_initialized = create_word_application(
            initial_delay=1.0,
            post_init_delay=0.5,
            use_existing=False,  # 并发环境下必须使用独立实例
            verify=True,
            node_name="get_replacements"
        )
        logger.info("成功创建 Word 实例")

        try:
            # 打开文档（带重试机制）
            doc = open_document_with_retry(
                word_app=word,
                file_path=prepared_doc_path,
                read_only=True,
                node_name="get_replacements"
            )
            logger.info(f"已打开文档: {prepared_doc_path}")

            # 取消文档保护
            if unprotect_document(doc, node_name="get_replacements"):
                logger.info("文档已取消保护")

            # 读取文档全文内容
            doc_content = doc.Content.Text
            logger.info(f"文档内容长度: {len(doc_content)} 个字符")

            # 读取首页页眉内容（异常时置空）
            try:
                first_page_header = doc.Sections(1).Headers(1).Range.Text
            except Exception as e:
                logger.debug(f"读取页眉时出错: {e}")
                first_page_header = ""

            # ========== 3. Extractor 执行逻辑 ==========
            found_placeholders: dict = {}
            log_parts: list = []

            def call_extractor(fn: Callable[..., Any]):
                try:
                    sig = inspect.signature(fn)
                except (TypeError, ValueError):
                    return fn(doc_content, first_page_header, state, log_parts)

                params = list(sig.parameters.values())
                if any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params):
                    return fn(doc_content, first_page_header, state, log_parts)

                positional = [
                    p
                    for p in params
                    if p.kind
                    in (
                        inspect.Parameter.POSITIONAL_ONLY,
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    )
                ]

                if len(positional) >= 4:
                    return fn(doc_content, first_page_header, state, log_parts)
                if len(positional) == 3:
                    return fn(doc_content, state, log_parts)
                if len(positional) == 2:
                    return fn(doc_content, state)
                return fn(doc_content)

            for spec in extractors:
                # 检查 enabled_if 条件
                if not spec.enabled_if(state):
                    continue

                try:
                    # 调用 extractor 获取字段值
                    result = call_extractor(spec.extract_callable)

                    # 根据返回值类型处理
                    if spec.output_field_names is not None:
                        # 多值返回：output_field_names 指定了每个返回值对应的字段名
                        if isinstance(result, tuple):
                            for field_name, value in zip(spec.output_field_names, result):
                                if value is not None and value != "":
                                    found_placeholders[field_name] = value
                        else:
                            # 如果指定了 output_field_names 但返回值不是元组，记录警告
                            warning_msg = f"警告: {spec.name} 指定了 output_field_names 但返回值不是元组"
                            log_parts.append(warning_msg)
                            logger.warning(warning_msg)
                    else:
                        # 单值返回：使用 spec.name 作为字段名
                        if result is not None and result != "":
                            if isinstance(result, tuple):
                                # 如果没有指定 output_field_names 但返回了元组，使用第一个值
                                if result[0] is not None and result[0] != "":
                                    found_placeholders[spec.name] = result[0]
                            else:
                                found_placeholders[spec.name] = result

                except Exception as e:
                    # 异常隔离：单个 extractor 失败不影响其他
                    error_msg = f"提取 {spec.name} 时出错: {e}"
                    log_parts.append(error_msg)
                    logger.warning(error_msg)

            # 记录提取结果摘要
            if found_placeholders:
                log_parts.append(f"在文档中找到 {len(found_placeholders)} 个占位符")
            else:
                log_parts.append("未在文档中找到任何占位符")

            # ========== 4. Replacements 生成逻辑 ==========
            replacement_candidates: list[dict[str, str]] = []
            candidate_index_by_old_value: dict[str, int] = {}
            
            if found_placeholders:
                # 遍历 replacement_fields 列表生成替换
                for field_spec in replacement_fields:
                    field_name = field_spec.field_name
                    
                    # 从 found_placeholders 获取 old_value（文档中提取的旧值）
                    old_value = found_placeholders.get(field_name)
                    if not old_value:
                        continue
                    
                    # 从 state 获取 new_value
                    new_value = state.get(field_name)
                    
                    # 如果主字段无值，尝试 fallback_fields
                    if not new_value and field_spec.fallback_fields:
                        for fallback_field in field_spec.fallback_fields:
                            fallback_value = state.get(fallback_field)
                            if fallback_value:
                                new_value = fallback_value
                                log_parts.append(
                                    f"字段 '{field_name}' 未提供新值，使用 '{fallback_field}' 的值作为替换内容"
                                )
                                break
                    
                    if not new_value:
                        log_parts.append(
                            f"字段 '{field_name}' 有占位符 '{old_value}' 但 state 中没有新值，跳过"
                        )
                        continue

                    if field_spec.new_value_formatter is not None:
                        new_value = field_spec.new_value_formatter(new_value)
                        if not new_value:
                            log_parts.append(
                                f"字段 '{field_name}' 新值格式化后为空，跳过"
                            )
                            continue
                    
                    # 应用 skip_if_equal 规则
                    if field_spec.skip_if_equal and old_value == new_value:
                        log_parts.append(
                            f"字段 '{field_name}': 旧值等于新值，跳过"
                        )
                        continue

                    old_value = str(old_value)
                    new_value = str(new_value)
                    replacement_candidate = {
                        "field_name": field_name,
                        "old_value": old_value,
                        "new_value": new_value,
                    }
                    existing_index = candidate_index_by_old_value.get(old_value)
                    if existing_index is None:
                        candidate_index_by_old_value[old_value] = len(replacement_candidates)
                        replacement_candidates.append(replacement_candidate)
                        log_parts.append(
                            f"为字段 '{field_name}' 生成替换: '{old_value}' -> '{new_value}'"
                        )
                        continue

                    existing_candidate = replacement_candidates[existing_index]
                    existing_field_name = existing_candidate["field_name"]
                    existing_new_value = existing_candidate["new_value"]
                    current_priority = _replacement_priority(field_name)
                    existing_priority = _replacement_priority(existing_field_name)

                    if existing_new_value == new_value:
                        if current_priority < existing_priority:
                            replacement_candidates[existing_index] = replacement_candidate
                            log_parts.append(
                                f"字段 '{field_name}' 与 '{existing_field_name}' 共享占位符 '{old_value}'，"
                                f"新值一致，保留优先级更高的 '{field_name}'"
                            )
                        else:
                            log_parts.append(
                                f"字段 '{field_name}' 与 '{existing_field_name}' 共享占位符 '{old_value}'，"
                                f"新值一致，沿用 '{existing_field_name}'"
                            )
                        continue

                    if current_priority < existing_priority:
                        replacement_candidates[existing_index] = replacement_candidate
                        log_parts.append(
                            f"字段 '{field_name}' 与 '{existing_field_name}' 共享占位符 '{old_value}'，"
                            f"新值冲突，保留优先级更高的 '{field_name}'，跳过 '{existing_field_name}'"
                        )
                    else:
                        log_parts.append(
                            f"字段 '{field_name}' 与 '{existing_field_name}' 共享占位符 '{old_value}'，"
                            f"新值冲突，保留 '{existing_field_name}'，跳过 '{field_name}'"
                        )

                replacements = [
                    (candidate["old_value"], candidate["new_value"])
                    for candidate in replacement_candidates
                ]
                replacement_fields_aligned = [
                    candidate["field_name"] for candidate in replacement_candidates
                ]
                
                # 汇总替换结果
                if not replacements:
                    log_parts.append("未生成任何替换 (所有字段要么缺失要么未更改)")
                else:
                    log_parts.append(f"生成了 {len(replacements)} 对替换")
                    # 详细列出所有替换对（截断过长值）
                    for i, (old_val, new_val) in enumerate(replacements, 1):
                        old_display = old_val[:50] + "..." if len(old_val) > 50 else old_val
                        new_display = new_val[:50] + "..." if len(new_val) > 50 else new_val
                        log_parts.append(f"  [{i}] ({old_display}, {new_display})")
            else:
                log_parts.append("未找到占位符映射，跳过替换生成")
                replacements = []
                replacement_fields_aligned = []
            
            # 构建替换日志字符串
            replacement_log = "; ".join(log_parts)
            
            # 只返回需要更新的键，避免并行执行时的状态冲突
            return TenderGraphStateBase(
                placeholder_mapping=found_placeholders,
                replacements=replacements,
                replacement_fields=replacement_fields_aligned,
                replacement_log=replacement_log
            )

        except Exception as e:
            error_msg = f"读取文档时出错: {e}"
            logger.error(error_msg)
            # 在重新抛出异常之前，确保关闭文档和 Word
            if doc is not None:
                try:
                    doc.Close(SaveChanges=False)
                except Exception:
                    pass
            if word is not None:
                close_word_application(
                    word_app=word,
                    doc=None,
                    com_initialized=com_initialized,
                    wait_time=0.0,
                    node_name="get_replacements"
                )
            elif com_initialized:
                try:
                    close_word_application(
                        word_app=None,
                        doc=None,
                        com_initialized=True,
                        wait_time=0.0,
                        node_name="get_replacements"
                    )
                except Exception:
                    pass
            raise
        finally:
            # 使用统一的工具函数关闭 Word 应用程序
            close_word_application(
                word_app=word,
                doc=doc,
                com_initialized=com_initialized,
                wait_time=1.5,
                node_name="get_replacements"
            )
            logger.info("资源清理完成")

    except Exception as e:
        error_msg = f"初始化 Word COM 时出错: {e}"
        logger.error(error_msg)
        # 即使发生异常，也要确保关闭 Word 和清理 COM
        if word is not None:
            try:
                close_word_application(
                    word_app=word,
                    doc=doc,
                    com_initialized=com_initialized,
                    wait_time=0.0,
                    node_name="get_replacements"
                )
            except Exception:
                pass
        elif com_initialized:
            try:
                close_word_application(
                    word_app=None,
                    doc=None,
                    com_initialized=True,
                    wait_time=0.0,
                    node_name="get_replacements"
                )
            except Exception:
                pass
        raise
