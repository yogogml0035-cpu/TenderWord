"""
Word 正文行内样式抽取与回填 helper。

当前边界：
- 只处理锚点区正文段落与表格单元格
- 只处理 run/字符级样式，不处理段落版式
- 回填策略以高召回为先，但仍保留最低安全线避免盲写
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable, Dict, Iterable, Literal, Optional, Sequence, TypedDict

from backend.helper.word_helper.semantic_matcher import (
    normalize_semantic_text,
    semantic_similarity,
    semantic_similarity_norm,
    strip_number_prefix,
)
from backend.util.word_util import wdWithInTable

ContainerType = Literal["paragraph", "table_cell"]
SourceSpanKind = Literal["full_container", "partial_span", "number_prefix"]

CONTROL_CHAR_TEXT = {"\a": "", "\x07": "", "\f": "", "\r": "\n", "\n": "\n", "\v": "\n"}
BLACK_COLOR = 0
AUTOMATIC_COLOR = 0
WINDOWS_AUTO_COLOR = -16777216
NO_HIGHLIGHT = 0
FONT_COLOR_GATE_VERSION = "fail_closed_v3"
CONTEXT_CHARS = 24
CONTAINER_CANDIDATE_LIMIT = 5
APPROX_LOCAL_SCAN_WINDOW = 18
LOG_TEXT_LIMIT = 80
CANDIDATE_DIAGNOSTIC_LIMIT = 3
SHORT_TITLE_MAX_LEN = 8
SHORT_FULL_CONTAINER_MAX_LEN = 16
SHORT_PARTIAL_MAX_LEN = 6
SHORT_PARTIAL_EXACT_ONLY_MAX_LEN = 3
SHORT_PARTIAL_CONTEXT_MIN_SCORE = 0.72
SHORT_PARTIAL_EXACT_CONTAINER_MIN_SCORE = 0.50
SHORT_PARTIAL_APPROX_MIN_SCORE = 0.82
SHORT_PARTIAL_HIGH_VISIBLE_APPROX_MIN_SCORE = 0.88
SHORT_PARTIAL_CONTAINER_MIN_SCORE = 0.78
TABLE_SHORT_PARTIAL_APPROX_MIN_SCORE = 0.86
TABLE_SHORT_PARTIAL_HIGH_VISIBLE_APPROX_MIN_SCORE = 0.90
TABLE_SHORT_PARTIAL_STRUCTURE_MIN_SCORE = 0.84
TABLE_SHORT_PARTIAL_CONTAINER_MIN_SCORE = 0.82
FONT_COLOR_CONTAINER_MIN_SCORE = 0.78
FONT_COLOR_SINGLE_CONTEXT_CONTAINER_MIN_SCORE = 0.90
FONT_COLOR_SINGLE_CONTEXT_MIN_LEN = 7
SUCCESS_EXAMPLE_LIMIT = 3
SUCCESS_EXAMPLE_TEXT_LIMIT = 24
SHORT_HIGH_FREQUENCY_COLOR_TOKENS = {
    "提供",
    "投标人",
    "单位",
    "要求",
    "服务",
    "设备",
}
HEADING_TEXT_RE = re.compile(
    r"^\s*(?:"
    r"第?[一二三四五六七八九十百千]+(?:章|节|部分)"
    r"|[（(][一二三四五六七八九十]+[)）]"
    r"|[一二三四五六七八九十]+[、.．])"
)
LEADING_DOTTED_NUMBER_RE = re.compile(r"^\s*\d+(?:\.\d+)+\s+(?=\S)")

STYLE_LABEL_MAP = {
    "bold": "加粗",
    "underline": "下划线",
    "italic": "斜体",
    "strikethrough": "删除线",
    "font_color": "字体颜色",
    "highlight_color": "高亮",
}
REASON_LABEL_MAP = {
    "apply_failed": "写回样式失败",
    "empty_fragment": "源样式片段为空",
    "empty_search_bound": "样式回填搜索范围为空",
    "empty_target_span": "命中的目标文本范围为空",
    "low_confidence": "相似度不足",
    "low_local_confidence": "局部文本相似度不足",
    "multiple_candidate_conflict": "存在多个候选位置，无法唯一定位",
    "multiple_local_candidates": "存在多个局部命中位置，无法唯一定位",
    "no_candidate_container": "未找到可回填的目标容器",
    "no_partial_candidate_container": "未找到可承接局部样式的目标容器",
    "no_same_table_candidate": "同表内未找到可回填的目标单元格",
    "no_title_candidate_container": "未找到可承接标题样式的目标段落",
    "no_local_candidate": "未找到局部文本命中位置",
    "no_number_prefix_target": "目标行未找到编号前缀",
    "number_prefix_high_visible_style": "编号前缀包含高风险可见样式",
    "short_fragment_prefix_conflict": "短片段命中目标编号前缀",
    "short_fragment_semantic_mismatch": "短片段上下文不匹配",
    "short_fragment_unanchored": "短片段缺少可靠锚点",
    "font_color_full_container_blocked": "字体颜色整段回填已拦截",
    "font_color_number_prefix_blocked": "字体颜色编号回填已拦截",
    "font_color_unanchored_partial": "字体颜色片段缺少可靠锚点",
    "table_structure_changed": "表格结构已变化，无法按原单元格定位",
}
SPAN_KIND_LABEL_MAP = {
    "full_container": "整容器",
    "partial_span": "局部片段",
    "number_prefix": "编号前缀",
}


class InlineStyleFlags(TypedDict):
    strikethrough: bool
    underline: bool
    bold: bool
    italic: bool


class InlineStyleContainerLocator(TypedDict, total=False):
    paragraph_index: int
    table_index: int
    row: int
    col: int


class InlineStyleFragment(TypedDict, total=False):
    container_type: ContainerType
    container_locator: InlineStyleContainerLocator
    source_text: str
    normalized_text: str
    container_text: str
    normalized_container_text: str
    context_before: str
    context_after: str
    position_ratio: float
    local_position_ratio: float
    style_flags: InlineStyleFlags
    font_color: Optional[int]
    highlight_color: Optional[int]
    font_name: Optional[str]
    font_size: Optional[float]
    underline_style: Optional[int]
    source_span_kind: SourceSpanKind
    number_prefix_text: str


class InlineStyleWritebackIssue(TypedDict, total=False):
    index: int
    reason: str
    source_text: str
    container_type: ContainerType
    container_locator: InlineStyleContainerLocator
    score: float
    error: str


class InlineStyleWritebackResult(TypedDict):
    extracted: int
    attempted: int
    applied: int
    skipped: int
    failed: int
    issues: list[InlineStyleWritebackIssue]
    applied_by_style: dict[str, int]
    skipped_by_reason: dict[str, int]


class CharacterStyleSignature(TypedDict, total=False):
    style_flags: InlineStyleFlags
    font_color: Optional[int]
    highlight_color: Optional[int]
    font_name: Optional[str]
    font_size: Optional[float]
    underline_style: Optional[int]


class StyledVisibleChar(TypedDict):
    text: str
    start: int
    end: int
    signature: CharacterStyleSignature


@dataclass(frozen=True)
class _VisibleChar:
    text: str
    start: int
    end: int
    visible_start: int
    visible_end: int
    signature: CharacterStyleSignature


@dataclass(frozen=True)
class _ContainerCandidate:
    container_type: ContainerType
    container_locator: InlineStyleContainerLocator
    visible_chars: list[_VisibleChar]
    visible_text: str
    normalized_text: str
    normalized_index_to_visible: list[int]
    logical_lines: list["_LogicalLine"]
    position_ratio: float
    range_start: int
    range_end: int


@dataclass(frozen=True)
class _LogicalLine:
    text: str
    normalized_text: str
    normalized_index_to_visible: list[int]
    visible_start: int
    visible_end: int
    actual_start: int
    actual_end: int
    position_ratio: float


@dataclass(frozen=True)
class _LocalMatch:
    visible_start: int
    visible_end: int
    actual_start: int
    actual_end: int
    score: float
    context_score: float
    local_position_score: float
    text_score: float = 0.0
    is_exact: bool = False


@dataclass
class _CandidateProbe:
    candidate: _ContainerCandidate
    container_score: float
    local_hint_score: float
    position_score: float
    title_score: float = 0.0
    structure_score: float = 0.0
    coarse_score: float = 0.0
    final_score: float = 0.0
    selected: bool = False
    rejection_reason: str = ""
    local_error: str = ""
    local_match: Optional[_LocalMatch] = None


def _truncate_log_text(value: Any, *, max_chars: int = LOG_TEXT_LIMIT) -> str:
    text = (
        str(value or "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\v", "\n")
        .strip()
    )
    if not text:
        return "(空)"

    compact = " / ".join(part.strip() for part in text.split("\n") if part.strip())
    if len(compact) <= max_chars:
        return compact

    head_len = max(8, (max_chars - 3) // 2)
    tail_len = max(5, max_chars - 3 - head_len)
    return f"{compact[:head_len]}...{compact[-tail_len:]}"


def _format_container_hint(
    container_type: str,
    container_locator: Optional[InlineStyleContainerLocator],
) -> str:
    locator = dict(container_locator or {})
    if container_type == "table_cell":
        table_index = locator.get("table_index")
        row = locator.get("row")
        col = locator.get("col")
        return f"表格#{table_index or '?'} 第{row or '?'}行第{col or '?'}列"

    paragraph_index = locator.get("paragraph_index")
    return f"段落#{paragraph_index or '?'}"


def _resolve_style_labels(fragment: InlineStyleFragment) -> list[str]:
    labels: list[str] = []
    style_flags = fragment.get("style_flags") or {}

    for style_name in ("bold", "underline", "italic", "strikethrough"):
        if style_flags.get(style_name):
            labels.append(STYLE_LABEL_MAP[style_name])

    if fragment.get("font_color") is not None:
        labels.append(STYLE_LABEL_MAP["font_color"])
    if fragment.get("highlight_color") is not None:
        labels.append(STYLE_LABEL_MAP["highlight_color"])

    return labels or ["未知样式"]


def _format_style_labels(fragment: InlineStyleFragment) -> str:
    return "、".join(_resolve_style_labels(fragment))


def translate_inline_style_reason(reason: str) -> str:
    return REASON_LABEL_MAP.get(str(reason or ""), str(reason or "未知原因"))


def _format_source_span_kind(fragment: InlineStyleFragment) -> str:
    kind = str(fragment.get("source_span_kind") or "partial_span")
    return SPAN_KIND_LABEL_MAP.get(kind, kind)


def _normalized_length(value: Any) -> int:
    return len(str(value or ""))


def _looks_like_heading_text(value: Any) -> bool:
    cleaned = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not cleaned:
        return False
    first_line = cleaned.split("\n", 1)[0].strip()
    return bool(HEADING_TEXT_RE.match(first_line))


def _is_number_prefix_fragment(fragment: InlineStyleFragment) -> bool:
    return str(fragment.get("source_span_kind") or "") == "number_prefix"


def _line_start_offset(text: str, offset: int) -> int:
    safe_offset = max(0, min(len(text), int(offset)))
    line_break = str(text or "").rfind("\n", 0, safe_offset)
    return 0 if line_break < 0 else line_break + 1


def _leading_number_prefix_len(line_text: str) -> int:
    line = str(line_text or "")
    if not line.strip():
        return 0
    stripped = strip_number_prefix(line)
    prefix_len = len(line) - len(stripped)
    fallback_match = LEADING_DOTTED_NUMBER_RE.match(line)
    if fallback_match is not None:
        prefix_len = max(prefix_len, fallback_match.end())
    if not line[:prefix_len].strip():
        return 0
    return prefix_len


def _is_leading_number_prefix_span(
    *,
    container_text: str,
    visible_start: int,
    visible_end: int,
) -> bool:
    if int(visible_end) <= int(visible_start):
        return False

    text = str(container_text or "")
    line_start = _line_start_offset(text, int(visible_start))
    line_text = text[line_start:]
    prefix_len = _leading_number_prefix_len(line_text)
    if prefix_len <= 0:
        return False

    line_relative_start = int(visible_start) - line_start
    line_relative_end = int(visible_end) - line_start
    return (
        line_relative_start >= 0
        and line_relative_end <= prefix_len
        and bool(text[int(visible_start) : int(visible_end)].strip())
    )


def _is_short_title_fragment(fragment: InlineStyleFragment) -> bool:
    return (
        str(fragment.get("container_type") or "paragraph") == "paragraph"
        and str(fragment.get("source_span_kind") or "partial_span") == "full_container"
        and _normalized_length(fragment.get("normalized_container_text")) <= SHORT_TITLE_MAX_LEN
        and _looks_like_heading_text(fragment.get("source_text") or fragment.get("container_text"))
    )


def _is_short_partial_fragment(fragment: InlineStyleFragment) -> bool:
    return (
        str(fragment.get("source_span_kind") or "partial_span") == "partial_span"
        and _normalized_length(fragment.get("normalized_text")) <= SHORT_PARTIAL_MAX_LEN
    )


def _is_high_visible_short_style(fragment: InlineStyleFragment) -> bool:
    if not _is_short_partial_fragment(fragment):
        return False
    style_flags = fragment.get("style_flags") or {}
    return bool(style_flags.get("strikethrough") or style_flags.get("italic"))


def _has_high_visible_risk_style(fragment: InlineStyleFragment) -> bool:
    style_flags = fragment.get("style_flags") or {}
    return bool(style_flags.get("strikethrough") or style_flags.get("italic"))


def _fragment_has_effective_style(fragment: InlineStyleFragment) -> bool:
    style_flags = fragment.get("style_flags") or {}
    return bool(
        style_flags.get("strikethrough")
        or style_flags.get("underline")
        or style_flags.get("bold")
        or style_flags.get("italic")
        or fragment.get("font_color") is not None
        or fragment.get("highlight_color") is not None
    )


def _fragment_without_font_color(fragment: InlineStyleFragment) -> InlineStyleFragment:
    clean_fragment = InlineStyleFragment(**dict(fragment))
    clean_fragment["font_color"] = None
    return clean_fragment


def _normalize_fragment_font_color(fragment: InlineStyleFragment) -> InlineStyleFragment:
    normalized_color = _normalize_font_color(fragment.get("font_color"))
    if normalized_color == fragment.get("font_color"):
        return fragment

    clean_fragment = InlineStyleFragment(**dict(fragment))
    clean_fragment["font_color"] = normalized_color
    return clean_fragment


def _is_font_color_only_partial_fragment(fragment: InlineStyleFragment) -> bool:
    return (
        fragment.get("font_color") is not None
        and str(fragment.get("source_span_kind") or "partial_span") == "partial_span"
        and not _fragment_has_effective_style(_fragment_without_font_color(fragment))
    )


def _is_full_container_font_color_fragment(fragment: InlineStyleFragment) -> bool:
    return (
        fragment.get("font_color") is not None
        and str(fragment.get("source_span_kind") or "partial_span") == "full_container"
    )


def _is_short_full_container_font_color_fragment(fragment: InlineStyleFragment) -> bool:
    if not _is_full_container_font_color_fragment(fragment):
        return False

    normalized_text = str(
        fragment.get("normalized_container_text") or fragment.get("normalized_text") or ""
    )
    return _normalized_length(normalized_text) <= SHORT_FULL_CONTAINER_MAX_LEN


def _static_font_color_block_reason(fragment: InlineStyleFragment) -> str:
    if fragment.get("font_color") is None:
        return ""
    if _is_number_prefix_fragment(fragment):
        return "font_color_number_prefix_blocked"
    if str(fragment.get("source_span_kind") or "partial_span") == "full_container":
        if _is_short_full_container_font_color_fragment(fragment):
            return ""
        return "font_color_full_container_blocked"
    return ""


def _record_skipped_style_reason(
    result: InlineStyleWritebackResult,
    reason: str,
) -> None:
    if not reason:
        return
    result["skipped_by_reason"][reason] = result["skipped_by_reason"].get(reason, 0) + 1


def _has_short_partial_context(fragment: InlineStyleFragment) -> bool:
    return any(
        _normalized_length(normalize_semantic_text(fragment.get(key))) >= 2
        for key in ("context_before", "context_after")
    )


def _short_partial_context_gate_passed(
    fragment: InlineStyleFragment,
    candidate: _ContainerCandidate,
    local_match: _LocalMatch,
) -> bool:
    if not _has_short_partial_context(fragment):
        return False

    before_context = normalize_semantic_text(fragment.get("context_before"))
    after_context = normalize_semantic_text(fragment.get("context_after"))
    before_slice = normalize_semantic_text(
        candidate.visible_text[
            max(0, local_match.visible_start - CONTEXT_CHARS) : local_match.visible_start
        ]
    )
    after_slice = normalize_semantic_text(
        candidate.visible_text[local_match.visible_end : local_match.visible_end + CONTEXT_CHARS]
    )

    before_ok = not before_context or before_slice.endswith(before_context)
    after_ok = not after_context or after_slice.startswith(after_context)
    raw_context_ok = (bool(before_context) or bool(after_context)) and before_ok and after_ok
    return raw_context_ok or float(local_match.context_score) >= SHORT_PARTIAL_CONTEXT_MIN_SCORE


def _normalized_raw_context(value: Any) -> str:
    return normalize_semantic_text(
        str(value or "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\v", "\n")
        .replace("\u00a0", " ")
    )


def _font_color_context_state(
    fragment: InlineStyleFragment,
    candidate: _ContainerCandidate,
    local_match: _LocalMatch,
) -> tuple[bool, bool, bool, bool]:
    before_context = _normalized_raw_context(fragment.get("context_before"))
    after_context = _normalized_raw_context(fragment.get("context_after"))
    before_slice = _normalized_raw_context(
        candidate.visible_text[
            max(0, local_match.visible_start - CONTEXT_CHARS) : local_match.visible_start
        ]
    )
    after_slice = _normalized_raw_context(
        candidate.visible_text[local_match.visible_end : local_match.visible_end + CONTEXT_CHARS]
    )

    before_has = bool(before_context)
    after_has = bool(after_context)
    before_ok = before_has and before_slice.endswith(before_context)
    after_ok = after_has and after_slice.startswith(after_context)
    return before_has, before_ok, after_has, after_ok


def _is_short_high_frequency_color_fragment(fragment: InlineStyleFragment) -> bool:
    normalized_text = str(fragment.get("normalized_text") or "")
    return (
        len(normalized_text) <= SHORT_PARTIAL_EXACT_ONLY_MAX_LEN
        or normalized_text in SHORT_HIGH_FREQUENCY_COLOR_TOKENS
    )


def _font_color_raw_context_gate_passed(
    fragment: InlineStyleFragment,
    candidate: _ContainerCandidate,
    local_match: _LocalMatch,
    *,
    container_score: float,
) -> bool:
    before_has, before_ok, after_has, after_ok = _font_color_context_state(
        fragment,
        candidate,
        local_match,
    )
    has_both_contexts = before_has and after_has
    both_contexts_match = before_ok and after_ok
    same_locator = _container_locator_equals(
        candidate.container_locator,
        dict(fragment.get("container_locator") or {}),
    )

    if _is_short_high_frequency_color_fragment(fragment):
        return has_both_contexts and both_contexts_match and same_locator

    if has_both_contexts:
        return both_contexts_match

    single_context_matches = before_ok or after_ok
    return (
        single_context_matches
        and _normalized_length(fragment.get("normalized_text")) >= FONT_COLOR_SINGLE_CONTEXT_MIN_LEN
        and float(container_score) >= FONT_COLOR_SINGLE_CONTEXT_CONTAINER_MIN_SCORE
    )


def _count_exact_occurrences_in_candidates(
    candidates: Sequence[_ContainerCandidate],
    normalized_text: str,
    *,
    locator_filter: Optional[Callable[[_ContainerCandidate], bool]] = None,
) -> int:
    if not normalized_text:
        return 0

    count = 0
    for candidate in candidates:
        if locator_filter is not None and not locator_filter(candidate):
            continue
        count += len(_locate_exact_occurrences(candidate, normalized_text))
    return count


def _font_color_structure_unique_gate_passed(
    fragment: InlineStyleFragment,
    candidate: _ContainerCandidate,
    candidates: Sequence[_ContainerCandidate],
    normalized_text: str,
) -> bool:
    if candidate.container_type != "table_cell":
        return False

    source_locator = dict(fragment.get("container_locator") or {})
    if not _container_locator_equals(candidate.container_locator, source_locator):
        return False

    same_locator_count = _count_exact_occurrences_in_candidates(
        candidates,
        normalized_text,
        locator_filter=lambda item: item.container_type == "table_cell"
        and _container_locator_equals(item.container_locator, source_locator),
    )
    return same_locator_count == 1


def _font_color_uniqueness_gate_passed(
    fragment: InlineStyleFragment,
    candidate: _ContainerCandidate,
    candidates: Sequence[_ContainerCandidate],
    normalized_text: str,
) -> bool:
    if len(_locate_exact_occurrences(candidate, normalized_text)) != 1:
        return False

    global_count = _count_exact_occurrences_in_candidates(candidates, normalized_text)
    if global_count == 1:
        return True

    return _font_color_structure_unique_gate_passed(
        fragment,
        candidate,
        candidates,
        normalized_text,
    )


def _normalize_full_container_color_gate_text(value: Any) -> str:
    return (
        str(value or "")
        .replace("\a", "")
        .replace("\x07", "")
        .replace("\f", "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\v", "\n")
        .replace("\u00a0", " ")
        .strip()
    )


def _full_container_color_gate_source_text(fragment: InlineStyleFragment) -> str:
    return _normalize_full_container_color_gate_text(
        fragment.get("container_text") or fragment.get("source_text")
    )


def _full_container_color_gate_normalized_text(fragment: InlineStyleFragment) -> str:
    return str(fragment.get("normalized_container_text") or fragment.get("normalized_text") or "")


def _count_full_container_color_gate_matches(
    fragment: InlineStyleFragment,
    target_containers: Sequence[_ContainerCandidate],
) -> int:
    normalized_text = _full_container_color_gate_normalized_text(fragment)
    source_visible_text = _full_container_color_gate_source_text(fragment)
    if not normalized_text or not source_visible_text:
        return 0

    return sum(
        1
        for item in target_containers
        if item.normalized_text == normalized_text
        and _normalize_full_container_color_gate_text(item.visible_text) == source_visible_text
    )


def _font_color_full_container_gate_passed(
    fragment: InlineStyleFragment,
    candidate: _ContainerCandidate,
    target_containers: Sequence[_ContainerCandidate],
) -> bool:
    if not _is_short_full_container_font_color_fragment(fragment):
        return False

    normalized_text = _full_container_color_gate_normalized_text(fragment)
    if not normalized_text or candidate.normalized_text != normalized_text:
        return False

    source_visible_text = _full_container_color_gate_source_text(fragment)
    if not source_visible_text:
        return False
    if _normalize_full_container_color_gate_text(candidate.visible_text) != source_visible_text:
        return False

    if _count_full_container_color_gate_matches(fragment, target_containers) != 1:
        return False

    if candidate.container_type == "table_cell" and not _container_locator_equals(
        candidate.container_locator,
        dict(fragment.get("container_locator") or {}),
    ):
        return False

    return True


def _font_color_partial_gate_passed(
    fragment: InlineStyleFragment,
    candidate: _ContainerCandidate,
    local_match: Optional[_LocalMatch],
    target_containers: Sequence[_ContainerCandidate],
) -> bool:
    if (
        fragment.get("font_color") is None
        or str(fragment.get("source_span_kind") or "partial_span") != "partial_span"
        or local_match is None
    ):
        return False

    if not bool(getattr(local_match, "is_exact", False)):
        return False
    if _is_target_line_leading_number_prefix_match(candidate, local_match):
        return False
    source_is_table = str(fragment.get("container_type") or "paragraph") == "table_cell"
    target_is_table = candidate.container_type == "table_cell"
    if source_is_table or target_is_table:
        if not source_is_table or not target_is_table:
            return False
        if not _container_locator_equals(
            candidate.container_locator,
            dict(fragment.get("container_locator") or {}),
        ):
            return False

    normalized_text = str(fragment.get("normalized_text") or "")
    if not normalized_text:
        return False

    container_score = semantic_similarity_norm(
        str(fragment.get("normalized_container_text") or ""),
        candidate.normalized_text,
    )
    if container_score < FONT_COLOR_CONTAINER_MIN_SCORE:
        return False

    if not _font_color_raw_context_gate_passed(
        fragment,
        candidate,
        local_match,
        container_score=container_score,
    ):
        return False

    return _font_color_uniqueness_gate_passed(
        fragment,
        candidate,
        target_containers,
        normalized_text,
    )


def _build_font_color_gate_diagnostic(
    fragment: InlineStyleFragment,
    *,
    candidate: _ContainerCandidate,
    local_match: Optional[_LocalMatch],
    target_containers: Sequence[_ContainerCandidate],
    reason: str,
) -> str:
    normalized_text = str(fragment.get("normalized_text") or "")
    container_occurrences = (
        len(_locate_exact_occurrences(candidate, normalized_text))
        if normalized_text
        else 0
    )
    global_occurrences = _count_exact_occurrences_in_candidates(
        target_containers,
        normalized_text,
    )
    container_score = semantic_similarity_norm(
        str(fragment.get("normalized_container_text") or ""),
        candidate.normalized_text,
    )
    exact = bool(getattr(local_match, "is_exact", False)) if local_match is not None else False
    prefix = (
        _is_target_line_leading_number_prefix_match(candidate, local_match)
        if local_match is not None
        else False
    )
    before_ok = False
    after_ok = False
    if local_match is not None:
        _, before_ok, _, after_ok = _font_color_context_state(
            fragment,
            candidate,
            local_match,
        )
    parts = [
        f"font_color_gate_version={FONT_COLOR_GATE_VERSION}",
        f"reason={reason}",
        f"exact={exact}",
        f"prefix={prefix}",
        f"raw_before={before_ok}",
        f"raw_after={after_ok}",
        f"container_occurrences={container_occurrences}",
        f"global_occurrences={global_occurrences}",
    ]
    if str(fragment.get("source_span_kind") or "partial_span") == "full_container":
        parts.append(
            "full_container_global_exact_matches="
            f"{_count_full_container_color_gate_matches(fragment, target_containers)}"
        )
    parts.append(f"container_score={container_score:.4f}")
    return "; ".join(parts)


def _resolve_effective_fragment_for_writeback(
    fragment: InlineStyleFragment,
    *,
    candidate: _ContainerCandidate,
    local_match: Optional[_LocalMatch],
    target_containers: Sequence[_ContainerCandidate],
) -> tuple[InlineStyleFragment, str]:
    if fragment.get("font_color") is None:
        return fragment, ""

    static_reason = _static_font_color_block_reason(fragment)
    if static_reason:
        return _fragment_without_font_color(fragment), static_reason

    if str(fragment.get("source_span_kind") or "partial_span") == "partial_span":
        if _font_color_partial_gate_passed(fragment, candidate, local_match, target_containers):
            return fragment, ""
        return _fragment_without_font_color(fragment), "font_color_unanchored_partial"

    if str(fragment.get("source_span_kind") or "partial_span") == "full_container":
        if _font_color_full_container_gate_passed(fragment, candidate, target_containers):
            return fragment, ""
        return _fragment_without_font_color(fragment), "font_color_full_container_blocked"

    return fragment, ""


def _is_target_line_leading_number_prefix_match(
    candidate: _ContainerCandidate,
    local_match: _LocalMatch,
) -> bool:
    return _is_leading_number_prefix_span(
        container_text=candidate.visible_text,
        visible_start=local_match.visible_start,
        visible_end=local_match.visible_end,
    )


def _candidate_limit(fragment: InlineStyleFragment) -> int:
    if _is_number_prefix_fragment(fragment):
        return max(CONTAINER_CANDIDATE_LIMIT, 6)
    if str(fragment.get("container_type") or "paragraph") == "table_cell":
        return max(CONTAINER_CANDIDATE_LIMIT, 6)
    if _is_short_partial_fragment(fragment):
        return max(CONTAINER_CANDIDATE_LIMIT, 8)
    if _is_short_title_fragment(fragment):
        return max(CONTAINER_CANDIDATE_LIMIT, 6)
    return CONTAINER_CANDIDATE_LIMIT


def _approx_local_scan_window(fragment: InlineStyleFragment) -> int:
    if _is_number_prefix_fragment(fragment):
        return max(APPROX_LOCAL_SCAN_WINDOW, 24)
    if str(fragment.get("container_type") or "paragraph") == "table_cell":
        return max(APPROX_LOCAL_SCAN_WINDOW, 24)
    if _is_short_partial_fragment(fragment):
        return max(APPROX_LOCAL_SCAN_WINDOW, 28)
    return APPROX_LOCAL_SCAN_WINDOW


def _presence_score(source_text: str, candidate_text: str) -> float:
    source = str(source_text or "")
    candidate = str(candidate_text or "")
    if not source or not candidate:
        return 0.0

    score = semantic_similarity_norm(source, candidate)
    if source in candidate:
        overrun = max(0, len(candidate) - len(source))
        penalty = min(0.22, (overrun / max(1, len(source))) * 0.04)
        score = max(score, max(0.72, 1.0 - penalty))
    elif candidate in source:
        overrun = max(0, len(source) - len(candidate))
        penalty = min(0.22, (overrun / max(1, len(candidate))) * 0.04)
        score = max(score, max(0.72, 1.0 - penalty))

    return round(float(score), 6)


def _default_no_candidate_reason(fragment: InlineStyleFragment) -> str:
    if str(fragment.get("container_type") or "paragraph") == "table_cell":
        return "no_same_table_candidate"
    if _is_short_title_fragment(fragment):
        return "no_title_candidate_container"
    if str(fragment.get("source_span_kind") or "partial_span") == "partial_span":
        return "no_partial_candidate_container"
    return "no_candidate_container"


def build_inline_style_extraction_logs(
    inline_style_fragments: Iterable[Dict[str, Any]] | None,
    *,
    step_label: str = "样式提取",
    max_text_chars: int = LOG_TEXT_LIMIT,
) -> list[str]:
    fragments = [
        _normalize_fragment_font_color(InlineStyleFragment(**dict(item)))
        for item in list(inline_style_fragments or [])
    ]
    logs: list[str] = []
    total = len(fragments)

    for index, fragment in enumerate(fragments, start=1):
        logs.append(
            " | ".join(
                [
                    f"{step_label}[{index}/{total}]",
                    f"样式={_format_style_labels(fragment)}",
                    f"源文本=\"{_truncate_log_text(fragment.get('source_text'), max_chars=max_text_chars)}\"",
                    f"容器={_format_container_hint(str(fragment.get('container_type') or 'paragraph'), fragment.get('container_locator'))}",
                    f"范围={_format_source_span_kind(fragment)}",
                ]
            )
        )

    return logs


def _emit_runtime_log(
    log_parts: list[str],
    message: str,
    progress_logger: Optional[Callable[[str], Any]] = None,
) -> None:
    log_parts.append(message)
    if callable(progress_logger):
        try:
            progress_logger(message)
        except Exception:
            pass


def _emit_diagnostic_log(
    message: str,
    diagnostic_logger: Optional[Callable[[str], Any]] = None,
) -> None:
    if callable(diagnostic_logger):
        try:
            diagnostic_logger(message)
        except Exception:
            pass


def _clean_character_text(raw_text: Any) -> str:
    text = str(raw_text or "")
    if text in CONTROL_CHAR_TEXT:
        return CONTROL_CHAR_TEXT[text]
    return text.replace("\u00a0", " ")


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _read_font_property(char_range, attr_name: str, default: Any = None) -> Any:
    try:
        font = getattr(char_range, "Font", None)
        if font is None:
            return default
        value = getattr(font, attr_name)
        return default if value is None else value
    except Exception:
        return default


def _read_direct_font_property(font, attr_name: str, default: Any = None) -> Any:
    try:
        if font is None:
            return default
        value = getattr(font, attr_name)
        return default if value is None else value
    except Exception:
        return default


def _normalize_font_color(value: Any) -> Optional[int]:
    color = _safe_int(value, default=BLACK_COLOR)
    if color in {BLACK_COLOR, AUTOMATIC_COLOR, WINDOWS_AUTO_COLOR}:
        return None
    return color


def _normalize_highlight_color(value: Any) -> Optional[int]:
    color = _safe_int(value, default=NO_HIGHLIGHT)
    if color == NO_HIGHLIGHT:
        return None
    return color


def _build_font_signature(font) -> CharacterStyleSignature:
    underline_style = _safe_int(_read_direct_font_property(font, "Underline", 0), default=0)
    signature: CharacterStyleSignature = {
        "style_flags": {
            "strikethrough": bool(_read_direct_font_property(font, "StrikeThrough", False)),
            "underline": bool(underline_style),
            "bold": bool(_read_direct_font_property(font, "Bold", False)),
            "italic": bool(_read_direct_font_property(font, "Italic", False)),
        },
        "font_color": _normalize_font_color(_read_direct_font_property(font, "Color", BLACK_COLOR)),
        "highlight_color": _normalize_highlight_color(
            _read_direct_font_property(font, "HighlightColorIndex", NO_HIGHLIGHT)
        ),
        "font_name": str(_read_direct_font_property(font, "Name", "") or "").strip() or None,
        "font_size": None,
        "underline_style": underline_style or None,
    }

    font_size = _safe_float(_read_direct_font_property(font, "Size", 0))
    if font_size > 0:
        signature["font_size"] = font_size
    return signature


def _build_character_signature(char_range) -> CharacterStyleSignature:
    return _build_font_signature(getattr(char_range, "Font", None))


def _signature_has_supported_style(signature: CharacterStyleSignature) -> bool:
    flags = signature.get("style_flags") or {}
    return bool(
        flags.get("strikethrough")
        or flags.get("underline")
        or flags.get("bold")
        or flags.get("italic")
        or signature.get("font_color") is not None
        or signature.get("highlight_color") is not None
    )


def _signature_key(signature: CharacterStyleSignature) -> tuple[Any, ...]:
    flags = signature.get("style_flags") or {}
    return (
        bool(flags.get("strikethrough")),
        bool(flags.get("underline")),
        bool(flags.get("bold")),
        bool(flags.get("italic")),
        signature.get("font_color"),
        signature.get("highlight_color"),
        signature.get("font_name"),
        signature.get("font_size"),
        signature.get("underline_style"),
    )


def _build_visible_chars(range_obj) -> tuple[list[_VisibleChar], str]:
    visible_chars: list[_VisibleChar] = []
    visible_text_parts: list[str] = []
    visible_index = 0

    try:
        characters = range_obj.Characters
        count = _safe_int(getattr(characters, "Count", 0))
    except Exception:
        count = 0

    for index in range(1, count + 1):
        try:
            char_range = characters.Item(index)
        except Exception:
            continue

        text = _clean_character_text(getattr(char_range, "Text", ""))
        if not text:
            continue

        start = _safe_int(getattr(char_range, "Start", 0))
        end = _safe_int(getattr(char_range, "End", start))
        signature = _build_character_signature(char_range)

        visible_chars.append(
            _VisibleChar(
                text=text,
                start=start,
                end=end,
                visible_start=visible_index,
                visible_end=visible_index + len(text),
                signature=signature,
            )
        )
        visible_text_parts.append(text)
        visible_index += len(text)

    return visible_chars, "".join(visible_text_parts)


def _build_logical_lines(
    visible_chars: Sequence[_VisibleChar],
    *,
    bound_start: int,
    bound_end: int,
) -> list[_LogicalLine]:
    total_length = max(1, int(bound_end) - int(bound_start))
    logical_lines: list[_LogicalLine] = []
    line_text_parts: list[str] = []
    line_visible_start: Optional[int] = None
    line_visible_end: Optional[int] = None
    line_actual_start: Optional[int] = None
    line_actual_end: Optional[int] = None

    def flush_line() -> None:
        nonlocal line_text_parts, line_visible_start, line_visible_end, line_actual_start, line_actual_end
        if (
            line_visible_start is None
            or line_visible_end is None
            or line_actual_start is None
            or line_actual_end is None
            or not line_text_parts
        ):
            line_text_parts = []
            line_visible_start = None
            line_visible_end = None
            line_actual_start = None
            line_actual_end = None
            return

        line_text = "".join(line_text_parts)
        normalized_text, normalized_index_to_visible = _build_normalized_text_with_visible_map(
            line_text
        )
        if normalized_text:
            midpoint = (float(line_actual_start) + float(line_actual_end)) / 2.0
            position_ratio = max(
                0.0,
                min(1.0, (midpoint - float(bound_start)) / float(total_length)),
            )
            logical_lines.append(
                _LogicalLine(
                    text=line_text,
                    normalized_text=normalized_text,
                    normalized_index_to_visible=normalized_index_to_visible,
                    visible_start=int(line_visible_start),
                    visible_end=int(line_visible_end),
                    actual_start=int(line_actual_start),
                    actual_end=int(line_actual_end),
                    position_ratio=position_ratio,
                )
            )

        line_text_parts = []
        line_visible_start = None
        line_visible_end = None
        line_actual_start = None
        line_actual_end = None

    for char in visible_chars:
        if char.text == "\n":
            flush_line()
            continue

        if line_visible_start is None:
            line_visible_start = int(char.visible_start)
            line_actual_start = int(char.start)

        line_text_parts.append(char.text)
        line_visible_end = int(char.visible_end)
        line_actual_end = int(char.end)

    flush_line()
    return logical_lines


def _build_normalized_text_with_visible_map(text: str) -> tuple[str, list[int]]:
    cleaned = (
        str(text or "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\v", "\n")
        .replace("\u00a0", " ")
    )
    if not cleaned:
        return "", []

    normalized_chars: list[str] = []
    visible_indices: list[int] = []
    index = 0
    at_line_start = True

    while index < len(cleaned):
        remaining = cleaned[index:]
        if at_line_start:
            stripped = strip_number_prefix(remaining)
            prefix_len = len(remaining) - len(stripped)
            if prefix_len > 0:
                index += prefix_len
                continue

        char = cleaned[index]
        if char == "\n":
            at_line_start = True
            index += 1
            continue

        at_line_start = False
        normalized_char = normalize_semantic_text(char)
        if normalized_char:
            normalized_chars.append(normalized_char)
            visible_indices.append(index)
        index += 1

    return "".join(normalized_chars), visible_indices


def _build_container_candidate(
    *,
    container_type: ContainerType,
    container_locator: InlineStyleContainerLocator,
    range_obj,
    bound_start: int,
    bound_end: int,
) -> Optional[_ContainerCandidate]:
    visible_chars, visible_text = _build_visible_chars(range_obj)
    if not visible_chars:
        return None

    normalized_text, normalized_index_to_visible = _build_normalized_text_with_visible_map(
        visible_text
    )
    if not normalized_text:
        return None

    total_length = max(1, int(bound_end) - int(bound_start))
    position_ratio = max(
        0.0,
        min(1.0, (_safe_int(getattr(range_obj, "Start", bound_start)) - int(bound_start)) / total_length),
    )
    logical_lines = _build_logical_lines(
        visible_chars,
        bound_start=bound_start,
        bound_end=bound_end,
    )

    return _ContainerCandidate(
        container_type=container_type,
        container_locator=container_locator,
        visible_chars=visible_chars,
        visible_text=visible_text,
        normalized_text=normalized_text,
        normalized_index_to_visible=normalized_index_to_visible,
        logical_lines=logical_lines,
        position_ratio=position_ratio,
        range_start=_safe_int(getattr(range_obj, "Start", 0)),
        range_end=_safe_int(getattr(range_obj, "End", 0)),
    )


def build_inline_style_fragments_from_text_runs(
    *,
    container_type: ContainerType,
    container_locator: InlineStyleContainerLocator,
    container_text: str,
    position_ratio: float,
    runs: Sequence[StyledVisibleChar],
) -> list[InlineStyleFragment]:
    """纯文本/字符切片版 fragment 构建器，便于单测覆盖合并规则。"""
    if not runs:
        return []

    fragments: list[InlineStyleFragment] = []
    container_visible_text = str(container_text or "")
    normalized_container_text = normalize_semantic_text(container_visible_text)
    if not normalized_container_text:
        return []

    current_signature: Optional[CharacterStyleSignature] = None
    current_text_parts: list[str] = []
    current_start: Optional[int] = None
    current_end: Optional[int] = None

    def flush_current() -> None:
        nonlocal current_signature, current_text_parts, current_start, current_end
        if (
            current_signature is None
            or current_start is None
            or current_end is None
            or not current_text_parts
        ):
            current_signature = None
            current_text_parts = []
            current_start = None
            current_end = None
            return

        source_text = "".join(current_text_parts).strip()
        normalized_text = normalize_semantic_text(source_text)
        is_number_prefix = False
        if source_text and not normalized_text:
            is_number_prefix = _is_leading_number_prefix_span(
                container_text=container_visible_text,
                visible_start=current_start,
                visible_end=current_end,
            )
            if is_number_prefix:
                normalized_text = normalized_container_text

        if not source_text or not normalized_text:
            current_signature = None
            current_text_parts = []
            current_start = None
            current_end = None
            return

        context_before = container_visible_text[max(0, current_start - CONTEXT_CHARS) : current_start]
        context_after = container_visible_text[current_end : current_end + CONTEXT_CHARS]
        local_position_ratio = max(
            0.0,
            min(
                1.0,
                ((current_start + current_end) / 2.0) / max(1.0, float(len(container_visible_text))),
            ),
        )
        if is_number_prefix:
            source_span_kind: SourceSpanKind = "number_prefix"
        else:
            source_span_kind = (
                "full_container"
                if normalized_text == normalized_container_text
                else "partial_span"
            )

        fragment = InlineStyleFragment(
            container_type=container_type,
            container_locator=dict(container_locator),
            source_text=source_text,
            normalized_text=normalized_text,
            container_text=container_visible_text,
            normalized_container_text=normalized_container_text,
            context_before=context_before,
            context_after=context_after,
            position_ratio=float(position_ratio),
            local_position_ratio=float(local_position_ratio),
            style_flags=dict(current_signature.get("style_flags") or {}),
            font_color=current_signature.get("font_color"),
            highlight_color=current_signature.get("highlight_color"),
            font_name=current_signature.get("font_name"),
            font_size=current_signature.get("font_size"),
            underline_style=current_signature.get("underline_style"),
            source_span_kind=source_span_kind,
        )
        if is_number_prefix:
            fragment["number_prefix_text"] = source_text
        fragments.append(fragment)

        current_signature = None
        current_text_parts = []
        current_start = None
        current_end = None

    for run in runs:
        text = str(run.get("text") or "")
        if text == "\n":
            flush_current()
            continue

        signature = run.get("signature") or {}
        if not _signature_has_supported_style(signature):
            flush_current()
            continue

        run_start = _safe_int(run.get("start"), 0)
        run_end = _safe_int(run.get("end"), run_start)

        if current_signature is None:
            current_signature = dict(signature)
            current_text_parts = [text]
            current_start = run_start
            current_end = run_end
            continue

        if _signature_key(current_signature) == _signature_key(signature):
            current_text_parts.append(text)
            current_end = run_end
            continue

        flush_current()
        current_signature = dict(signature)
        current_text_parts = [text]
        current_start = run_start
        current_end = run_end

    flush_current()
    return fragments


def _build_fragments_from_container(
    *,
    container_type: ContainerType,
    container_locator: InlineStyleContainerLocator,
    range_obj,
    bound_start: int,
    bound_end: int,
) -> list[InlineStyleFragment]:
    candidate = _build_container_candidate(
        container_type=container_type,
        container_locator=container_locator,
        range_obj=range_obj,
        bound_start=bound_start,
        bound_end=bound_end,
    )
    if candidate is None:
        return []

    runs: list[StyledVisibleChar] = []
    for char in candidate.visible_chars:
        runs.append(
            StyledVisibleChar(
                text=char.text,
                start=char.visible_start,
                end=char.visible_end,
                signature=char.signature,
            )
        )

    return build_inline_style_fragments_from_text_runs(
        container_type=container_type,
        container_locator=container_locator,
        container_text=candidate.visible_text,
        position_ratio=candidate.position_ratio,
        runs=runs,
    )


def _collection_item(collection, index: int):
    if collection is None:
        return None
    try:
        return collection(index)
    except Exception:
        try:
            return collection.Item(index)
        except Exception:
            return None


def _read_list_level_font(list_format) -> Any:
    try:
        level_number = _safe_int(getattr(list_format, "ListLevelNumber", 1), default=1)
    except Exception:
        level_number = 1
    if level_number <= 0:
        level_number = 1

    try:
        list_template = getattr(list_format, "ListTemplate", None)
        list_levels = getattr(list_template, "ListLevels", None)
        list_level = _collection_item(list_levels, level_number)
        return getattr(list_level, "Font", None) if list_level is not None else None
    except Exception:
        return None


def _read_list_string(list_format) -> str:
    try:
        return str(getattr(list_format, "ListString", "") or "").strip()
    except Exception:
        return ""


def _range_has_list_label(range_obj) -> bool:
    try:
        list_format = getattr(range_obj, "ListFormat", None)
    except Exception:
        return False
    if list_format is None:
        return False

    try:
        if _safe_int(getattr(list_format, "ListType", 0), default=0) <= 0:
            return False
    except Exception:
        pass

    return bool(_read_list_string(list_format))


def _build_number_prefix_fragment_from_paragraph_list(
    *,
    container_locator: InlineStyleContainerLocator,
    paragraph_range,
    candidate: _ContainerCandidate,
) -> Optional[InlineStyleFragment]:
    try:
        list_format = getattr(paragraph_range, "ListFormat", None)
    except Exception:
        return None
    if list_format is None:
        return None

    list_string = ""
    try:
        if _safe_int(getattr(list_format, "ListType", 0), default=0) <= 0:
            return None
    except Exception:
        pass

    list_string = _read_list_string(list_format)
    if not list_string:
        return None

    signature = _build_font_signature(_read_list_level_font(list_format))
    if not _signature_has_supported_style(signature):
        return None

    normalized_container_text = candidate.normalized_text
    if not normalized_container_text:
        return None

    return InlineStyleFragment(
        container_type="paragraph",
        container_locator=dict(container_locator),
        source_text=list_string,
        normalized_text=normalized_container_text,
        container_text=f"{list_string} {candidate.visible_text}".strip(),
        normalized_container_text=normalized_container_text,
        context_before="",
        context_after=candidate.visible_text[:CONTEXT_CHARS],
        position_ratio=float(candidate.position_ratio),
        local_position_ratio=0.0,
        style_flags=dict(signature.get("style_flags") or {}),
        font_color=signature.get("font_color"),
        highlight_color=signature.get("highlight_color"),
        font_name=signature.get("font_name"),
        font_size=signature.get("font_size"),
        underline_style=signature.get("underline_style"),
        source_span_kind="number_prefix",
        number_prefix_text=list_string,
    )


def _collect_paragraph_fragments(doc, *, bound_start: int, bound_end: int) -> list[InlineStyleFragment]:
    fragments: list[InlineStyleFragment] = []
    paragraph_index = 0
    content_range = doc.Range(int(bound_start), int(bound_end))
    try:
        paragraphs = content_range.Paragraphs
        count = _safe_int(getattr(paragraphs, "Count", 0))
    except Exception:
        count = 0

    for index in range(1, count + 1):
        try:
            paragraph = paragraphs(index)
            paragraph_range = paragraph.Range
        except Exception:
            continue

        try:
            if bool(paragraph_range.Information(wdWithInTable)):
                continue
        except Exception:
            pass

        paragraph_index += 1
        container_locator: InlineStyleContainerLocator = {"paragraph_index": paragraph_index}
        candidate = _build_container_candidate(
            container_type="paragraph",
            container_locator=container_locator,
            range_obj=paragraph_range,
            bound_start=bound_start,
            bound_end=bound_end,
        )
        if candidate is None:
            continue

        list_fragment = _build_number_prefix_fragment_from_paragraph_list(
            container_locator=container_locator,
            paragraph_range=paragraph_range,
            candidate=candidate,
        )
        if list_fragment is not None:
            fragments.append(list_fragment)

        runs: list[StyledVisibleChar] = []
        for char in candidate.visible_chars:
            runs.append(
                StyledVisibleChar(
                    text=char.text,
                    start=char.visible_start,
                    end=char.visible_end,
                    signature=char.signature,
                )
            )
        fragments.extend(
            build_inline_style_fragments_from_text_runs(
                container_type="paragraph",
                container_locator=container_locator,
                container_text=candidate.visible_text,
                position_ratio=candidate.position_ratio,
                runs=runs,
            )
        )

    return fragments


def _collect_table_cell_fragments(doc, *, bound_start: int, bound_end: int) -> list[InlineStyleFragment]:
    fragments: list[InlineStyleFragment] = []
    content_range = doc.Range(int(bound_start), int(bound_end))

    try:
        tables = content_range.Tables
        table_count = _safe_int(getattr(tables, "Count", 0))
    except Exception:
        table_count = 0

    for table_index in range(1, table_count + 1):
        try:
            table = tables(table_index)
            row_count = _safe_int(getattr(table.Rows, "Count", 0))
            col_count = _safe_int(getattr(table.Columns, "Count", 0))
        except Exception:
            continue

        for row in range(1, row_count + 1):
            for col in range(1, col_count + 1):
                try:
                    cell = table.Cell(row, col)
                    cell_range = cell.Range
                except Exception:
                    continue

                fragments.extend(
                    _build_fragments_from_container(
                        container_type="table_cell",
                        container_locator={
                            "table_index": table_index,
                            "row": row,
                            "col": col,
                        },
                        range_obj=cell_range,
                        bound_start=bound_start,
                        bound_end=bound_end,
                    )
                )

    return fragments


def extract_inline_style_fragments(doc, *, bound_start: int, bound_end: int) -> list[InlineStyleFragment]:
    """从锚点区正文段落与表格单元格里提取可回填的行内样式片段。"""
    if int(bound_end) <= int(bound_start):
        return []

    fragments: list[InlineStyleFragment] = []
    fragments.extend(_collect_paragraph_fragments(doc, bound_start=bound_start, bound_end=bound_end))
    fragments.extend(_collect_table_cell_fragments(doc, bound_start=bound_start, bound_end=bound_end))
    return fragments


def _build_target_containers(doc, *, bound_start: int, bound_end: int) -> list[_ContainerCandidate]:
    candidates: list[_ContainerCandidate] = []
    content_range = doc.Range(int(bound_start), int(bound_end))

    try:
        paragraphs = content_range.Paragraphs
        paragraph_count = _safe_int(getattr(paragraphs, "Count", 0))
    except Exception:
        paragraph_count = 0

    paragraph_index = 0
    for index in range(1, paragraph_count + 1):
        try:
            paragraph_range = paragraphs(index).Range
        except Exception:
            continue
        try:
            if bool(paragraph_range.Information(wdWithInTable)):
                continue
        except Exception:
            pass

        paragraph_index += 1
        candidate = _build_container_candidate(
            container_type="paragraph",
            container_locator={"paragraph_index": paragraph_index},
            range_obj=paragraph_range,
            bound_start=bound_start,
            bound_end=bound_end,
        )
        if candidate is not None:
            candidates.append(candidate)

    try:
        tables = content_range.Tables
        table_count = _safe_int(getattr(tables, "Count", 0))
    except Exception:
        table_count = 0

    for table_index in range(1, table_count + 1):
        try:
            table = tables(table_index)
            row_count = _safe_int(getattr(table.Rows, "Count", 0))
            col_count = _safe_int(getattr(table.Columns, "Count", 0))
        except Exception:
            continue

        for row in range(1, row_count + 1):
            for col in range(1, col_count + 1):
                try:
                    cell_range = table.Cell(row, col).Range
                except Exception:
                    continue

                candidate = _build_container_candidate(
                    container_type="table_cell",
                    container_locator={
                        "table_index": table_index,
                        "row": row,
                        "col": col,
                    },
                    range_obj=cell_range,
                    bound_start=bound_start,
                    bound_end=bound_end,
                )
                if candidate is not None:
                    candidates.append(candidate)

    return candidates


def _container_locator_equals(
    left: InlineStyleContainerLocator,
    right: InlineStyleContainerLocator,
) -> bool:
    return (
        left.get("paragraph_index") == right.get("paragraph_index")
        and left.get("table_index") == right.get("table_index")
        and left.get("row") == right.get("row")
        and left.get("col") == right.get("col")
    )


def _position_score(source_ratio: float, target_ratio: float) -> float:
    distance = abs(float(source_ratio) - float(target_ratio))
    return max(0.0, 1.0 - min(1.0, distance / 0.35))


def _local_position_score(fragment: InlineStyleFragment, candidate: _ContainerCandidate, visible_start: int, visible_end: int) -> float:
    expected_ratio = float(fragment.get("local_position_ratio") or 0.0)
    actual_ratio = max(
        0.0,
        min(
            1.0,
            ((float(visible_start) + float(visible_end)) / 2.0)
            / max(1.0, float(len(candidate.visible_text))),
        ),
    )
    return max(0.0, 1.0 - min(1.0, abs(expected_ratio - actual_ratio) / 0.40))


def _table_structure_score(
    source_locator: InlineStyleContainerLocator,
    candidate_locator: InlineStyleContainerLocator,
) -> float:
    source_row = _safe_int(source_locator.get("row"), 0)
    source_col = _safe_int(source_locator.get("col"), 0)
    candidate_row = _safe_int(candidate_locator.get("row"), 0)
    candidate_col = _safe_int(candidate_locator.get("col"), 0)

    distance = abs(source_row - candidate_row) * 0.75 + abs(source_col - candidate_col)
    return max(0.0, 1.0 - min(1.0, distance / 4.0))


def _append_issue(
    result: InlineStyleWritebackResult,
    *,
    index: int,
    reason: str,
    fragment: InlineStyleFragment,
    score: float = 0.0,
    error: str = "",
) -> None:
    issue: InlineStyleWritebackIssue = {
        "index": int(index),
        "reason": str(reason),
        "source_text": str(fragment.get("source_text") or "")[:120],
        "container_type": str(fragment.get("container_type") or "paragraph"),
        "container_locator": dict(fragment.get("container_locator") or {}),
        "score": round(float(score), 4),
    }
    if error:
        issue["error"] = str(error)
    result["issues"].append(issue)
    result["skipped_by_reason"][reason] = result["skipped_by_reason"].get(reason, 0) + 1


def _context_score(
    *,
    context_before: str,
    context_after: str,
    candidate_text: str,
    visible_start: int,
    visible_end: int,
) -> float:
    before_slice = candidate_text[max(0, visible_start - CONTEXT_CHARS) : visible_start]
    after_slice = candidate_text[visible_end : visible_end + CONTEXT_CHARS]

    before_score = 1.0 if not context_before else semantic_similarity(context_before, before_slice)
    after_score = 1.0 if not context_after else semantic_similarity(context_after, after_slice)
    return (before_score + after_score) / 2.0


def _resolve_actual_span(candidate: _ContainerCandidate, visible_start: int, visible_end: int) -> Optional[tuple[int, int]]:
    start_char = None
    end_char = None
    for char in candidate.visible_chars:
        if start_char is None and char.visible_start <= visible_start < char.visible_end:
            start_char = char
        if char.visible_start < visible_end <= char.visible_end:
            end_char = char
            break
        if char.visible_start < visible_end:
            end_char = char

    if start_char is None or end_char is None:
        return None
    return int(start_char.start), int(end_char.end)


def _locate_exact_occurrences_in_text(
    normalized_candidate_text: str,
    normalized_text: str,
) -> list[tuple[int, int]]:
    occurrences: list[tuple[int, int]] = []
    if not normalized_text:
        return occurrences

    start = 0
    while start < len(normalized_candidate_text):
        hit = normalized_candidate_text.find(normalized_text, start)
        if hit < 0:
            break
        occurrences.append((hit, hit + len(normalized_text)))
        start = hit + 1
    return occurrences


def _locate_exact_occurrences(candidate: _ContainerCandidate, normalized_text: str) -> list[tuple[int, int]]:
    return _locate_exact_occurrences_in_text(candidate.normalized_text, normalized_text)


def _build_local_match_from_norm_span(
    candidate: _ContainerCandidate,
    *,
    fragment: InlineStyleFragment,
    norm_start: int,
    norm_end: int,
    base_score: float,
) -> Optional[_LocalMatch]:
    if norm_end <= norm_start:
        return None

    try:
        visible_start = candidate.normalized_index_to_visible[norm_start]
        visible_end = candidate.normalized_index_to_visible[norm_end - 1] + 1
    except Exception:
        return None

    actual_span = _resolve_actual_span(candidate, visible_start, visible_end)
    if actual_span is None:
        return None

    context_score = _context_score(
        context_before=str(fragment.get("context_before") or ""),
        context_after=str(fragment.get("context_after") or ""),
        candidate_text=candidate.visible_text,
        visible_start=visible_start,
        visible_end=visible_end,
    )
    local_position_score = _local_position_score(
        fragment,
        candidate,
        visible_start,
        visible_end,
    )
    final_score = (
        0.78 * float(base_score)
        + 0.12 * context_score
        + 0.10 * local_position_score
    )
    return _LocalMatch(
        visible_start=visible_start,
        visible_end=visible_end,
        actual_start=actual_span[0],
        actual_end=actual_span[1],
        score=final_score,
        context_score=context_score,
        local_position_score=local_position_score,
        text_score=float(base_score),
        is_exact=float(base_score) >= 0.999,
    )


def _build_local_match_from_line_norm_span(
    candidate: _ContainerCandidate,
    *,
    line: _LogicalLine,
    fragment: InlineStyleFragment,
    norm_start: int,
    norm_end: int,
    base_score: float,
) -> Optional[_LocalMatch]:
    if norm_end <= norm_start:
        return None

    try:
        visible_start = line.visible_start + line.normalized_index_to_visible[norm_start]
        visible_end = (
            line.visible_start
            + line.normalized_index_to_visible[norm_end - 1]
            + 1
        )
    except Exception:
        return None

    if _is_short_title_fragment(fragment) and norm_start == 0:
        source_text = str(fragment.get("source_text") or "").strip()
        if source_text and line.text.startswith(source_text):
            visible_start = line.visible_start
            visible_end = min(line.visible_start + len(source_text), line.visible_end)

    actual_span = _resolve_actual_span(candidate, visible_start, visible_end)
    if actual_span is None:
        return None

    context_score = _context_score(
        context_before=str(fragment.get("context_before") or ""),
        context_after=str(fragment.get("context_after") or ""),
        candidate_text=candidate.visible_text,
        visible_start=visible_start,
        visible_end=visible_end,
    )
    line_position_score = _position_score(
        float(fragment.get("position_ratio") or 0.0),
        line.position_ratio,
    )
    final_score = (
        0.80 * float(base_score)
        + 0.15 * context_score
        + 0.05 * line_position_score
    )
    return _LocalMatch(
        visible_start=visible_start,
        visible_end=visible_end,
        actual_start=actual_span[0],
        actual_end=actual_span[1],
        score=final_score,
        context_score=context_score,
        local_position_score=line_position_score,
        text_score=float(base_score),
        is_exact=float(base_score) >= 0.999,
    )


def _match_short_title_line(
    candidate: _ContainerCandidate,
    fragment: InlineStyleFragment,
) -> tuple[float, float, Optional[_LocalMatch]]:
    normalized_title = str(fragment.get("normalized_container_text") or "")
    if not normalized_title:
        return 0.0, 0.0, None

    best_score = 0.0
    best_position_score = 0.0
    best_match: Optional[_LocalMatch] = None

    for line in candidate.logical_lines:
        hits = _locate_exact_occurrences_in_text(line.normalized_text, normalized_title)
        if not hits:
            continue

        line_position_score = _position_score(
            float(fragment.get("position_ratio") or 0.0),
            line.position_ratio,
        )
        for norm_start, norm_end in hits:
            match = _build_local_match_from_line_norm_span(
                candidate,
                line=line,
                fragment=fragment,
                norm_start=norm_start,
                norm_end=norm_end,
                base_score=1.0,
            )
            if match is None:
                continue

            combined_score = round(0.68 * match.score + 0.32 * line_position_score, 6)
            if (
                combined_score > best_score
                or (
                    abs(combined_score - best_score) < 1e-6
                    and line_position_score > best_position_score
                )
            ):
                best_score = combined_score
                best_position_score = line_position_score
                best_match = match

    return best_score, best_position_score, best_match


def _locate_number_prefix_span(
    candidate: _ContainerCandidate,
    fragment: InlineStyleFragment,
    *,
    doc=None,
) -> tuple[Optional[_LocalMatch], Optional[str]]:
    normalized_container_text = str(fragment.get("normalized_container_text") or "")

    def build_list_label_match() -> tuple[Optional[_LocalMatch], Optional[str]]:
        if doc is None:
            return None, "no_number_prefix_target"
        try:
            target_range = doc.Range(int(candidate.range_start), int(candidate.range_end))
        except Exception:
            return None, "no_number_prefix_target"
        if not _range_has_list_label(target_range):
            return None, "no_number_prefix_target"

        text_score = semantic_similarity_norm(
            normalized_container_text,
            candidate.normalized_text,
        )
        context_score = semantic_similarity(
            str(fragment.get("context_after") or ""),
            candidate.visible_text,
        )
        position_score = _position_score(
            float(fragment.get("position_ratio") or 0.0),
            candidate.position_ratio,
        )
        final_score = 0.64 * text_score + 0.18 * context_score + 0.18 * position_score
        return (
            _LocalMatch(
                visible_start=0,
                visible_end=0,
                actual_start=int(candidate.range_start),
                actual_end=int(candidate.range_start),
                score=final_score,
                context_score=context_score,
                local_position_score=position_score,
            ),
            None,
        )

    if not candidate.logical_lines:
        return build_list_label_match()

    matches: list[tuple[float, _LocalMatch]] = []

    for line in candidate.logical_lines:
        prefix_len = _leading_number_prefix_len(line.text)
        if prefix_len <= 0:
            continue

        prefix_text = line.text[:prefix_len]
        prefix_start_offset = len(prefix_text) - len(prefix_text.lstrip())
        prefix_end_offset = len(prefix_text.rstrip())
        if prefix_end_offset <= prefix_start_offset:
            continue

        visible_start = line.visible_start + prefix_start_offset
        visible_end = line.visible_start + prefix_end_offset
        actual_span = _resolve_actual_span(candidate, visible_start, visible_end)
        if actual_span is None:
            continue

        line_text_score = semantic_similarity_norm(
            normalized_container_text,
            line.normalized_text,
        )
        context_score = _context_score(
            context_before=str(fragment.get("context_before") or ""),
            context_after=str(fragment.get("context_after") or ""),
            candidate_text=candidate.visible_text,
            visible_start=visible_start,
            visible_end=visible_end,
        )
        line_position_score = _position_score(
            float(fragment.get("position_ratio") or 0.0),
            line.position_ratio,
        )
        local_position_score = _local_position_score(
            fragment,
            candidate,
            visible_start,
            visible_end,
        )
        final_score = (
            0.62 * line_text_score
            + 0.18 * context_score
            + 0.12 * line_position_score
            + 0.08 * local_position_score
        )
        matches.append(
            (
                round(final_score, 6),
                _LocalMatch(
                    visible_start=visible_start,
                    visible_end=visible_end,
                    actual_start=actual_span[0],
                    actual_end=actual_span[1],
                    score=final_score,
                    context_score=context_score,
                    local_position_score=max(line_position_score, local_position_score),
                ),
            )
        )

    if not matches:
        return build_list_label_match()

    matches.sort(
        key=lambda item: (
            item[0],
            item[1].context_score,
            item[1].local_position_score,
        ),
        reverse=True,
    )
    if (
        len(matches) > 1
        and abs(matches[0][0] - matches[1][0]) < 0.02
        and abs(matches[0][1].local_position_score - matches[1][1].local_position_score) < 0.05
    ):
        return None, "multiple_local_candidates"

    return matches[0][1], None


def _short_partial_match_gate_reason(
    fragment: InlineStyleFragment,
    probe: _CandidateProbe,
    local_match: Optional[_LocalMatch],
) -> str:
    if not _is_short_partial_fragment(fragment) or local_match is None:
        return ""

    candidate = probe.candidate
    if _is_target_line_leading_number_prefix_match(candidate, local_match):
        return "short_fragment_prefix_conflict"

    text_len = _normalized_length(fragment.get("normalized_text"))
    is_exact = bool(local_match.is_exact)
    is_high_visible = _is_high_visible_short_style(fragment)
    context_passed = _short_partial_context_gate_passed(fragment, candidate, local_match)

    if candidate.container_type == "table_cell":
        same_cell = _container_locator_equals(
            candidate.container_locator,
            dict(fragment.get("container_locator") or {}),
        )
        if is_exact and same_cell:
            return ""

        min_local_score = (
            TABLE_SHORT_PARTIAL_HIGH_VISIBLE_APPROX_MIN_SCORE
            if is_high_visible
            else TABLE_SHORT_PARTIAL_APPROX_MIN_SCORE
        )
        if not is_exact and float(local_match.text_score) < min_local_score:
            return "short_fragment_unanchored"
        if float(probe.structure_score) < TABLE_SHORT_PARTIAL_STRUCTURE_MIN_SCORE:
            return "short_fragment_semantic_mismatch"
        if (
            not context_passed
            and float(probe.container_score) < TABLE_SHORT_PARTIAL_CONTAINER_MIN_SCORE
        ):
            return "short_fragment_semantic_mismatch"
        return ""

    if not is_exact and text_len <= SHORT_PARTIAL_EXACT_ONLY_MAX_LEN:
        return "short_fragment_unanchored"

    if is_exact:
        if (
            text_len <= SHORT_PARTIAL_EXACT_ONLY_MAX_LEN
            and is_high_visible
            and not context_passed
            and float(probe.container_score) < SHORT_PARTIAL_EXACT_CONTAINER_MIN_SCORE
        ):
            return "short_fragment_semantic_mismatch"
        return ""

    min_local_score = (
        SHORT_PARTIAL_HIGH_VISIBLE_APPROX_MIN_SCORE
        if is_high_visible
        else SHORT_PARTIAL_APPROX_MIN_SCORE
    )
    if float(local_match.text_score) < min_local_score:
        return "short_fragment_unanchored"
    if not context_passed and float(probe.container_score) < SHORT_PARTIAL_CONTAINER_MIN_SCORE:
        return "short_fragment_semantic_mismatch"
    return ""


def _best_short_partial_line_hint(
    candidate: _ContainerCandidate,
    fragment: InlineStyleFragment,
) -> tuple[float, float]:
    normalized_text = str(fragment.get("normalized_text") or "")
    if not normalized_text:
        return 0.0, 0.0

    best_score = 0.0
    best_position_score = 0.0
    min_text_score = 0.54
    exact_only = _normalized_length(normalized_text) <= SHORT_PARTIAL_EXACT_ONLY_MAX_LEN

    for line in candidate.logical_lines:
        if exact_only and not _locate_exact_occurrences_in_text(line.normalized_text, normalized_text):
            continue
        text_score = _presence_score(normalized_text, line.normalized_text)
        if text_score < min_text_score:
            continue

        line_position_score = _position_score(
            float(fragment.get("position_ratio") or 0.0),
            line.position_ratio,
        )
        combined_score = round(0.72 * text_score + 0.28 * line_position_score, 6)
        if (
            combined_score > best_score
            or (
                abs(combined_score - best_score) < 1e-6
                and line_position_score > best_position_score
            )
        ):
            best_score = combined_score
            best_position_score = line_position_score

    return best_score, best_position_score


def _locate_local_span(
    candidate: _ContainerCandidate,
    fragment: InlineStyleFragment,
) -> tuple[Optional[_LocalMatch], Optional[str]]:
    normalized_text = str(fragment.get("normalized_text") or "")
    if not normalized_text:
        return None, "empty_fragment"

    if _is_short_partial_fragment(fragment) and candidate.logical_lines:
        min_text_score = 0.58
        exact_only = _normalized_length(normalized_text) <= SHORT_PARTIAL_EXACT_ONLY_MAX_LEN
        line_matches: list[tuple[float, _LocalMatch]] = []

        for line in candidate.logical_lines:
            text_score = _presence_score(normalized_text, line.normalized_text)
            if text_score < min_text_score:
                continue

            exact_hits = _locate_exact_occurrences_in_text(line.normalized_text, normalized_text)
            if exact_hits:
                for start, end in exact_hits:
                    match = _build_local_match_from_line_norm_span(
                        candidate,
                        line=line,
                        fragment=fragment,
                        norm_start=start,
                        norm_end=end,
                        base_score=1.0,
                    )
                    if match is not None:
                        line_matches.append((round(0.72 * match.score + 0.28 * text_score, 6), match))
                continue

            if exact_only:
                continue

            target_len = len(normalized_text)
            lower_len = max(1, target_len - min(APPROX_LOCAL_SCAN_WINDOW, max(2, target_len // 3)))
            upper_len = min(
                len(line.normalized_text),
                target_len + min(APPROX_LOCAL_SCAN_WINDOW, max(2, target_len // 3)),
            )
            for start in range(0, len(line.normalized_text)):
                if start + lower_len > len(line.normalized_text):
                    break
                for window_len in range(lower_len, upper_len + 1):
                    end = start + window_len
                    if end > len(line.normalized_text):
                        break
                    segment = line.normalized_text[start:end]
                    segment_score = semantic_similarity_norm(normalized_text, segment)
                    if segment_score < min_text_score:
                        continue
                    match = _build_local_match_from_line_norm_span(
                        candidate,
                        line=line,
                        fragment=fragment,
                        norm_start=start,
                        norm_end=end,
                        base_score=segment_score,
                    )
                    if match is not None:
                        line_matches.append(
                            (
                                round(0.72 * match.score + 0.28 * segment_score, 6),
                                match,
                            )
                        )

        if not line_matches:
            if exact_only:
                return None, "short_fragment_unanchored"
            return None, "low_local_confidence"

        line_matches.sort(
            key=lambda item: (
                item[0],
                item[1].context_score,
                item[1].local_position_score,
            ),
            reverse=True,
        )
        if (
            not str(fragment.get("context_before") or "")
            and not str(fragment.get("context_after") or "")
            and len(line_matches) > 1
        ):
            return None, "multiple_local_candidates"
        if (
            len(line_matches) > 1
            and abs(line_matches[0][0] - line_matches[1][0]) < 0.02
            and abs(line_matches[0][1].context_score - line_matches[1][1].context_score) < 0.05
        ):
            return None, "multiple_local_candidates"

        return line_matches[0][1], None

    exact_hits = _locate_exact_occurrences(candidate, normalized_text)
    exact_matches: list[_LocalMatch] = []
    for start, end in exact_hits:
        match = _build_local_match_from_norm_span(
            candidate,
            fragment=fragment,
            norm_start=start,
            norm_end=end,
            base_score=1.0,
        )
        if match is not None:
            exact_matches.append(match)

    if exact_matches:
        exact_matches.sort(
            key=lambda item: (item.score, item.context_score, item.local_position_score),
            reverse=True,
        )
        return exact_matches[0], None

    candidate_text = candidate.normalized_text
    target_len = len(normalized_text)
    if not candidate_text or target_len == 0:
        return None, "no_local_candidate"
    if (
        _is_short_partial_fragment(fragment)
        and target_len <= SHORT_PARTIAL_EXACT_ONLY_MAX_LEN
    ):
        return None, "short_fragment_unanchored"

    scan_window = _approx_local_scan_window(fragment)
    lower_len = max(1, target_len - min(scan_window, max(2, target_len // 3)))
    upper_len = min(
        len(candidate_text),
        target_len + min(scan_window, max(2, target_len // 3)),
    )
    min_text_score = 0.62
    if _is_short_partial_fragment(fragment):
        min_text_score = 0.50
    elif str(fragment.get("container_type") or "paragraph") == "table_cell":
        min_text_score = 0.56

    matches: list[_LocalMatch] = []
    for start in range(0, len(candidate_text)):
        if start + lower_len > len(candidate_text):
            break
        for window_len in range(lower_len, upper_len + 1):
            end = start + window_len
            if end > len(candidate_text):
                break
            segment = candidate_text[start:end]
            text_score = semantic_similarity_norm(normalized_text, segment)
            if text_score < min_text_score:
                continue
            match = _build_local_match_from_norm_span(
                candidate,
                fragment=fragment,
                norm_start=start,
                norm_end=end,
                base_score=text_score,
            )
            if match is not None:
                matches.append(match)

    if not matches:
        return None, "low_local_confidence"

    matches.sort(
        key=lambda item: (item.score, item.context_score, item.local_position_score),
        reverse=True,
    )
    return matches[0], None


def _adaptive_threshold(fragment: InlineStyleFragment) -> float:
    container_type = str(fragment.get("container_type") or "paragraph")
    span_kind = str(fragment.get("source_span_kind") or "partial_span")

    if _is_number_prefix_fragment(fragment):
        return 0.70

    if container_type == "table_cell":
        threshold = 0.68
        if _is_short_partial_fragment(fragment):
            threshold = 0.64
        return min(0.92, max(0.60, threshold))

    if span_kind == "full_container":
        base_length = _normalized_length(fragment.get("normalized_container_text"))
        if _is_short_title_fragment(fragment):
            return 0.68
        if base_length <= SHORT_FULL_CONTAINER_MAX_LEN:
            return 0.74
        if base_length <= 40:
            return 0.76
        return 0.74

    base_length = _normalized_length(fragment.get("normalized_text"))
    if base_length <= 3:
        return 0.68
    if base_length <= SHORT_PARTIAL_MAX_LEN:
        return 0.70
    if base_length <= 12:
        return 0.74
    if base_length <= 24:
        return 0.76
    return 0.78


def _final_candidate_score(
    *,
    fragment: InlineStyleFragment,
    probe: _CandidateProbe,
    local_match: Optional[_LocalMatch],
) -> float:
    container_type = str(fragment.get("container_type") or "paragraph")
    span_kind = str(fragment.get("source_span_kind") or "partial_span")
    container_score = probe.container_score
    position_score = probe.position_score
    local_hint_score = probe.local_hint_score

    if container_type == "table_cell":
        local_score = local_match.score if local_match is not None else max(local_hint_score, container_score)
        return round(
            0.18 * container_score
            + 0.22 * position_score
            + 0.25 * probe.structure_score
            + 0.35 * local_score,
            6,
        )

    if _is_number_prefix_fragment(fragment):
        local_score = local_match.score if local_match is not None else 0.0
        return round(
            0.45 * max(container_score, local_hint_score)
            + 0.20 * position_score
            + 0.35 * local_score,
            6,
        )

    if span_kind == "full_container":
        if _is_short_title_fragment(fragment):
            title_match_score = probe.local_match.score if probe.local_match is not None else 0.0
            return round(
                0.65 * max(probe.title_score, title_match_score)
                + 0.35 * position_score,
                6,
            )
        return round(
            0.55 * container_score
            + 0.20 * position_score
            + 0.25 * max(local_hint_score, probe.title_score),
            6,
        )

    local_score = local_match.score if local_match is not None else 0.0
    if _is_short_partial_fragment(fragment):
        return round(
            0.15 * container_score + 0.25 * position_score + 0.60 * local_score,
            6,
        )
    return round(
        0.25 * container_score + 0.20 * position_score + 0.55 * local_score,
        6,
    )


def _select_candidate_containers(
    fragment: InlineStyleFragment,
    candidates: Sequence[_ContainerCandidate],
) -> tuple[list[_CandidateProbe], Optional[str], list[_CandidateProbe]]:
    container_type = str(fragment.get("container_type") or "paragraph")
    fragment_locator = dict(fragment.get("container_locator") or {})
    fragment_container_text = str(fragment.get("normalized_container_text") or "")
    fragment_local_text = str(fragment.get("normalized_text") or "")
    fragment_position = float(fragment.get("position_ratio") or 0.0)

    typed_candidates = [item for item in candidates if item.container_type == container_type]
    if container_type == "table_cell":
        if not typed_candidates:
            return [], "table_structure_changed", []

        exact = [
            item
            for item in typed_candidates
            if _container_locator_equals(item.container_locator, fragment_locator)
        ]
        if exact:
            selected = [
                _CandidateProbe(
                    candidate=exact[0],
                    container_score=semantic_similarity_norm(
                        fragment_container_text,
                        exact[0].normalized_text,
                    ),
                    local_hint_score=_presence_score(fragment_local_text, exact[0].normalized_text),
                    position_score=_position_score(fragment_position, exact[0].position_ratio),
                    title_score=_presence_score(fragment_container_text, exact[0].normalized_text),
                    structure_score=1.0,
                    coarse_score=1.0,
                    selected=True,
                )
            ]
            return selected, None, selected

        source_table_index = fragment_locator.get("table_index")
        same_table = [
            item
            for item in typed_candidates
            if item.container_locator.get("table_index") == source_table_index
        ]
        if not same_table:
            return [], "table_structure_changed", []

        probes: list[_CandidateProbe] = []
        for candidate in same_table:
            container_score = semantic_similarity_norm(fragment_container_text, candidate.normalized_text)
            local_hint = _presence_score(fragment_local_text, candidate.normalized_text)
            position_score = _position_score(fragment_position, candidate.position_ratio)
            structure_score = _table_structure_score(fragment_locator, candidate.container_locator)
            coarse_score = round(
                0.42 * max(container_score, local_hint)
                + 0.23 * position_score
                + 0.35 * structure_score,
                6,
            )
            rejection_reason = ""
            if max(container_score, local_hint) < 0.18:
                rejection_reason = "候选单元格语义过弱"
            elif coarse_score < 0.26:
                rejection_reason = "同表候选综合分过低"
            probes.append(
                _CandidateProbe(
                    candidate=candidate,
                    container_score=container_score,
                    local_hint_score=local_hint,
                    position_score=position_score,
                    structure_score=structure_score,
                    coarse_score=coarse_score,
                    selected=not rejection_reason,
                    rejection_reason=rejection_reason,
                )
            )

        probes.sort(key=lambda item: (item.coarse_score, item.position_score, item.structure_score), reverse=True)
        selected = [item for item in probes if item.selected][: _candidate_limit(fragment)]
        if not selected:
            return [], "no_same_table_candidate", probes
        return selected, None, probes

    probes = []
    is_title_fragment = _is_short_title_fragment(fragment)
    is_short_partial = _is_short_partial_fragment(fragment)
    is_number_prefix = _is_number_prefix_fragment(fragment)
    coarse_threshold = 0.35
    if is_number_prefix:
        coarse_threshold = 0.34
    elif is_title_fragment:
        coarse_threshold = 0.40
    elif is_short_partial:
        coarse_threshold = 0.34

    for candidate in typed_candidates:
        container_score = semantic_similarity_norm(fragment_container_text, candidate.normalized_text)
        local_hint = _presence_score(fragment_local_text, candidate.normalized_text)
        position_score = _position_score(fragment_position, candidate.position_ratio)
        title_score = 0.0
        title_match: Optional[_LocalMatch] = None

        if is_number_prefix:
            local_hint = _presence_score(fragment_container_text, candidate.normalized_text)
        elif is_title_fragment:
            title_score, position_score, title_match = _match_short_title_line(
                candidate,
                fragment,
            )
        elif is_short_partial and candidate.logical_lines:
            local_hint, position_score = _best_short_partial_line_hint(candidate, fragment)

        if is_number_prefix:
            coarse_score = round(
                0.55 * max(container_score, local_hint)
                + 0.25 * position_score
                + 0.20 * semantic_similarity(
                    str(fragment.get("context_after") or ""),
                    candidate.visible_text,
                ),
                6,
            )
        elif is_title_fragment:
            coarse_score = round(
                0.70 * title_score + 0.30 * position_score,
                6,
            )
        elif is_short_partial:
            coarse_score = round(
                0.60 * local_hint + 0.15 * container_score + 0.25 * position_score,
                6,
            )
        else:
            coarse_score = round(
                0.60 * container_score + 0.20 * position_score + 0.20 * local_hint,
                6,
            )

        rejection_reason = ""
        if max(container_score, local_hint, title_score) <= 0:
            rejection_reason = "候选容器不含目标语义"
        elif coarse_score < coarse_threshold:
            rejection_reason = "候选容器粗筛分过低"

        probes.append(
            _CandidateProbe(
                candidate=candidate,
                container_score=container_score,
                local_hint_score=local_hint,
                position_score=position_score,
                title_score=title_score,
                coarse_score=coarse_score,
                selected=not rejection_reason,
                rejection_reason=rejection_reason,
                local_match=title_match,
            )
        )

    probes.sort(
        key=lambda item: (item.coarse_score, item.position_score, item.local_hint_score, item.title_score),
        reverse=True,
    )
    selected = [item for item in probes if item.selected][: _candidate_limit(fragment)]
    if not selected:
        return [], _default_no_candidate_reason(fragment), probes
    return selected, None, probes


def _format_probe_reason(reason: str) -> str:
    if not reason:
        return ""
    translated = translate_inline_style_reason(reason)
    if translated != reason:
        return translated
    return reason


def _build_candidate_diagnostics(probes: Sequence[_CandidateProbe]) -> str:
    if not probes:
        return ""

    summaries: list[str] = []
    for probe in list(probes)[:CANDIDATE_DIAGNOSTIC_LIMIT]:
        parts = [
            _format_container_hint(probe.candidate.container_type, probe.candidate.container_locator),
            f"粗分={probe.coarse_score:.3f}",
            f"位置={probe.position_score:.2f}",
        ]
        if probe.final_score > 0:
            parts.append(f"终分={probe.final_score:.3f}")
        if probe.container_score > 0:
            parts.append(f"容器={probe.container_score:.2f}")
        if probe.local_hint_score > 0:
            parts.append(f"片段={probe.local_hint_score:.2f}")
        if probe.title_score > 0:
            parts.append(f"标题={probe.title_score:.2f}")
        if probe.structure_score > 0:
            parts.append(f"结构={probe.structure_score:.2f}")

        reason = probe.local_error or probe.rejection_reason
        if reason:
            parts.append(f"淘汰={_format_probe_reason(reason)}")
        elif not probe.selected:
            parts.append("淘汰=未进入候选池")
        summaries.append("，".join(parts))

    return "； ".join(summaries)


def _apply_fragment_style_to_font(font, fragment: InlineStyleFragment) -> None:
    if font is None:
        return

    style_flags = fragment.get("style_flags") or {}
    if style_flags.get("strikethrough"):
        font.StrikeThrough = True
    if style_flags.get("bold"):
        font.Bold = True
    if style_flags.get("italic"):
        font.Italic = True

    underline_style = fragment.get("underline_style")
    if style_flags.get("underline"):
        font.Underline = underline_style or True

    font_color = fragment.get("font_color")
    if font_color is not None:
        font.Color = int(font_color)

    highlight_color = fragment.get("highlight_color")
    if highlight_color is not None:
        font.HighlightColorIndex = int(highlight_color)


def _apply_fragment_style(target_range, fragment: InlineStyleFragment) -> None:
    _apply_fragment_style_to_font(getattr(target_range, "Font", None), fragment)


def _apply_fragment_style_to_list_label(target_range, fragment: InlineStyleFragment) -> bool:
    try:
        list_format = getattr(target_range, "ListFormat", None)
    except Exception:
        return False
    if list_format is None or not _read_list_string(list_format):
        return False

    font = _read_list_level_font(list_format)
    if font is None:
        return False

    _apply_fragment_style_to_font(font, fragment)
    return True


def _increment_applied_style_counters(
    applied_by_style: dict[str, int],
    fragment: InlineStyleFragment,
) -> None:
    style_flags = fragment.get("style_flags") or {}
    for style_name in ("strikethrough", "underline", "bold", "italic"):
        if style_flags.get(style_name):
            applied_by_style[style_name] = applied_by_style.get(style_name, 0) + 1

    if fragment.get("font_color") is not None:
        applied_by_style["font_color"] = applied_by_style.get("font_color", 0) + 1
    if fragment.get("highlight_color") is not None:
        applied_by_style["highlight_color"] = (
            applied_by_style.get("highlight_color", 0) + 1
        )


def _resolve_target_text(
    fragment: InlineStyleFragment,
    candidate: Optional[_ContainerCandidate],
    local_match: Optional[_LocalMatch],
) -> str:
    if candidate is None:
        return ""

    if _is_number_prefix_fragment(fragment) and local_match is not None:
        if int(local_match.actual_end) <= int(local_match.actual_start):
            return str(fragment.get("number_prefix_text") or fragment.get("source_text") or "")
        return candidate.visible_text[local_match.visible_start : local_match.visible_end]

    if str(fragment.get("source_span_kind") or "partial_span") == "full_container":
        if _is_short_title_fragment(fragment) and local_match is not None:
            return candidate.visible_text[local_match.visible_start : local_match.visible_end]
        return candidate.visible_text

    if local_match is None:
        return ""

    return candidate.visible_text[local_match.visible_start : local_match.visible_end]


def _build_writeback_outcome_log(
    *,
    step_label: str,
    index: int,
    total: int,
    status: str,
    fragment: InlineStyleFragment,
    reason: str = "",
    target_text: str = "",
    error: str = "",
    max_text_chars: int = LOG_TEXT_LIMIT,
) -> str:
    message_parts = [
        f"{step_label}：样式回填{status}[{index}/{total}] {_format_style_labels(fragment)}",
        f"\"{_truncate_log_text(fragment.get('source_text'), max_chars=max_text_chars)}\"",
    ]

    if status == "成功":
        resolved_target = _truncate_log_text(target_text, max_chars=max_text_chars)
        message_parts[-1] = (
            f"\"{_truncate_log_text(fragment.get('source_text'), max_chars=max_text_chars)}\""
            f" -> \"{resolved_target}\""
        )
    elif status == "跳过" and reason:
        message_parts.append(f"原因：{translate_inline_style_reason(reason)}")
    elif status == "失败":
        error_text = error or translate_inline_style_reason(reason)
        if error_text:
            message_parts.append(
                f"错误：{_truncate_log_text(error_text, max_chars=max(120, max_text_chars))}"
            )

    return " | ".join(message_parts)


def _build_writeback_diagnostic_log(
    *,
    step_label: str,
    index: int,
    total: int,
    status: str,
    fragment: InlineStyleFragment,
    reason: str = "",
    target_text: str = "",
    score: Optional[float] = None,
    threshold: Optional[float] = None,
    error: str = "",
    candidate_details: str = "",
    max_text_chars: int = LOG_TEXT_LIMIT,
) -> str:
    message_parts = [
        f"{step_label}：样式回填诊断[{index}/{total}] {status}",
        f"样式={_format_style_labels(fragment)}",
        f"源文本=\"{_truncate_log_text(fragment.get('source_text'), max_chars=max_text_chars)}\"",
        f"容器={_format_container_hint(str(fragment.get('container_type') or 'paragraph'), fragment.get('container_locator'))}",
        f"范围={_format_source_span_kind(fragment)}",
    ]

    if target_text:
        message_parts.append(f"目标文本=\"{_truncate_log_text(target_text, max_chars=max_text_chars)}\"")
    if score is not None:
        message_parts.append(f"得分={float(score):.4f}")
    if threshold is not None:
        message_parts.append(f"阈值={float(threshold):.4f}")
    if reason:
        message_parts.append(f"原因={translate_inline_style_reason(reason)}")
    if error:
        message_parts.append(f"错误={_truncate_log_text(error, max_chars=max(120, max_text_chars))}")
    if candidate_details:
        message_parts.append(
            f"候选={_truncate_log_text(candidate_details, max_chars=max(220, max_text_chars))}"
        )

    return " | ".join(message_parts)


def _build_success_example(fragment: InlineStyleFragment, target_text: str) -> str:
    style_label = _format_style_labels(fragment)
    source_text = _truncate_log_text(
        fragment.get("source_text"),
        max_chars=SUCCESS_EXAMPLE_TEXT_LIMIT,
    )
    resolved_target = _truncate_log_text(
        target_text,
        max_chars=SUCCESS_EXAMPLE_TEXT_LIMIT,
    )
    return f'{style_label} "{source_text}" -> "{resolved_target}"'


def _build_writeback_success_examples_log(
    *,
    step_label: str,
    examples: Sequence[str],
) -> str:
    visible_examples = list(examples)[:SUCCESS_EXAMPLE_LIMIT]
    body = "； ".join(visible_examples)
    if len(examples) > SUCCESS_EXAMPLE_LIMIT:
        body = f"{body}；等 {len(examples)} 项"
    return f"{step_label}：样式回填命中 | {body}"


def apply_inline_style_fragments(
    *,
    doc,
    inline_style_fragments: Iterable[Dict[str, Any]] | None,
    bound_start: int,
    bound_end: int,
    log_parts: list[str],
    step_label: str = "步骤6",
    progress_logger: Optional[Callable[[str], Any]] = None,
    diagnostic_logger: Optional[Callable[[str], Any]] = None,
) -> InlineStyleWritebackResult:
    """将抽取的行内样式按高召回 + 最低安全线策略回填到新正文中。"""
    fragments = [
        _normalize_fragment_font_color(InlineStyleFragment(**dict(item)))
        for item in list(inline_style_fragments or [])
    ]
    result: InlineStyleWritebackResult = {
        "extracted": len(fragments),
        "attempted": 0,
        "applied": 0,
        "skipped": 0,
        "failed": 0,
        "issues": [],
        "applied_by_style": {},
        "skipped_by_reason": {},
    }

    if int(bound_end) <= int(bound_start):
        _emit_runtime_log(log_parts, f"{step_label}：样式回填范围为空，跳过。", progress_logger)
        result["skipped"] = len(fragments)
        for index, fragment in enumerate(fragments, start=1):
            _append_issue(
                result,
                index=index,
                reason="empty_search_bound",
                fragment=fragment,
            )
            _emit_runtime_log(
                log_parts,
                _build_writeback_outcome_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="跳过",
                    fragment=fragment,
                    reason="empty_search_bound",
                ),
                progress_logger,
            )
            _emit_diagnostic_log(
                _build_writeback_diagnostic_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="跳过",
                    fragment=fragment,
                    reason="empty_search_bound",
                ),
                diagnostic_logger,
            )
        return result

    if not fragments:
        _emit_runtime_log(log_parts, f"{step_label}：未提取到可回填的行内样式。", progress_logger)
        return result

    target_containers: Optional[list[_ContainerCandidate]] = None
    success_examples: list[str] = []
    _emit_runtime_log(
        log_parts,
        f"{step_label}：开始回填行内样式，共 {len(fragments)} 个片段。",
        progress_logger,
    )
    _emit_diagnostic_log(
        f"{step_label}：font_color_gate_version={FONT_COLOR_GATE_VERSION}",
        diagnostic_logger,
    )

    for index, fragment in enumerate(fragments, start=1):
        result["attempted"] += 1
        if not _fragment_has_effective_style(fragment):
            reason = "empty_fragment"
            result["skipped"] += 1
            _append_issue(
                result,
                index=index,
                reason=reason,
                fragment=fragment,
            )
            _emit_runtime_log(
                log_parts,
                _build_writeback_outcome_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="跳过",
                    fragment=fragment,
                    reason=reason,
                ),
                progress_logger,
            )
            _emit_diagnostic_log(
                _build_writeback_diagnostic_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="跳过",
                    fragment=fragment,
                    reason=reason,
                ),
                diagnostic_logger,
            )
            continue

        if _is_number_prefix_fragment(fragment) and _has_high_visible_risk_style(fragment):
            reason = "number_prefix_high_visible_style"
            result["skipped"] += 1
            _append_issue(
                result,
                index=index,
                reason=reason,
                fragment=fragment,
            )
            _emit_runtime_log(
                log_parts,
                _build_writeback_outcome_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="跳过",
                    fragment=fragment,
                    reason=reason,
                ),
                progress_logger,
            )
            _emit_diagnostic_log(
                _build_writeback_diagnostic_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="跳过",
                    fragment=fragment,
                    reason=reason,
                ),
                diagnostic_logger,
            )
            continue

        active_fragment = fragment
        static_color_reason = _static_font_color_block_reason(fragment)
        if static_color_reason:
            active_fragment = _fragment_without_font_color(fragment)
            if not _fragment_has_effective_style(active_fragment):
                result["skipped"] += 1
                _append_issue(
                    result,
                    index=index,
                    reason=static_color_reason,
                    fragment=fragment,
                )
                _emit_runtime_log(
                    log_parts,
                    _build_writeback_outcome_log(
                        step_label=step_label,
                        index=index,
                        total=len(fragments),
                        status="跳过",
                        fragment=fragment,
                        reason=static_color_reason,
                    ),
                    progress_logger,
                )
                _emit_diagnostic_log(
                    _build_writeback_diagnostic_log(
                        step_label=step_label,
                        index=index,
                        total=len(fragments),
                        status="跳过",
                        fragment=fragment,
                        reason=static_color_reason,
                    ),
                    diagnostic_logger,
                )
                continue

            _record_skipped_style_reason(result, static_color_reason)
            _emit_diagnostic_log(
                _build_writeback_diagnostic_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="跳过",
                    fragment=fragment,
                    reason=static_color_reason,
                ),
                diagnostic_logger,
            )

        if target_containers is None:
            target_containers = _build_target_containers(
                doc,
                bound_start=bound_start,
                bound_end=bound_end,
            )

        candidate_probes, no_candidate_reason, all_probes = _select_candidate_containers(
            active_fragment,
            target_containers,
        )
        candidate_details = _build_candidate_diagnostics(all_probes)
        if no_candidate_reason:
            result["skipped"] += 1
            _append_issue(
                result,
                index=index,
                reason=no_candidate_reason,
                fragment=active_fragment,
            )
            _emit_runtime_log(
                log_parts,
                _build_writeback_outcome_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="跳过",
                    fragment=active_fragment,
                    reason=no_candidate_reason,
                ),
                progress_logger,
            )
            _emit_diagnostic_log(
                _build_writeback_diagnostic_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="跳过",
                    fragment=active_fragment,
                    reason=no_candidate_reason,
                    candidate_details=candidate_details,
                ),
                diagnostic_logger,
            )
            continue

        if not candidate_probes:
            result["skipped"] += 1
            reason = _default_no_candidate_reason(active_fragment)
            _append_issue(
                result,
                index=index,
                reason=reason,
                fragment=active_fragment,
            )
            _emit_runtime_log(
                log_parts,
                _build_writeback_outcome_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="跳过",
                    fragment=active_fragment,
                    reason=reason,
                ),
                progress_logger,
            )
            _emit_diagnostic_log(
                _build_writeback_diagnostic_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="跳过",
                    fragment=active_fragment,
                    reason=reason,
                    candidate_details=candidate_details,
                ),
                diagnostic_logger,
            )
            continue

        matches: list[tuple[float, _CandidateProbe, Optional[_LocalMatch]]] = []
        local_failures: list[str] = []
        for probe in candidate_probes:
            candidate = probe.candidate
            local_match: Optional[_LocalMatch] = probe.local_match
            local_error = None
            if _is_number_prefix_fragment(active_fragment):
                local_match, local_error = _locate_number_prefix_span(
                    candidate,
                    active_fragment,
                    doc=doc,
                )
                if local_error:
                    probe.local_error = local_error
                    local_failures.append(local_error)
                    continue
            elif str(active_fragment.get("source_span_kind") or "partial_span") == "partial_span":
                local_match, local_error = _locate_local_span(candidate, active_fragment)
                if local_error:
                    probe.local_error = local_error
                    local_failures.append(local_error)
                    continue
                gate_reason = _short_partial_match_gate_reason(active_fragment, probe, local_match)
                if gate_reason:
                    probe.local_error = gate_reason
                    local_failures.append(gate_reason)
                    continue
            elif _is_short_title_fragment(active_fragment) and local_match is None:
                probe.local_error = "no_local_candidate"
                local_failures.append("no_local_candidate")
                continue

            final_score = _final_candidate_score(
                fragment=active_fragment,
                probe=probe,
                local_match=local_match,
            )
            probe.final_score = final_score
            probe.local_match = local_match
            matches.append((final_score, probe, local_match))

        candidate_details = _build_candidate_diagnostics(all_probes)

        if not matches:
            reason = "low_confidence"
            if local_failures and len(set(local_failures)) == 1:
                reason = local_failures[0]
            if _is_font_color_only_partial_fragment(active_fragment):
                reason = "font_color_unanchored_partial"
            result["skipped"] += 1
            _append_issue(
                result,
                index=index,
                reason=reason,
                fragment=active_fragment,
            )
            _emit_runtime_log(
                log_parts,
                _build_writeback_outcome_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="跳过",
                    fragment=active_fragment,
                    reason=reason,
                ),
                progress_logger,
            )
            _emit_diagnostic_log(
                _build_writeback_diagnostic_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="跳过",
                    fragment=active_fragment,
                    reason=reason,
                    candidate_details=candidate_details,
                ),
                diagnostic_logger,
            )
            continue

        matches.sort(
            key=lambda item: (
                item[0],
                item[1].position_score,
                item[2].context_score if item[2] is not None else 0.0,
                item[2].local_position_score if item[2] is not None else 0.0,
            ),
            reverse=True,
        )
        best_score, best_probe, best_local_match = matches[0]
        best_candidate = best_probe.candidate
        threshold = _adaptive_threshold(active_fragment)
        if best_score < threshold:
            best_probe.rejection_reason = "终分低于阈值"
            candidate_details = _build_candidate_diagnostics(all_probes)
            reason = (
                "font_color_unanchored_partial"
                if _is_font_color_only_partial_fragment(active_fragment)
                else "low_confidence"
            )
            result["skipped"] += 1
            _append_issue(
                result,
                index=index,
                reason=reason,
                fragment=active_fragment,
                score=best_score,
            )
            _emit_runtime_log(
                log_parts,
                _build_writeback_outcome_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="跳过",
                    fragment=active_fragment,
                    reason=reason,
                ),
                progress_logger,
            )
            _emit_diagnostic_log(
                _build_writeback_diagnostic_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="跳过",
                    fragment=active_fragment,
                    reason=reason,
                    score=best_score,
                    threshold=threshold,
                    candidate_details=candidate_details,
                ),
                diagnostic_logger,
            )
            continue

        if (
            len(matches) > 1
            and abs(best_score - matches[1][0]) < 0.01
            and abs(best_probe.position_score - matches[1][1].position_score) < 0.01
        ):
            best_probe.rejection_reason = "候选位置区分度不足"
            candidate_details = _build_candidate_diagnostics(all_probes)
            reason = (
                "font_color_unanchored_partial"
                if _is_font_color_only_partial_fragment(active_fragment)
                else "multiple_candidate_conflict"
            )
            result["skipped"] += 1
            _append_issue(
                result,
                index=index,
                reason=reason,
                fragment=active_fragment,
                score=best_score,
            )
            _emit_runtime_log(
                log_parts,
                _build_writeback_outcome_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="跳过",
                    fragment=active_fragment,
                    reason=reason,
                ),
                progress_logger,
            )
            _emit_diagnostic_log(
                _build_writeback_diagnostic_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="跳过",
                    fragment=active_fragment,
                    reason=reason,
                    score=best_score,
                    threshold=threshold,
                    candidate_details=candidate_details,
                ),
                diagnostic_logger,
            )
            continue

        apply_to_list_label = False
        if _is_number_prefix_fragment(active_fragment):
            if best_local_match is None:
                result["skipped"] += 1
                _append_issue(
                    result,
                    index=index,
                    reason="no_number_prefix_target",
                    fragment=active_fragment,
                    score=best_score,
                )
                _emit_runtime_log(
                    log_parts,
                    _build_writeback_outcome_log(
                        step_label=step_label,
                        index=index,
                        total=len(fragments),
                        status="跳过",
                        fragment=active_fragment,
                        reason="no_number_prefix_target",
                    ),
                    progress_logger,
                )
                _emit_diagnostic_log(
                    _build_writeback_diagnostic_log(
                        step_label=step_label,
                        index=index,
                        total=len(fragments),
                        status="跳过",
                        fragment=active_fragment,
                        reason="no_number_prefix_target",
                        score=best_score,
                        threshold=threshold,
                        candidate_details=candidate_details,
                    ),
                    diagnostic_logger,
                )
                continue
            actual_start = best_local_match.actual_start
            actual_end = best_local_match.actual_end
            apply_to_list_label = int(actual_end) <= int(actual_start)
        elif str(active_fragment.get("source_span_kind") or "partial_span") == "full_container":
            if _is_short_title_fragment(active_fragment) and best_local_match is not None:
                actual_start = best_local_match.actual_start
                actual_end = best_local_match.actual_end
            else:
                actual_span = _resolve_actual_span(
                    best_candidate,
                    0,
                    len(best_candidate.visible_text),
                )
                if actual_span is None:
                    result["skipped"] += 1
                    _append_issue(
                        result,
                        index=index,
                        reason="empty_target_span",
                        fragment=active_fragment,
                        score=best_score,
                    )
                    _emit_runtime_log(
                        log_parts,
                        _build_writeback_outcome_log(
                            step_label=step_label,
                            index=index,
                            total=len(fragments),
                            status="跳过",
                            fragment=active_fragment,
                            reason="empty_target_span",
                        ),
                        progress_logger,
                    )
                    _emit_diagnostic_log(
                        _build_writeback_diagnostic_log(
                            step_label=step_label,
                            index=index,
                            total=len(fragments),
                            status="跳过",
                            fragment=active_fragment,
                            reason="empty_target_span",
                            score=best_score,
                            threshold=threshold,
                            candidate_details=candidate_details,
                        ),
                        diagnostic_logger,
                    )
                    continue
                actual_start, actual_end = actual_span
        else:
            if best_local_match is None:
                result["skipped"] += 1
                _append_issue(
                    result,
                    index=index,
                    reason="low_local_confidence",
                    fragment=active_fragment,
                    score=best_score,
                )
                _emit_runtime_log(
                    log_parts,
                    _build_writeback_outcome_log(
                        step_label=step_label,
                        index=index,
                        total=len(fragments),
                        status="跳过",
                        fragment=active_fragment,
                        reason="low_local_confidence",
                    ),
                    progress_logger,
                )
                _emit_diagnostic_log(
                    _build_writeback_diagnostic_log(
                        step_label=step_label,
                        index=index,
                        total=len(fragments),
                        status="跳过",
                        fragment=active_fragment,
                        reason="low_local_confidence",
                        score=best_score,
                        threshold=threshold,
                        candidate_details=candidate_details,
                    ),
                    diagnostic_logger,
                )
                continue
            actual_start = best_local_match.actual_start
            actual_end = best_local_match.actual_end

        if int(actual_end) <= int(actual_start) and not apply_to_list_label:
            result["skipped"] += 1
            _append_issue(
                result,
                index=index,
                reason="empty_target_span",
                fragment=active_fragment,
                score=best_score,
            )
            _emit_runtime_log(
                log_parts,
                _build_writeback_outcome_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="跳过",
                    fragment=active_fragment,
                    reason="empty_target_span",
                ),
                progress_logger,
            )
            _emit_diagnostic_log(
                _build_writeback_diagnostic_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="跳过",
                    fragment=active_fragment,
                    reason="empty_target_span",
                    score=best_score,
                    threshold=threshold,
                    candidate_details=candidate_details,
                ),
                diagnostic_logger,
            )
            continue

        effective_fragment, color_block_reason = _resolve_effective_fragment_for_writeback(
            active_fragment,
            candidate=best_candidate,
            local_match=best_local_match,
            target_containers=target_containers or [],
        )
        if color_block_reason:
            color_gate_diagnostic = _build_font_color_gate_diagnostic(
                active_fragment,
                candidate=best_candidate,
                local_match=best_local_match,
                target_containers=target_containers or [],
                reason=color_block_reason,
            )
            if not _fragment_has_effective_style(effective_fragment):
                result["skipped"] += 1
                _append_issue(
                    result,
                    index=index,
                    reason=color_block_reason,
                    fragment=active_fragment,
                    score=best_score,
                )
                _emit_runtime_log(
                    log_parts,
                    _build_writeback_outcome_log(
                        step_label=step_label,
                        index=index,
                        total=len(fragments),
                        status="跳过",
                        fragment=active_fragment,
                        reason=color_block_reason,
                    ),
                    progress_logger,
                )
                _emit_diagnostic_log(
                    _build_writeback_diagnostic_log(
                        step_label=step_label,
                        index=index,
                        total=len(fragments),
                        status="跳过",
                        fragment=active_fragment,
                        reason=color_block_reason,
                        score=best_score,
                        threshold=threshold,
                        candidate_details=(
                            f"{candidate_details}； {color_gate_diagnostic}"
                            if candidate_details
                            else color_gate_diagnostic
                        ),
                    ),
                    diagnostic_logger,
                )
                continue

            _record_skipped_style_reason(result, color_block_reason)
            _emit_diagnostic_log(
                _build_writeback_diagnostic_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="跳过",
                    fragment=active_fragment,
                    reason=color_block_reason,
                    score=best_score,
                    threshold=threshold,
                    candidate_details=(
                        f"{candidate_details}； {color_gate_diagnostic}"
                        if candidate_details
                        else color_gate_diagnostic
                    ),
                ),
                diagnostic_logger,
            )

        try:
            if apply_to_list_label:
                target_range = doc.Range(
                    int(best_candidate.range_start),
                    int(best_candidate.range_end),
                )
                if not _apply_fragment_style_to_list_label(target_range, effective_fragment):
                    raise RuntimeError("目标自动编号标签不可写")
            else:
                target_range = doc.Range(int(actual_start), int(actual_end))
                _apply_fragment_style(target_range, effective_fragment)
            result["applied"] += 1
            _increment_applied_style_counters(result["applied_by_style"], effective_fragment)
            resolved_target_text = _resolve_target_text(
                effective_fragment,
                best_candidate,
                best_local_match,
            )
            success_examples.append(_build_success_example(effective_fragment, resolved_target_text))
            _emit_runtime_log(
                log_parts,
                _build_writeback_outcome_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="成功",
                    fragment=effective_fragment,
                    target_text=resolved_target_text,
                ),
                progress_logger,
            )
            _emit_diagnostic_log(
                _build_writeback_diagnostic_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="成功",
                    fragment=effective_fragment,
                    target_text=resolved_target_text,
                    score=best_score,
                    threshold=threshold,
                    candidate_details=candidate_details,
                ),
                diagnostic_logger,
            )
        except Exception as exc:
            result["failed"] += 1
            issue: InlineStyleWritebackIssue = {
                "index": int(index),
                "reason": "apply_failed",
                "source_text": str(effective_fragment.get("source_text") or "")[:120],
                "container_type": str(effective_fragment.get("container_type") or "paragraph"),
                "container_locator": dict(effective_fragment.get("container_locator") or {}),
                "score": round(float(best_score), 4),
                "error": str(exc),
            }
            result["issues"].append(issue)
            _emit_runtime_log(
                log_parts,
                _build_writeback_outcome_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="失败",
                    fragment=effective_fragment,
                    target_text=_resolve_target_text(effective_fragment, best_candidate, best_local_match),
                    reason="apply_failed",
                    error=str(exc),
                ),
                progress_logger,
            )
            _emit_diagnostic_log(
                _build_writeback_diagnostic_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="失败",
                    fragment=effective_fragment,
                    target_text=_resolve_target_text(effective_fragment, best_candidate, best_local_match),
                    reason="apply_failed",
                    score=best_score,
                    threshold=threshold,
                    error=str(exc),
                    candidate_details=candidate_details,
                ),
                diagnostic_logger,
            )
            continue

    _emit_runtime_log(log_parts, summarize_style_writeback_result(result), progress_logger)
    if success_examples:
        _emit_runtime_log(
            log_parts,
            _build_writeback_success_examples_log(
                step_label=step_label,
                examples=success_examples,
            ),
            progress_logger,
        )
    return result


def summarize_style_writeback_result(result: InlineStyleWritebackResult) -> str:
    summary = (
        "样式回填: "
        f"抽取={result.get('extracted', 0)}, "
        f"尝试={result.get('attempted', 0)}, "
        f"成功={result.get('applied', 0)}, "
        f"跳过={result.get('skipped', 0)}, "
        f"失败={result.get('failed', 0)}"
    )

    applied_by_style = result.get("applied_by_style") or {}
    if applied_by_style:
        ordered_styles = ", ".join(
            f"{STYLE_LABEL_MAP.get(style, style)}={count}"
            for style, count in sorted(applied_by_style.items())
        )
        summary = f"{summary}; 命中样式: {ordered_styles}"
    return summary


def build_style_writeback_summary_payload(
    result: InlineStyleWritebackResult | None,
    summary: str = "",
) -> Optional[Dict[str, Any]]:
    if result is None:
        return None

    return {
        "summary": summary or summarize_style_writeback_result(result),
        "extracted": int(result.get("extracted", 0)),
        "attempted": int(result.get("attempted", 0)),
        "applied": int(result.get("applied", 0)),
        "skipped": int(result.get("skipped", 0)),
        "failed": int(result.get("failed", 0)),
        "applied_by_style": dict(result.get("applied_by_style") or {}),
        "skipped_by_reason": dict(result.get("skipped_by_reason") or {}),
    }


__all__ = [
    "InlineStyleFlags",
    "InlineStyleContainerLocator",
    "InlineStyleFragment",
    "InlineStyleWritebackIssue",
    "InlineStyleWritebackResult",
    "build_inline_style_fragments_from_text_runs",
    "build_inline_style_extraction_logs",
    "extract_inline_style_fragments",
    "apply_inline_style_fragments",
    "summarize_style_writeback_result",
    "build_style_writeback_summary_payload",
    "translate_inline_style_reason",
]
