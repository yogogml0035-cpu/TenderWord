from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import re


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BAD_CASE_DIR = BACKEND_DIR / "retrieval" / "bad_cases"
DEFAULT_COMMENT_BAD_CASE_FILE = DEFAULT_BAD_CASE_DIR / "comment_bad_cases.md"

FIELD_LABELS = (
    "问题类别",
    "原始条款",
    "核心问题",
    "评标风险点",
    "正确批注要点",
    "依据",
    "示例批注",
)

V2_FIELD_LABELS = (
    "bad_case_id",
    "risk_layer",
    "risk_type",
    "risk_pattern",
    "comment_action",
    "evidence_strength",
    "source_signals",
    "trigger_signals",
    "keywords_for_retrieval",
    "typical_source_pattern",
    "bad_case_core",
    "recommended_comment_policy",
    "non_retain_reason",
    "applicability_boundary",
    "anchor_policy",
    "basis_hint",
)

V2_CHUNK_FIELD_LABELS = (
    "risk_pattern",
    "trigger_signals",
    "keywords_for_retrieval",
    "typical_source_pattern",
    "bad_case_core",
    "recommended_comment_policy",
    "applicability_boundary",
    "anchor_policy",
    "basis_hint",
)

V2_METADATA_LABELS = (
    "risk_layer",
    "risk_type",
    "risk_pattern",
    "comment_action",
    "evidence_strength",
    "recommended_comment_policy",
    "applicability_boundary",
    "anchor_policy",
)

V2_BLOCK_RE = re.compile(
    r"---BEGIN_BAD_CASE---\s*(.*?)\s*---END_BAD_CASE---",
    re.DOTALL,
)
V2_FIELD_RE = re.compile(r"^([a-z][a-z0-9_]*):\s*(.*)$")


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

    v2_cases = _parse_v2_bad_cases(raw_text)
    if v2_cases:
        return v2_cases
    return _parse_legacy_bad_cases(raw_text)


def _parse_v2_bad_cases(raw_text: str) -> list[BadCase]:
    cases: list[BadCase] = []
    for block_index, match in enumerate(V2_BLOCK_RE.finditer(raw_text)):
        block = match.group(1).strip()
        fields = _parse_v2_fields(block)
        case_id = fields.get("bad_case_id", f"unknown_{block_index:03d}")
        title = fields.get("risk_pattern", case_id)
        cases.append(BadCase(case_id=case_id, title=title, fields=fields))
    return cases


def _parse_v2_fields(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []

    def flush_field() -> None:
        nonlocal current_key, current_lines
        if current_key:
            fields[current_key] = "\n".join(current_lines).strip()
        current_key = None
        current_lines = []

    for raw_line in block.splitlines():
        line = raw_line.rstrip()
        field_match = V2_FIELD_RE.match(line)
        if field_match:
            flush_field()
            current_key = field_match.group(1)
            current_lines = [field_match.group(2).strip()]
            continue
        if current_key:
            current_lines.append(line)

    flush_field()
    return fields


def _parse_legacy_bad_cases(raw_text: str) -> list[BadCase]:
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
        if _is_v2_case(case):
            chunks.extend(_build_v2_bad_case_chunks(case))
            continue

        normalized_case_id = _chunk_case_prefix(case.case_id)
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


def load_bad_cases(path: str | Path | None = None) -> list[BadCase]:
    """Load bad cases from the formal comment bad-case knowledge file."""

    source_path = Path(path) if path is not None else DEFAULT_COMMENT_BAD_CASE_FILE
    return parse_bad_cases(source_path.read_text(encoding="utf-8"))


def load_bad_case_chunks(path: str | Path | None = None) -> list[BadCaseChunk]:
    """Load retrieval chunks from the formal comment bad-case knowledge file."""

    return build_bad_case_chunks(load_bad_cases(path))


def _is_v2_case(case: BadCase) -> bool:
    return any(label in case.fields for label in V2_FIELD_LABELS)


def _chunk_case_prefix(case_id: str) -> str:
    try:
        return f"case_{int(case_id):02d}"
    except ValueError:
        return case_id


def _build_v2_bad_case_chunks(case: BadCase) -> list[BadCaseChunk]:
    metadata_base = {
        "case_id": case.case_id,
        "title": case.title,
        **{
            label: case.fields.get(label, "")
            for label in V2_METADATA_LABELS
            if case.fields.get(label)
        },
    }
    full_text = "\n".join(
        f"{label}: {case.fields[label]}"
        for label in V2_FIELD_LABELS
        if case.fields.get(label)
    )
    chunks = [
        BadCaseChunk(
            chunk_id=f"{case.case_id}:full",
            case_id=case.case_id,
            title=case.title,
            field="full",
            text=full_text,
            metadata={
                **metadata_base,
                "field": "full",
                "chunk_type": "case",
            },
        )
    ]

    for label in V2_CHUNK_FIELD_LABELS:
        content = case.fields.get(label, "").strip()
        if not content:
            continue
        chunk_text = "\n".join(
            [
                f"bad_case_id: {case.case_id}",
                f"risk_layer: {case.fields.get('risk_layer', '')}",
                f"risk_type: {case.fields.get('risk_type', '')}",
                f"{label}: {content}",
            ]
        )
        chunks.append(
            BadCaseChunk(
                chunk_id=f"{case.case_id}:{label}",
                case_id=case.case_id,
                title=case.title,
                field=label,
                text=chunk_text,
                metadata={
                    **metadata_base,
                    "field": label,
                    "chunk_type": "field",
                },
            )
        )

    return chunks
