"""
edit 链路的行内样式抽取与回填 helper。

第一版边界：
- 只处理锚点区正文段落与表格单元格
- 只处理 run/字符级样式，不处理段落版式
- 仅保守回填唯一高置信命中的片段
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Literal, Optional, Sequence, TypedDict

from backend.helper.word_helper.semantic_matcher import (
    normalize_semantic_text,
    semantic_similarity,
    semantic_similarity_norm,
    strip_number_prefix,
)
from backend.util.word_util import wdWithInTable

ContainerType = Literal["paragraph", "table_cell"]
SourceSpanKind = Literal["full_container", "partial_span"]

CONTROL_CHAR_TEXT = {"\a": "", "\x07": "", "\f": "", "\r": "\n", "\n": "\n", "\v": "\n"}
BLACK_COLOR = 0
AUTOMATIC_COLOR = 0
WINDOWS_AUTO_COLOR = -16777216
NO_HIGHLIGHT = 0
CONTEXT_CHARS = 24
CONTAINER_CANDIDATE_LIMIT = 5
APPROX_LOCAL_SCAN_WINDOW = 18
LOG_TEXT_LIMIT = 80

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
    "no_local_candidate": "未找到局部文本命中位置",
    "table_structure_changed": "表格结构已变化，无法按原单元格定位",
}
SPAN_KIND_LABEL_MAP = {
    "full_container": "整容器",
    "partial_span": "局部片段",
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
    style_flags: InlineStyleFlags
    font_color: Optional[int]
    highlight_color: Optional[int]
    font_name: Optional[str]
    font_size: Optional[float]
    underline_style: Optional[int]
    source_span_kind: SourceSpanKind


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
    position_ratio: float
    range_start: int
    range_end: int


@dataclass(frozen=True)
class _LocalMatch:
    visible_start: int
    visible_end: int
    actual_start: int
    actual_end: int
    score: float
    context_score: float


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


def build_inline_style_extraction_logs(
    inline_style_fragments: Iterable[Dict[str, Any]] | None,
    *,
    step_label: str = "样式提取",
    max_text_chars: int = LOG_TEXT_LIMIT,
) -> list[str]:
    fragments = [InlineStyleFragment(**dict(item)) for item in list(inline_style_fragments or [])]
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


def _build_character_signature(char_range) -> CharacterStyleSignature:
    underline_style = _safe_int(_read_font_property(char_range, "Underline", 0), default=0)
    signature: CharacterStyleSignature = {
        "style_flags": {
            "strikethrough": bool(_read_font_property(char_range, "StrikeThrough", False)),
            "underline": bool(underline_style),
            "bold": bool(_read_font_property(char_range, "Bold", False)),
            "italic": bool(_read_font_property(char_range, "Italic", False)),
        },
        "font_color": _normalize_font_color(_read_font_property(char_range, "Color", BLACK_COLOR)),
        "highlight_color": _normalize_highlight_color(
            _read_font_property(char_range, "HighlightColorIndex", NO_HIGHLIGHT)
        ),
        "font_name": str(_read_font_property(char_range, "Name", "") or "").strip() or None,
        "font_size": None,
        "underline_style": underline_style or None,
    }

    font_size = _safe_float(_read_font_property(char_range, "Size", 0))
    if font_size > 0:
        signature["font_size"] = font_size
    return signature


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

    return _ContainerCandidate(
        container_type=container_type,
        container_locator=container_locator,
        visible_chars=visible_chars,
        visible_text=visible_text,
        normalized_text=normalized_text,
        normalized_index_to_visible=normalized_index_to_visible,
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
        if not source_text or not normalized_text:
            current_signature = None
            current_text_parts = []
            current_start = None
            current_end = None
            return

        context_before = container_visible_text[max(0, current_start - CONTEXT_CHARS) : current_start]
        context_after = container_visible_text[current_end : current_end + CONTEXT_CHARS]
        source_span_kind: SourceSpanKind = (
            "full_container"
            if normalized_text == normalized_container_text
            else "partial_span"
        )

        fragments.append(
            InlineStyleFragment(
                container_type=container_type,
                container_locator=dict(container_locator),
                source_text=source_text,
                normalized_text=normalized_text,
                container_text=container_visible_text,
                normalized_container_text=normalized_container_text,
                context_before=context_before,
                context_after=context_after,
                position_ratio=float(position_ratio),
                style_flags=dict(current_signature.get("style_flags") or {}),
                font_color=current_signature.get("font_color"),
                highlight_color=current_signature.get("highlight_color"),
                font_name=current_signature.get("font_name"),
                font_size=current_signature.get("font_size"),
                underline_style=current_signature.get("underline_style"),
                source_span_kind=source_span_kind,
            )
        )

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
        fragments.extend(
            _build_fragments_from_container(
                container_type="paragraph",
                container_locator={"paragraph_index": paragraph_index},
                range_obj=paragraph_range,
                bound_start=bound_start,
                bound_end=bound_end,
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


def _locate_exact_occurrences(candidate: _ContainerCandidate, normalized_text: str) -> list[tuple[int, int]]:
    occurrences: list[tuple[int, int]] = []
    if not normalized_text:
        return occurrences

    start = 0
    while start < len(candidate.normalized_text):
        hit = candidate.normalized_text.find(normalized_text, start)
        if hit < 0:
            break
        occurrences.append((hit, hit + len(normalized_text)))
        start = hit + 1
    return occurrences


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
    final_score = 0.90 * float(base_score) + 0.10 * context_score
    return _LocalMatch(
        visible_start=visible_start,
        visible_end=visible_end,
        actual_start=actual_span[0],
        actual_end=actual_span[1],
        score=final_score,
        context_score=context_score,
    )


def _locate_local_span(
    candidate: _ContainerCandidate,
    fragment: InlineStyleFragment,
) -> tuple[Optional[_LocalMatch], Optional[str]]:
    normalized_text = str(fragment.get("normalized_text") or "")
    if not normalized_text:
        return None, "empty_fragment"

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
        exact_matches.sort(key=lambda item: item.score, reverse=True)
        if (
            len(exact_matches) > 1
            and abs(exact_matches[0].score - exact_matches[1].score) < 0.08
        ):
            return None, "multiple_local_candidates"
        return exact_matches[0], None

    candidate_text = candidate.normalized_text
    target_len = len(normalized_text)
    if not candidate_text or target_len == 0:
        return None, "no_local_candidate"

    lower_len = max(1, target_len - min(APPROX_LOCAL_SCAN_WINDOW, max(2, target_len // 3)))
    upper_len = min(
        len(candidate_text),
        target_len + min(APPROX_LOCAL_SCAN_WINDOW, max(2, target_len // 3)),
    )

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
            if text_score < 0.62:
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

    matches.sort(key=lambda item: item.score, reverse=True)
    if len(matches) > 1 and abs(matches[0].score - matches[1].score) < 0.06:
        return None, "multiple_local_candidates"
    return matches[0], None


def _adaptive_threshold(fragment: InlineStyleFragment) -> float:
    if str(fragment.get("source_span_kind") or "partial_span") == "full_container":
        base_length = len(str(fragment.get("normalized_container_text") or ""))
        threshold = 0.76
        if base_length <= 8:
            threshold = 0.92
        elif base_length <= 16:
            threshold = 0.86
        elif base_length <= 40:
            threshold = 0.80
    else:
        base_length = len(str(fragment.get("normalized_text") or ""))
        threshold = 0.78
        if base_length <= 6:
            threshold = 0.86
        elif base_length <= 12:
            threshold = 0.83
        elif base_length <= 24:
            threshold = 0.80

    if str(fragment.get("container_type") or "paragraph") == "table_cell":
        threshold += 0.06

    return min(0.98, threshold)


def _final_candidate_score(
    *,
    fragment: InlineStyleFragment,
    candidate: _ContainerCandidate,
    local_match: Optional[_LocalMatch],
) -> float:
    container_score = semantic_similarity_norm(
        str(fragment.get("normalized_container_text") or ""),
        candidate.normalized_text,
    )
    position_score = _position_score(
        float(fragment.get("position_ratio") or 0.0),
        candidate.position_ratio,
    )

    if str(fragment.get("source_span_kind") or "partial_span") == "full_container":
        local_score = 1.0
        return round(0.55 * container_score + 0.20 * position_score + 0.25 * local_score, 6)
    else:
        local_score = local_match.score if local_match is not None else 0.0
        return round(0.35 * container_score + 0.20 * position_score + 0.45 * local_score, 6)


def _select_candidate_containers(
    fragment: InlineStyleFragment,
    candidates: Sequence[_ContainerCandidate],
) -> tuple[list[_ContainerCandidate], Optional[str]]:
    container_type = str(fragment.get("container_type") or "paragraph")
    fragment_locator = dict(fragment.get("container_locator") or {})

    typed_candidates = [item for item in candidates if item.container_type == container_type]
    if container_type == "table_cell":
        exact = [
            item
            for item in typed_candidates
            if _container_locator_equals(item.container_locator, fragment_locator)
        ]
        if not exact:
            return [], "table_structure_changed"
        return exact[:1], None

    scored: list[tuple[float, _ContainerCandidate]] = []
    fragment_container_text = str(fragment.get("normalized_container_text") or "")
    fragment_local_text = str(fragment.get("normalized_text") or "")
    fragment_position = float(fragment.get("position_ratio") or 0.0)

    for candidate in typed_candidates:
        container_score = semantic_similarity_norm(fragment_container_text, candidate.normalized_text)
        if container_score <= 0:
            continue

        position_score = _position_score(fragment_position, candidate.position_ratio)
        local_hint = semantic_similarity_norm(fragment_local_text, candidate.normalized_text)
        coarse_score = 0.65 * container_score + 0.20 * position_score + 0.15 * local_hint
        if coarse_score < 0.35:
            continue
        scored.append((coarse_score, candidate))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[:CONTAINER_CANDIDATE_LIMIT]], None


def _apply_fragment_style(target_range, fragment: InlineStyleFragment) -> None:
    font = getattr(target_range, "Font", None)
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

    if str(fragment.get("source_span_kind") or "partial_span") == "full_container":
        return candidate.visible_text

    if local_match is None:
        return ""

    return candidate.visible_text[local_match.visible_start : local_match.visible_end]


def _build_writeback_detail_log(
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
    max_text_chars: int = LOG_TEXT_LIMIT,
) -> str:
    message_parts = [
        f"{step_label}：样式回填[{index}/{total}] {status}",
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

    return " | ".join(message_parts)


def apply_inline_style_fragments(
    *,
    doc,
    inline_style_fragments: Iterable[Dict[str, Any]] | None,
    bound_start: int,
    bound_end: int,
    log_parts: list[str],
    step_label: str = "步骤6",
    progress_logger: Optional[Callable[[str], Any]] = None,
) -> InlineStyleWritebackResult:
    """将抽取的行内样式保守回填到新正文中。"""
    fragments = [InlineStyleFragment(**dict(item)) for item in list(inline_style_fragments or [])]
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
                _build_writeback_detail_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="跳过",
                    fragment=fragment,
                    reason="empty_search_bound",
                ),
                progress_logger,
            )
        return result

    if not fragments:
        _emit_runtime_log(log_parts, f"{step_label}：未提取到可回填的行内样式。", progress_logger)
        return result

    target_containers = _build_target_containers(doc, bound_start=bound_start, bound_end=bound_end)
    _emit_runtime_log(
        log_parts,
        f"{step_label}：开始回填行内样式，共 {len(fragments)} 个片段。",
        progress_logger,
    )

    for index, fragment in enumerate(fragments, start=1):
        result["attempted"] += 1
        candidates, no_candidate_reason = _select_candidate_containers(fragment, target_containers)
        if no_candidate_reason:
            result["skipped"] += 1
            _append_issue(
                result,
                index=index,
                reason=no_candidate_reason,
                fragment=fragment,
            )
            _emit_runtime_log(
                log_parts,
                _build_writeback_detail_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="跳过",
                    fragment=fragment,
                    reason=no_candidate_reason,
                ),
                progress_logger,
            )
            continue

        if not candidates:
            result["skipped"] += 1
            _append_issue(
                result,
                index=index,
                reason="no_candidate_container",
                fragment=fragment,
            )
            _emit_runtime_log(
                log_parts,
                _build_writeback_detail_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="跳过",
                    fragment=fragment,
                    reason="no_candidate_container",
                ),
                progress_logger,
            )
            continue

        matches: list[tuple[float, _ContainerCandidate, Optional[_LocalMatch]]] = []
        local_failures: list[str] = []
        for candidate in candidates:
            local_match: Optional[_LocalMatch] = None
            local_error = None
            if str(fragment.get("source_span_kind") or "partial_span") == "partial_span":
                local_match, local_error = _locate_local_span(candidate, fragment)
                if local_error:
                    local_failures.append(local_error)
                    continue

            final_score = _final_candidate_score(
                fragment=fragment,
                candidate=candidate,
                local_match=local_match,
            )
            matches.append((final_score, candidate, local_match))

        if not matches:
            reason = "low_confidence"
            if local_failures and len(set(local_failures)) == 1:
                reason = local_failures[0]
            result["skipped"] += 1
            _append_issue(
                result,
                index=index,
                reason=reason,
                fragment=fragment,
            )
            _emit_runtime_log(
                log_parts,
                _build_writeback_detail_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="跳过",
                    fragment=fragment,
                    reason=reason,
                ),
                progress_logger,
            )
            continue

        matches.sort(key=lambda item: item[0], reverse=True)
        best_score, best_candidate, best_local_match = matches[0]
        threshold = _adaptive_threshold(fragment)
        if best_score < threshold:
            result["skipped"] += 1
            _append_issue(
                result,
                index=index,
                reason="low_confidence",
                fragment=fragment,
                score=best_score,
            )
            _emit_runtime_log(
                log_parts,
                _build_writeback_detail_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="跳过",
                    fragment=fragment,
                    reason="low_confidence",
                    score=best_score,
                    threshold=threshold,
                ),
                progress_logger,
            )
            continue

        if len(matches) > 1 and abs(best_score - matches[1][0]) < 0.05:
            result["skipped"] += 1
            _append_issue(
                result,
                index=index,
                reason="multiple_candidate_conflict",
                fragment=fragment,
                score=best_score,
            )
            _emit_runtime_log(
                log_parts,
                _build_writeback_detail_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="跳过",
                    fragment=fragment,
                    reason="multiple_candidate_conflict",
                    score=best_score,
                    threshold=threshold,
                ),
                progress_logger,
            )
            continue

        if str(fragment.get("source_span_kind") or "partial_span") == "full_container":
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
                    fragment=fragment,
                    score=best_score,
                )
                _emit_runtime_log(
                    log_parts,
                    _build_writeback_detail_log(
                        step_label=step_label,
                        index=index,
                        total=len(fragments),
                        status="跳过",
                        fragment=fragment,
                        reason="empty_target_span",
                        score=best_score,
                        threshold=threshold,
                    ),
                    progress_logger,
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
                    fragment=fragment,
                    score=best_score,
                )
                _emit_runtime_log(
                    log_parts,
                    _build_writeback_detail_log(
                        step_label=step_label,
                        index=index,
                        total=len(fragments),
                        status="跳过",
                        fragment=fragment,
                        reason="low_local_confidence",
                        score=best_score,
                        threshold=threshold,
                    ),
                    progress_logger,
                )
                continue
            actual_start = best_local_match.actual_start
            actual_end = best_local_match.actual_end

        if int(actual_end) <= int(actual_start):
            result["skipped"] += 1
            _append_issue(
                result,
                index=index,
                reason="empty_target_span",
                fragment=fragment,
                score=best_score,
            )
            _emit_runtime_log(
                log_parts,
                _build_writeback_detail_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="跳过",
                    fragment=fragment,
                    reason="empty_target_span",
                    score=best_score,
                    threshold=threshold,
                ),
                progress_logger,
            )
            continue

        try:
            target_range = doc.Range(int(actual_start), int(actual_end))
            _apply_fragment_style(target_range, fragment)
            result["applied"] += 1
            _increment_applied_style_counters(result["applied_by_style"], fragment)
            _emit_runtime_log(
                log_parts,
                _build_writeback_detail_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="成功",
                    fragment=fragment,
                    target_text=_resolve_target_text(fragment, best_candidate, best_local_match),
                    score=best_score,
                    threshold=threshold,
                ),
                progress_logger,
            )
        except Exception as exc:
            result["failed"] += 1
            issue: InlineStyleWritebackIssue = {
                "index": int(index),
                "reason": "apply_failed",
                "source_text": str(fragment.get("source_text") or "")[:120],
                "container_type": str(fragment.get("container_type") or "paragraph"),
                "container_locator": dict(fragment.get("container_locator") or {}),
                "score": round(float(best_score), 4),
                "error": str(exc),
            }
            result["issues"].append(issue)
            _emit_runtime_log(
                log_parts,
                _build_writeback_detail_log(
                    step_label=step_label,
                    index=index,
                    total=len(fragments),
                    status="失败",
                    fragment=fragment,
                    target_text=_resolve_target_text(fragment, best_candidate, best_local_match),
                    reason="apply_failed",
                    score=best_score,
                    threshold=threshold,
                    error=str(exc),
                ),
                progress_logger,
            )
            continue

    _emit_runtime_log(log_parts, summarize_style_writeback_result(result), progress_logger)
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
