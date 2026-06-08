from __future__ import annotations

from dataclasses import asdict, dataclass
import logging
from pathlib import Path
from typing import Iterable
import re


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BAD_CASE_DIR = BACKEND_DIR / "retrieval" / "bad_cases"
DEFAULT_COMMENT_BAD_CASE_FILE = DEFAULT_BAD_CASE_DIR / "comment_bad_cases.md"
BAD_CASE_CONTEXT_AVAILABLE = "bad_case_context available"
BAD_CASE_CONTEXT_UNAVAILABLE = "bad_case_context unavailable"
LOGGER = logging.getLogger(__name__)

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


@dataclass(frozen=True)
class BadCaseSourceFile:
    file_name: str
    path: str
    case_count: int
    chunk_count: int


@dataclass(frozen=True)
class BadCaseLoadFailure:
    file_name: str
    path: str
    reason: str


@dataclass(frozen=True)
class BadCaseDirectoryLoadResult:
    cases: list[BadCase]
    chunks: list[BadCaseChunk]
    source_files: list[BadCaseSourceFile]
    failed_files: list[BadCaseLoadFailure]
    warnings: list[str]
    bad_case_context_status: str

    @property
    def available(self) -> bool:
        return self.bad_case_context_status != BAD_CASE_CONTEXT_UNAVAILABLE

    def to_log_payload(self) -> dict[str, object]:
        failed_files = [asdict(failure) for failure in self.failed_files]
        failure_summary: dict[str, object] | None = None
        if not self.available:
            failure_summary = {
                "status": BAD_CASE_CONTEXT_UNAVAILABLE,
                "reason": _summarize_unavailable_reason(self),
                "failed_files": failed_files,
            }

        return {
            "bad_case_context_status": self.bad_case_context_status,
            "source_files": [asdict(source_file) for source_file in self.source_files],
            "load_summary": {
                "successful_file_count": len(self.source_files),
                "failed_file_count": len(self.failed_files),
                "failed_files": failed_files,
            },
            "warnings": list(self.warnings),
            "failure_summary": failure_summary,
        }


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
    """Load bad cases from the formal directory, or from one explicit file."""

    source_path = Path(path) if path is not None else DEFAULT_BAD_CASE_DIR
    if source_path.is_dir() or path is None:
        return load_bad_case_directory(source_path).cases
    return parse_bad_cases(source_path.read_text(encoding="utf-8"))


def load_bad_case_chunks(path: str | Path | None = None) -> list[BadCaseChunk]:
    """Load retrieval chunks from the formal directory, or from one explicit file."""

    source_path = Path(path) if path is not None else DEFAULT_BAD_CASE_DIR
    if source_path.is_dir() or path is None:
        return load_bad_case_directory(source_path).chunks
    return build_bad_case_chunks(load_bad_cases(source_path))


def load_bad_case_directory(
    directory: str | Path | None = None,
) -> BadCaseDirectoryLoadResult:
    """Load all markdown bad-case files in a directory.

    Directory-level loading is intentionally soft-failing: malformed files are
    reported in the result and through warnings, while valid files remain usable.
    """

    source_dir = Path(directory) if directory is not None else DEFAULT_BAD_CASE_DIR
    warnings: list[str] = []
    failures: list[BadCaseLoadFailure] = []
    source_files: list[BadCaseSourceFile] = []
    all_cases: list[BadCase] = []
    all_chunks: list[BadCaseChunk] = []

    if not source_dir.exists():
        warning = f"bad case directory not found: {source_dir}"
        LOGGER.warning(warning)
        warnings.append(warning)
        return _build_directory_load_result(
            cases=[],
            chunks=[],
            source_files=[],
            failed_files=[],
            warnings=warnings,
        )

    if not source_dir.is_dir():
        warning = f"bad case path is not a directory: {source_dir}"
        LOGGER.warning(warning)
        warnings.append(warning)
        return _build_directory_load_result(
            cases=[],
            chunks=[],
            source_files=[],
            failed_files=[],
            warnings=warnings,
        )

    markdown_files = sorted(source_dir.glob("*.md"), key=lambda item: item.name)
    if not markdown_files:
        warning = f"bad case directory has no markdown files: {source_dir}"
        LOGGER.warning(warning)
        warnings.append(warning)
        return _build_directory_load_result(
            cases=[],
            chunks=[],
            source_files=[],
            failed_files=[],
            warnings=warnings,
        )

    for file_path in markdown_files:
        try:
            cases, chunks = _load_bad_case_file(file_path)
        except Exception as exc:  # noqa: BLE001 - runtime must skip bad files.
            reason = str(exc)
            warning = f"skipping bad case file {file_path.name}: {reason}"
            LOGGER.warning(warning)
            warnings.append(warning)
            failures.append(
                BadCaseLoadFailure(
                    file_name=file_path.name,
                    path=str(file_path),
                    reason=reason,
                )
            )
            continue

        all_cases.extend(cases)
        all_chunks.extend(chunks)
        source_files.append(
            BadCaseSourceFile(
                file_name=file_path.name,
                path=str(file_path),
                case_count=len(cases),
                chunk_count=len(chunks),
            )
        )

    return _build_directory_load_result(
        cases=all_cases,
        chunks=all_chunks,
        source_files=source_files,
        failed_files=failures,
        warnings=warnings,
    )


def _load_bad_case_file(path: Path) -> tuple[list[BadCase], list[BadCaseChunk]]:
    cases = parse_bad_cases(path.read_text(encoding="utf-8"))
    if not cases:
        raise ValueError("no bad cases parsed")
    chunks = build_bad_case_chunks(cases)
    if not chunks:
        raise ValueError("no bad case chunks built")
    return cases, chunks


def _build_directory_load_result(
    *,
    cases: list[BadCase],
    chunks: list[BadCaseChunk],
    source_files: list[BadCaseSourceFile],
    failed_files: list[BadCaseLoadFailure],
    warnings: list[str],
) -> BadCaseDirectoryLoadResult:
    return BadCaseDirectoryLoadResult(
        cases=cases,
        chunks=chunks,
        source_files=source_files,
        failed_files=failed_files,
        warnings=warnings,
        bad_case_context_status=(
            BAD_CASE_CONTEXT_AVAILABLE if chunks else BAD_CASE_CONTEXT_UNAVAILABLE
        ),
    )


def _summarize_unavailable_reason(result: BadCaseDirectoryLoadResult) -> str:
    if result.failed_files and not result.source_files:
        return "all bad case files failed to parse"
    if result.warnings:
        return result.warnings[0]
    return "bad case directory has no loadable markdown files"


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
