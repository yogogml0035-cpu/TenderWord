from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import re


FIELD_LABELS = (
    "问题类别",
    "原始条款",
    "核心问题",
    "评标风险点",
    "正确批注要点",
    "依据",
    "示例批注",
)


@dataclass(frozen=True)
class BadCase:
    case_id: str
    title: str
    fields: dict[str, str]


@dataclass(frozen=True)
class BadCaseChunk:
    chunk_id: str
    case_id: str
    title: str
    field: str
    text: str
    metadata: dict[str, str]


def parse_bad_cases(raw_text: str) -> list[BadCase]:
    """Parse the markdown-like bad-case text into structured cases."""

    blocks = re.split(r"(?=案例编号：)", raw_text.strip())
    cases: list[BadCase] = []

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        lines = [line.rstrip() for line in block.splitlines()]
        first = lines[0].strip()
        match = re.match(r"案例编号：\s*(\d+)\s*(.*)", first)
        if not match:
            continue

        case_id = match.group(1).strip()
        title = match.group(2).strip()
        fields: dict[str, str] = {}
        current_label: str | None = None
        current_lines: list[str] = []

        def flush_current() -> None:
            nonlocal current_label, current_lines
            if current_label:
                fields[current_label] = "\n".join(current_lines).strip()
            current_label = None
            current_lines = []

        for line in lines[1:]:
            field_match = re.match(r"^([^：]+)：\s*(.*)$", line.strip())
            if field_match and field_match.group(1) in FIELD_LABELS:
                flush_current()
                current_label = field_match.group(1)
                current_lines = [field_match.group(2).strip()]
                continue
            if current_label:
                current_lines.append(line)

        flush_current()
        cases.append(BadCase(case_id=case_id, title=title, fields=fields))

    return cases


def build_bad_case_chunks(cases: Iterable[BadCase]) -> list[BadCaseChunk]:
    """Create retrieval chunks.

    Each case gets a full-context chunk plus section-level chunks. The full chunk
    keeps enough context for reranking and later annotation generation, while the
    section chunks improve keyword and vector recall for specific risks.
    """

    chunks: list[BadCaseChunk] = []
    for case in cases:
        normalized_case_id = f"case_{int(case.case_id):02d}"
        category = case.fields.get("问题类别", "")
        full_parts = [
            f"案例编号：{case.case_id} {case.title}",
            *[
                f"{label}：{case.fields[label]}"
                for label in FIELD_LABELS
                if case.fields.get(label)
            ],
        ]
        chunks.append(
            BadCaseChunk(
                chunk_id=f"{normalized_case_id}:full",
                case_id=case.case_id,
                title=case.title,
                field="完整案例",
                text="\n".join(full_parts),
                metadata={
                    "case_id": case.case_id,
                    "title": case.title,
                    "category": category,
                    "field": "完整案例",
                    "chunk_type": "case",
                },
            )
        )

        for label in FIELD_LABELS:
            content = case.fields.get(label, "").strip()
            if not content:
                continue
            text = "\n".join(
                [
                    f"案例编号：{case.case_id} {case.title}",
                    f"问题类别：{category}",
                    f"{label}：{content}",
                ]
            )
            chunks.append(
                BadCaseChunk(
                    chunk_id=f"{normalized_case_id}:{label}",
                    case_id=case.case_id,
                    title=case.title,
                    field=label,
                    text=text,
                    metadata={
                        "case_id": case.case_id,
                        "title": case.title,
                        "category": category,
                        "field": label,
                        "chunk_type": "field",
                    },
                )
            )

    return chunks

