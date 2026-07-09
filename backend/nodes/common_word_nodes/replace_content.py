from __future__ import annotations

import os
import re
import time
import pathlib
import sys
from dataclasses import dataclass
from typing import Any

# 添加项目根目录到 sys.path
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.states import TenderGraphStateBase
from backend.config.tender_config import get_tender_type_family
from backend.util.log_util.progress_log import progress_log
from backend.util.word_util import (
    create_word_application,
    close_word_application,
    open_document_with_retry,
    unprotect_document,
)
from backend.util.word_util import (
    wdFindStop,
    wdCollapseEnd,
    wdActiveEndPageNumber,
)
from backend.nodes.gjgk_word_nodes.gjgk_replace_content import (
    build_gjgk_special_replacements,
)


def _get_page_number(rng) -> int:
    """
    获取 Word Range 所在的页数。
    
    返回页数，如果无法获取则返回 -1。
    """
    try:
        page_num = rng.Information(wdActiveEndPageNumber)
        return int(page_num) if page_num else -1
    except Exception:
        return -1


def _normalize_find_text(text: str) -> str:
    if text is None:
        return ""
    text = str(text)
    text = text.replace("\x07", "")
    if "\r" in text or "\n" in text:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = text.replace("\n", "^p")
    return text


def _normalize_replace_text(text: str) -> str:
    if text is None:
        return ""
    text = str(text)
    text = text.replace("\x07", "")
    if "\n" in text and "\r" not in text:
        text = text.replace("\n", "\r")
    return text


@dataclass(frozen=True)
class ReplacementEntry:
    field_name: str | None
    search_text: str
    replace_text: str
    comment_label: str | None = None


ERP_COMMENT_LABEL = "ERP数据"
PROJECT_NAME_FIRST_HIT_COMMENT = "此次文件由AI生成，请业务员不要删除该条批注，由管理组统一删除"
INVESTMENT_SUFFIX_PATTERN = re.compile(r"^\s*万\s*元")
WORD_FIND_TEXT_MAX_LEN = 256


def _ranges_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    a_start = int(a_start)
    a_end = int(a_end)
    b_start = int(b_start)
    b_end = int(b_end)

    # Word 里的批注锚点有时会退化成零宽范围；判重时需要把这类贴边锚点
    # 视为与正文命中处相同的落点，避免重复插入同文案批注。
    a_is_collapsed = a_start == a_end
    b_is_collapsed = b_start == b_end

    if a_is_collapsed and b_is_collapsed:
        return a_start == b_start
    if a_is_collapsed:
        return b_start <= a_start <= b_end
    if b_is_collapsed:
        return a_start <= b_start <= a_end

    return not (a_end <= b_start or b_end <= a_start)


def _get_comment_range(comment: Any) -> Any | None:
    for attr in ("Scope", "Reference", "Range"):
        try:
            value = getattr(comment, attr)
        except Exception:
            value = None
        if value is not None:
            return value
    return None


def _get_overlapping_comments(doc, target_rng) -> list[Any]:
    overlapping_comments: list[Any] = []
    try:
        comments = doc.Comments
        count = int(comments.Count)
    except Exception:
        return overlapping_comments

    for idx in range(1, count + 1):
        try:
            comment = comments(idx)
        except Exception:
            continue

        comment_rng = _get_comment_range(comment)
        if comment_rng is None:
            continue

        try:
            comment_start = int(comment_rng.Start)
            comment_end = int(comment_rng.End)
            target_start = int(target_rng.Start)
            target_end = int(target_rng.End)
        except Exception:
            continue

        if _ranges_overlap(comment_start, comment_end, target_start, target_end):
            overlapping_comments.append(comment)

    return overlapping_comments


def _range_following_text(match_rng, story_rng, lookahead_chars: int = 8) -> str:
    try:
        start = int(match_rng.End)
        story_end = int(story_rng.End)
        if start >= story_end:
            return ""

        tail_rng = story_rng.Duplicate
        tail_rng.Start = start
        tail_rng.End = min(start + int(lookahead_chars), story_end)
        return str(tail_rng.Text or "")
    except Exception:
        return ""


def _normalize_comment_text(text: Any) -> str:
    value = str(text or "")
    return value.replace("\x07", "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _get_comment_text(comment: Any) -> str:
    for getter in (
        lambda: comment.Text,
        lambda: comment.Range.Text,
    ):
        try:
            return _normalize_comment_text(getter())
        except Exception:
            continue

    return ""


def _build_adjacent_comment_ranges(target_rng) -> list[Any]:
    candidate_ranges: list[Any] = []
    seen_positions: set[tuple[int, int]] = set()

    try:
        target_start = int(target_rng.Start)
        target_end = int(target_rng.End)
    except Exception:
        return candidate_ranges

    for start, end in (
        (target_end, target_end + 1),
        (target_start - 1, target_start),
    ):
        if start < 0 or end <= start:
            continue

        try:
            candidate_rng = target_rng.Duplicate
            candidate_rng.Start = start
            candidate_rng.End = end
            candidate_start = int(candidate_rng.Start)
            candidate_end = int(candidate_rng.End)
            candidate_text = str(candidate_rng.Text or "")
        except Exception:
            continue

        position_key = (candidate_start, candidate_end)
        if candidate_end <= candidate_start or not candidate_text or position_key in seen_positions:
            continue

        seen_positions.add(position_key)
        candidate_ranges.append(candidate_rng)

    return candidate_ranges


def _has_comment_with_text_on_ranges(doc, target_ranges: list[Any], text: str) -> bool:
    normalized_target_text = _normalize_comment_text(text)
    if not normalized_target_text:
        return False

    seen_comment_ids: set[int] = set()
    for target_rng in target_ranges:
        for comment in _get_overlapping_comments(doc, target_rng):
            comment_id = id(comment)
            if comment_id in seen_comment_ids:
                continue
            seen_comment_ids.add(comment_id)
            if _get_comment_text(comment) == normalized_target_text:
                return True

    return False


def _add_project_name_first_hit_comment(doc, target_rng) -> str:
    candidate_ranges = [target_rng.Duplicate]
    candidate_ranges.extend(_build_adjacent_comment_ranges(target_rng))

    if _has_comment_with_text_on_ranges(doc, candidate_ranges, PROJECT_NAME_FIRST_HIT_COMMENT):
        return "已存在同文案，跳过重复新增"

    try:
        doc.Comments.Add(
            Range=target_rng.Duplicate,
            Text=PROJECT_NAME_FIRST_HIT_COMMENT,
        )
        return "新增批注"
    except Exception as primary_error:
        last_error: Exception = primary_error

    for candidate_rng in candidate_ranges[1:]:
        if _get_overlapping_comments(doc, candidate_rng):
            continue

        try:
            doc.Comments.Add(
                Range=candidate_rng.Duplicate,
                Text=PROJECT_NAME_FIRST_HIT_COMMENT,
            )
            return "邻位新增批注"
        except Exception as candidate_error:
            last_error = candidate_error

    raise RuntimeError(f"原范围新增失败且邻位重试未成功: {last_error}") from last_error


def replace_content(state: TenderGraphStateBase, config) -> TenderGraphStateBase:
    """
    在 Word 文档中替换指定的内容，包括页眉页脚等所有部分。
    
    从 state 中读取 replacements 列表（由 get_replacements 节点生成）。
    替换前会检查内容是否处于保护状态，受保护的内容不会被替换。
    
    Word 文档的页眉页脚类型说明：
    - 首页页眉/页脚：文档第一页的页眉页脚（如果启用了"首页不同"选项）
    - 奇数页页眉/页脚（Primary）：第1、3、5...页的页眉页脚
    - 偶数页页眉/页脚（Even Pages）：第2、4、6...页的页眉页脚
    这种设计主要用于双面打印，使左右页面的页眉页脚可以不同。
    
    日志会记录：
    - 找到了多少条替换的内容
    - 多少条已被成功替换
    - 多少条因为保护状态替换失败
    - 失败的内容和所在页数
    """
    start_time = time.time()
    progress_log.info("[replace_content] 开始执行...")
    
    prepared_doc_path = state.get("prepared_doc_path")
    
    if not prepared_doc_path:
        raise ValueError("需要 prepared_doc_path 来替换 Word 文档中的内容")
    
    # 确保路径是绝对路径（Word COM 对象需要绝对路径）
    if not os.path.isabs(prepared_doc_path):
        prepared_doc_path = os.path.abspath(prepared_doc_path)
    
    # 检查文件是否存在
    if not os.path.exists(prepared_doc_path):
        raise FileNotFoundError(f"未找到准备好的文档: {prepared_doc_path}")
    
    # 检查文件是否可读
    if not os.access(prepared_doc_path, os.R_OK):
        raise PermissionError(f"无法读取准备好的文档: {prepared_doc_path}")
    
    # 获取替换列表
    replacements = state.get("replacements")
    tender_type = state.get("tender_type", "xjcg")
    tender_type_family = get_tender_type_family(tender_type)
    enable_erp_comments = tender_type_family in ("gngk", "xjcg", "gjgk")
    derived_state_updates: dict[str, str] = {}
    
    # 如果没有需要替换的内容，直接返回
    if not replacements and tender_type != "gjgk":
        replacement_log = "未指定替换内容，跳过内容替换。"
        new_state_dict = dict(state)
        new_state_dict["replacement_log"] = replacement_log
        new_state = TenderGraphStateBase(**new_state_dict)
        return new_state
    
    replacement_log_parts = []
    word = None
    doc = None
    com_initialized = False
    
    # 统计信息
    total_stats = {
        "total_found": 0,
        "total_replaced": 0,
        "total_error": 0,
        "total_comment_added": 0,
        "total_comment_error": 0,
    }
    
    # 记录失败的替换详情
    failed_replacements = []
    found_any_replacements = {}
    
    try:
        # 使用统一的工具函数创建 Word 应用程序
        # 独立实例 + 预留时间，避免前序节点关闭未完成导致句柄失效
        word, com_initialized = create_word_application(
            initial_delay=1.0,  # 创建前等待 1 秒，让之前的实例有时间完全关闭
            post_init_delay=1.0,  # 给 Word 完成初始化的时间
            use_existing=False,  # 使用独立实例
            verify=False,  # 验证步骤在工具函数中已包含
            node_name="replace_content"
        )
        
        # 使用统一的工具函数打开文档（带重试机制）
        doc = open_document_with_retry(
            word_app=word,
            file_path=prepared_doc_path,
            read_only=False,
            node_name="replace_content"
        )
        replacement_log_parts.append(f"已打开: {prepared_doc_path}")
        
        # 使用统一的工具函数取消文档保护
        unprotect_document(doc, node_name="replace_content")
        
        placeholder_mapping = state.get("placeholder_mapping", {}) or {}
        replacement_field_names = state.get("replacement_fields") or []
        replacement_entries: list[ReplacementEntry] = []
        for idx, replacement in enumerate(replacements or []):
            field_name = None
            if idx < len(replacement_field_names):
                field_name = str(replacement_field_names[idx] or "").strip() or None

            if isinstance(replacement, dict):
                search_text = replacement.get("search_text")
                replace_text = replacement.get("replace_text")
                field_name = str(replacement.get("field_name") or field_name or "").strip() or None
            else:
                try:
                    search_text, replace_text = replacement
                except Exception:
                    continue

            if not str(search_text or "").strip():
                continue

            replacement_entries.append(
                ReplacementEntry(
                    field_name=field_name,
                    search_text=str(search_text or ""),
                    replace_text=str(replace_text or ""),
                    comment_label=ERP_COMMENT_LABEL if enable_erp_comments else None,
                )
            )

        if tender_type_family == "gjgk":
            gjgk_entries, gjgk_state_updates, gjgk_logs = build_gjgk_special_replacements(state)
            replacement_entries.extend(gjgk_entries)
            derived_state_updates.update(gjgk_state_updates)
            replacement_log_parts.extend(gjgk_logs)

        if not replacement_entries:
            replacement_log_parts.append("未生成任何有效替换，跳过内容替换。")
            doc.Save()
            replacement_log_parts.append("文档已保存。")
            new_state_dict = dict(state)
            new_state_dict.update(derived_state_updates)
            new_state_dict["replacement_log"] = "\n".join(replacement_log_parts)
            new_state_dict["replace_content_done"] = True
            return TenderGraphStateBase(**new_state_dict)

        progress_log.info(f"开始替换 {len(replacement_entries)} 对替换内容...")
        
        # 判断哪些替换是项目内容、项目名称和项目编号
        # 通过 placeholder_mapping 来判断
        project_content_placeholder = placeholder_mapping.get("project_content")
        project_content_v1_placeholder = placeholder_mapping.get("project_content_v1")
        project_content_labeled_placeholders = {
            value
            for key, value in placeholder_mapping.items()
            if (
                (
                    key.startswith("project_content_") and key.endswith("_line")
                )
                or key == "project_content_v2"
            )
            and value
        }
        project_number_placeholder = placeholder_mapping.get("project_number")
        project_name_placeholder = placeholder_mapping.get("project_name")
        investment_placeholder = placeholder_mapping.get("investment")
        enable_project_name_first_hit_comment = bool(
            enable_erp_comments
            and project_name_placeholder
            and str(project_name_placeholder).strip()
        )
        project_name_comment_tracker = {
            "first_candidate_hit": False,
            "first_candidate_mode": "",
            "first_candidate_page": -1,
            "first_candidate_error": "",
            "fallback_count": 0,
            "total_candidates": 0,
            "final_success": False,
            "final_mode": "",
            "final_hit_index": 0,
            "final_page": -1,
        }
        
        # 将替换对分为三类：
        # 1. project_content_replacements - 项目内容（含 project_content 与 project_content_v1，最先处理，只在正文中）
        # 2. header_replacements - 项目名称和项目编号（在页眉和正文中）
        # 3. body_replacements - 其他内容（只在正文中）
        project_content_replacements = []  # 项目内容替换（最先处理）
        header_replacements = []  # 需要遍历页眉和正文的替换
        body_replacements = []    # 只需要遍历正文的替换
        
        project_content_field_names = {
            "project_content",
            "project_content_v1",
            "project_content_v2",
        }
        project_content_field_names.update(
            key
            for key in placeholder_mapping.keys()
            if key.startswith("project_content_") and key.endswith("_line")
        )
        header_field_names = {"project_number", "project_name"}

        for entry in replacement_entries:
            if entry.field_name in project_content_field_names:
                project_content_replacements.append(entry)
            elif entry.field_name in header_field_names:
                header_replacements.append(entry)
            elif (
                entry.search_text == project_content_placeholder
                or entry.search_text == project_content_v1_placeholder
                or entry.search_text in project_content_labeled_placeholders
            ):
                project_content_replacements.append(entry)
            elif (
                entry.search_text == project_number_placeholder
                or entry.search_text == project_name_placeholder
            ):
                header_replacements.append(entry)
            else:
                body_replacements.append(entry)

        for entry in replacement_entries:
            normalized_search_text = _normalize_find_text(entry.search_text)
            if normalized_search_text not in found_any_replacements:
                found_any_replacements[normalized_search_text] = False
        
        story_type_names = {
            1: "正文",
            6: "偶数页页眉",
            7: "奇数页页眉",
            10: "首页页眉",
        }
        
        # 定义需要处理的 StoryType
        # 项目内容：只处理正文(1) - 最先处理
        # 项目名称和项目编号：正文(1) + 页眉(6, 7, 10)
        # 其他内容：只处理正文(1)
        project_content_story_types = {1}  # 只处理正文
        header_story_types = {1, 6, 7, 10}  # 正文和所有页眉
        body_story_types = {1}  # 只处理正文
        
        def process_replacements_in_range(rng, replacements_to_process, story_type_name, story_type: int, allow_comments: bool):
            """在指定的 Range 中处理替换"""
            
            for rep_idx, entry in enumerate(replacements_to_process, 1):
                normalized_search_text = _normalize_find_text(entry.search_text)
                normalized_replace_text = _normalize_replace_text(entry.replace_text)
                is_project_name_entry = bool(
                    enable_project_name_first_hit_comment
                    and entry.search_text == project_name_placeholder
                )
                progress_log.debug(f"  [{rep_idx}/{len(replacements_to_process)}] 正在在 [{story_type_name}] 中搜索 {repr(normalized_search_text)}...")

                if len(normalized_search_text) > WORD_FIND_TEXT_MAX_LEN:
                    total_stats["total_error"] += 1
                    failed_replacements.append(
                        (
                            normalized_search_text,
                            -1,
                            f"查找串长度 {len(normalized_search_text)} 超过 Word Find 上限 {WORD_FIND_TEXT_MAX_LEN}，已跳过",
                        )
                    )
                    progress_log.warning(
                        f"    [跳过] [{story_type_name}] 查找串长度 {len(normalized_search_text)} 超过 Word Find 上限 {WORD_FIND_TEXT_MAX_LEN}"
                    )
                    continue
                
                # 创建搜索范围的副本，避免丢失原始引用
                search_rng = rng.Duplicate
                find = search_rng.Find
                find.ClearFormatting()
                find.Text = normalized_search_text
                find.Forward = True
                find.Wrap = wdFindStop
                find.MatchCase = False
                find.MatchWholeWord = False
                
                count = 0
                # Execute 返回 True 如果找到
                while find.Execute():
                    # 获取页数
                    page_num = _get_page_number(search_rng)
                    page_info = f"第 {page_num} 页" if page_num > 0 else "未知页码"

                    if entry.search_text == investment_placeholder:
                        following_text = _range_following_text(search_rng, rng)
                        if not INVESTMENT_SUFFIX_PATTERN.match(following_text):
                            progress_log.debug(
                                f"    [跳过] {repr(normalized_search_text)} 在 {page_info} 后缀不是 '万元': {repr(following_text)}"
                            )
                            search_rng.Collapse(wdCollapseEnd)
                            continue

                    count += 1
                    total_stats["total_found"] += 1
                    found_any_replacements[normalized_search_text] = True
                    
                    try:
                        search_rng.Text = normalized_replace_text
                        total_stats["total_replaced"] += 1
                        progress_log.info(f"    [已替换] {repr(normalized_search_text)} -> {repr(normalized_replace_text)} 在 {page_info}")

                        comment_label = entry.comment_label if allow_comments else None
                        if comment_label and normalized_replace_text is not None and str(normalized_replace_text).strip() != "":
                            should_apply_first_hit_comment = bool(
                                is_project_name_entry
                                and story_type == 1
                                and not project_name_comment_tracker["final_success"]
                            )
                            if should_apply_first_hit_comment:
                                project_name_comment_tracker["total_candidates"] += 1
                                current_hit_index = int(project_name_comment_tracker["total_candidates"])
                                if current_hit_index == 1:
                                    project_name_comment_tracker["first_candidate_hit"] = True
                                    project_name_comment_tracker["first_candidate_page"] = page_num

                                try:
                                    comment_write_mode = _add_project_name_first_hit_comment(doc, search_rng)
                                    if comment_write_mode != "已存在同文案，跳过重复新增":
                                        total_stats["total_comment_added"] += 1
                                    project_name_comment_tracker["final_success"] = True
                                    project_name_comment_tracker["final_mode"] = comment_write_mode
                                    project_name_comment_tracker["final_hit_index"] = current_hit_index
                                    project_name_comment_tracker["final_page"] = page_num
                                    if current_hit_index == 1:
                                        project_name_comment_tracker["first_candidate_mode"] = comment_write_mode
                                except Exception as e:
                                    total_stats["total_comment_error"] += 1
                                    failed_replacements.append(
                                        (
                                            normalized_search_text,
                                            page_num,
                                            f"project_name 首命中特殊批注失败: {e}",
                                        )
                                    )
                                    project_name_comment_tracker["fallback_count"] += 1
                                    if current_hit_index == 1:
                                        project_name_comment_tracker["first_candidate_mode"] = "处理失败"
                                        project_name_comment_tracker["first_candidate_error"] = str(e)
                                    progress_log.warning(
                                        f"    [批注特殊处理失败] project_name 在 {page_info} 第 {current_hit_index} 个命中写入长提示失败: {e}"
                                    )
                            else:
                                try:
                                    doc.Comments.Add(Range=search_rng.Duplicate, Text=str(comment_label))
                                    total_stats["total_comment_added"] += 1
                                except Exception as e:
                                    total_stats["total_comment_error"] += 1
                                    failed_replacements.append((normalized_search_text, page_num, f"添加批注失败: {e}"))
                        
                        search_rng.Collapse(wdCollapseEnd)
                    except Exception as e:
                        total_stats["total_error"] += 1
                        failed_replacements.append((normalized_search_text, page_num, str(e)))
                        progress_log.error(f"    [错误] 在 {page_info} 找到 {repr(normalized_search_text)} 但编辑失败: {e}")
                        search_rng.Collapse(wdCollapseEnd)
                
                if count > 0:
                    progress_log.info(f"  摘要: 在 [{story_type_name}] 中将 {repr(normalized_search_text)} 替换为 {repr(normalized_replace_text)} 共 {count} 处")
        
        # 一次遍历处理所有替换，按优先级顺序：project_content -> header -> body
        if project_content_replacements:
            progress_log.info(f"正在处理项目内容替换 ({len(project_content_replacements)} 对) 在正文中（优先处理）...")
        if header_replacements:
            progress_log.info(f"正在处理项目编号/项目名称替换 ({len(header_replacements)} 对) 在页眉和正文中...")
        if body_replacements:
            progress_log.info(f"正在处理其他替换 ({len(body_replacements)} 对) 仅在正文中...")
        
        # 遍历所有 StoryRanges，根据类型决定处理哪些替换
        # 处理顺序：1. project_content（正文） 2. header（页眉和正文） 3. body（正文）
        for story_range in doc.StoryRanges:
            rng = story_range
            while rng:
                story_type = rng.StoryType
                story_type_name = story_type_names.get(story_type, f"未知类型 {story_type}")
                
                # 1. 优先处理项目内容（只在正文中）
                if project_content_replacements and story_type in project_content_story_types:
                    progress_log.debug(f"正在处理 [{story_type_name}]...")
                    process_replacements_in_range(
                        rng,
                        project_content_replacements,
                        story_type_name,
                        story_type,
                        allow_comments=(enable_erp_comments and story_type == 1),
                    )
                
                # 2. 处理项目名称和项目编号（在正文和页眉中）
                if header_replacements and story_type in header_story_types:
                    # 如果已经在处理 project_content 时打印过，这里不再重复打印
                    if not (project_content_replacements and story_type in project_content_story_types):
                        progress_log.debug(f"正在处理 [{story_type_name}]...")
                    process_replacements_in_range(
                        rng,
                        header_replacements,
                        story_type_name,
                        story_type,
                        allow_comments=(enable_erp_comments and story_type == 1),
                    )
                
                # 3. 处理其他内容（只在正文中）
                if body_replacements and story_type in body_story_types:
                    # 如果已经在处理 project_content 或 header 时打印过，这里不再重复打印
                    if not (project_content_replacements and story_type in project_content_story_types) and \
                       not (header_replacements and story_type in header_story_types):
                        progress_log.debug(f"正在处理 [{story_type_name}]...")
                    process_replacements_in_range(
                        rng,
                        body_replacements,
                        story_type_name,
                        story_type,
                        allow_comments=(enable_erp_comments and story_type == 1),
                    )
                
                try:
                    rng = rng.NextStoryRange
                except:
                    break
        
        # 生成最终统计报告
        replacement_log_parts.append("=" * 60)
        replacement_log_parts.append("替换摘要:")
        replacement_log_parts.append(f"  总计找到: {total_stats['total_found']}")
        replacement_log_parts.append(f"  成功替换: {total_stats['total_replaced']}")
        replacement_log_parts.append(f"  失败 (错误): {total_stats['total_error']}")
        if enable_erp_comments:
            replacement_log_parts.append(f"  已添加批注: {total_stats['total_comment_added']}")
            replacement_log_parts.append(f"  批注失败: {total_stats['total_comment_error']}")
            if enable_project_name_first_hit_comment:
                replacement_log_parts.append("")
                replacement_log_parts.append("project_name 正文首命中特殊批注轨迹:")
                replacement_log_parts.append(
                    f"  首个候选是否命中: {'是' if project_name_comment_tracker['first_candidate_hit'] else '否'}"
                )
                if project_name_comment_tracker["first_candidate_hit"]:
                    replacement_log_parts.append(
                        f"  首个候选处理方式: {project_name_comment_tracker['first_candidate_mode'] or '未处理'}"
                    )
                    first_page_num = int(project_name_comment_tracker["first_candidate_page"])
                    first_page_info = f"第 {first_page_num} 页" if first_page_num > 0 else "未知页码"
                    replacement_log_parts.append(f"  首个候选页码: {first_page_info}")
                    if project_name_comment_tracker["first_candidate_error"]:
                        replacement_log_parts.append(
                            f"  首个候选失败原因: {project_name_comment_tracker['first_candidate_error']}"
                        )
                replacement_log_parts.append(
                    f"  是否发生 fallback 到后续 project_name: {'是' if project_name_comment_tracker['fallback_count'] > 0 else '否'}"
                )
                replacement_log_parts.append(
                    f"  fallback 次数: {project_name_comment_tracker['fallback_count']}"
                )
                if project_name_comment_tracker["final_success"]:
                    final_page_num = int(project_name_comment_tracker["final_page"])
                    final_page_info = f"第 {final_page_num} 页" if final_page_num > 0 else "未知页码"
                    replacement_log_parts.append(
                        "  特殊批注最终落位: "
                        f"第 {project_name_comment_tracker['final_hit_index']} 个正文 project_name 命中"
                        f"（{final_page_info}，{project_name_comment_tracker['final_mode']}）"
                    )
                else:
                    replacement_log_parts.append("  特殊批注最终落位: 未成功落位")
        
        if failed_replacements:
            replacement_log_parts.append("")
            replacement_log_parts.append("失败的替换:")
            for search_text, page_num, reason in failed_replacements:
                page_info = f"第 {page_num} 页" if page_num > 0 else "未知页码"
                replacement_log_parts.append(f"  - '{search_text}' 在 {page_info}: {reason}")
        not_found_replacements = [k for k, v in found_any_replacements.items() if not v]
        if not_found_replacements:
            replacement_log_parts.append("")
            replacement_log_parts.append("未找到的替换:")
            for search_text in not_found_replacements:
                replacement_log_parts.append(f"  - {repr(search_text)}")
        
        replacement_log_parts.append("=" * 60)
        replacement_log_parts.append("内容替换完成。")
        
        doc.Save()
        replacement_log_parts.append("文档已保存。")
            
    finally:
        progress_log.info("[replace_content] 开始清理资源...")
        # 使用统一的工具函数关闭 Word 应用程序
        close_word_application(
            word_app=word,
            doc=doc,
            com_initialized=com_initialized,
            wait_time=1.5,
            node_name="replace_content"
        )
    
    # Update state with replacement log
    new_state_dict = dict(state)
    new_state_dict.update(derived_state_updates)
    # 使用换行符连接日志，使输出更易读
    replacement_log = "\n".join(replacement_log_parts)
    new_state_dict["replacement_log"] = replacement_log
    new_state_dict["replace_content_done"] = True
    new_state = TenderGraphStateBase(**new_state_dict)
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    progress_log.info(f"[replace_content] 执行完成，耗时: {elapsed_time:.2f} 秒 ({elapsed_time*1000:.0f} 毫秒)")
    
    return new_state
