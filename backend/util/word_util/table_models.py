from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, TypedDict


TABLE_PLACEHOLDER_RE = re.compile(r"^\s*\[\[TABLE:([A-Za-z0-9_-]+)\]\]\s*$")


class TableCellModel(TypedDict):
    row: int
    col: int
    row_span: int
    col_span: int
    text: str


class StructuredTableModel(TypedDict):
    table_id: str
    rows: int
    cols: int
    cells: list[TableCellModel]


def match_table_placeholder(line: str) -> str | None:
    match = TABLE_PLACEHOLDER_RE.match(str(line or ""))
    if match is None:
        return None
    return match.group(1)


def normalize_table_cell_model(cell: Mapping[str, Any]) -> TableCellModel:
    return TableCellModel(
        row=max(1, int(cell.get("row", 1) or 1)),
        col=max(1, int(cell.get("col", 1) or 1)),
        row_span=max(1, int(cell.get("row_span", 1) or 1)),
        col_span=max(1, int(cell.get("col_span", 1) or 1)),
        text=str(cell.get("text") or ""),
    )


def normalize_structured_table_model(
    model: Mapping[str, Any],
) -> StructuredTableModel | None:
    table_id = str(model.get("table_id") or "").strip()
    if not table_id:
        return None

    rows = max(1, int(model.get("rows", 1) or 1))
    cols = max(1, int(model.get("cols", 1) or 1))
    raw_cells = model.get("cells") or []
    if not isinstance(raw_cells, list):
        return None

    cells = [normalize_table_cell_model(cell) for cell in raw_cells]
    return StructuredTableModel(
        table_id=table_id,
        rows=rows,
        cols=cols,
        cells=cells,
    )


def build_structured_table_model_index(
    models: Iterable[Mapping[str, Any]] | None,
) -> dict[str, StructuredTableModel]:
    index: dict[str, StructuredTableModel] = {}
    if models is None:
        return index

    for raw_model in models:
        if not isinstance(raw_model, Mapping):
            continue
        model = normalize_structured_table_model(raw_model)
        if model is None:
            continue
        index[model["table_id"]] = model
    return index


def render_structured_table_grid(
    model: Mapping[str, Any],
    *,
    repeat_merged_text: bool = True,
) -> list[list[str]]:
    normalized = normalize_structured_table_model(model)
    if normalized is None:
        return []

    row_count = normalized["rows"]
    col_count = normalized["cols"]
    grid = [["" for _ in range(col_count)] for _ in range(row_count)]

    for cell in normalized["cells"]:
        row_start = cell["row"] - 1
        col_start = cell["col"] - 1
        row_end = min(row_count, row_start + cell["row_span"])
        col_end = min(col_count, col_start + cell["col_span"])
        for row_idx in range(row_start, row_end):
            for col_idx in range(col_start, col_end):
                if row_idx == row_start and col_idx == col_start:
                    grid[row_idx][col_idx] = cell["text"]
                elif repeat_merged_text:
                    grid[row_idx][col_idx] = cell["text"]

    return grid


def render_structured_table_markdown(
    model: Mapping[str, Any],
    *,
    repeat_merged_text: bool = True,
) -> str:
    rows = render_structured_table_grid(model, repeat_merged_text=repeat_merged_text)
    if not rows:
        return ""

    def _format_cell(value: str) -> str:
        text = str(value or "")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = text.replace("\n", "\\n")
        return text.replace("|", "\\|")

    header = rows[0]
    lines = [
        "| " + " | ".join(_format_cell(cell) for cell in header) + " |",
        "| " + " | ".join(["---"] * len(header)) + " |",
    ]
    for row in rows[1:]:
        padded = list(row[: len(header)])
        while len(padded) < len(header):
            padded.append("")
        lines.append("| " + " | ".join(_format_cell(cell) for cell in padded) + " |")
    return "\n".join(lines)


def render_structured_table_prompt_context(
    model: Mapping[str, Any],
    *,
    max_rows: int = 3,
    max_cell_chars: int = 40,
) -> str:
    rows = render_structured_table_grid(model, repeat_merged_text=False)
    if not rows:
        return ""

    context_lines: list[str] = []
    for row in rows:
        cells: list[str] = []
        for cell in row:
            text = str(cell or "").replace("\r\n", "\n").replace("\r", "\n").strip()
            if not text:
                continue
            text = " ".join(part for part in text.splitlines() if part.strip()).strip()
            if not text:
                continue
            if len(text) > max_cell_chars:
                text = text[: max_cell_chars - 3].rstrip() + "..."
            cells.append(text)
        if not cells:
            continue
        line = " / ".join(cells)
        if context_lines and context_lines[-1] == line:
            continue
        context_lines.append(line)
        if len(context_lines) >= max_rows:
            break
    return "\n".join(context_lines)


__all__ = [
    "StructuredTableModel",
    "TABLE_PLACEHOLDER_RE",
    "TableCellModel",
    "build_structured_table_model_index",
    "match_table_placeholder",
    "normalize_structured_table_model",
    "render_structured_table_grid",
    "render_structured_table_markdown",
    "render_structured_table_prompt_context",
]
