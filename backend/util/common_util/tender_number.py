from __future__ import annotations

import re

_PREFIXED_PROJECT_NUMBER_PATTERN = re.compile(r"^\d+\s*-\s*([A-Za-z0-9]+)$")
_ALNUM_PROJECT_NUMBER_PATTERN = re.compile(r"^[A-Za-z0-9]+$")
_NUMERIC_TAIL_PATTERN = re.compile(r"(\d+)$")


def _compact_project_number(value: str | None) -> str:
    return re.sub(r"\s+", "", str(value or "").strip())


def extract_numeric_tail_project_number(value: str | None) -> str | None:
    normalized = _compact_project_number(value)
    if not normalized:
        return None

    match = _NUMERIC_TAIL_PATTERN.search(normalized)
    return match.group(1) if match else None


def strip_tender_number_prefix(value: str | None) -> str | None:
    normalized = _compact_project_number(value)
    if not normalized:
        return None

    prefixed_match = _PREFIXED_PROJECT_NUMBER_PATTERN.match(normalized)
    if prefixed_match:
        return prefixed_match.group(1)

    if _ALNUM_PROJECT_NUMBER_PATTERN.fullmatch(normalized):
        return normalized

    return None


def normalize_gjgk_project_number(
    project_number: str | None,
    tender_no: str | None = None,
) -> str:
    for candidate in (tender_no, project_number):
        normalized = strip_tender_number_prefix(candidate)
        if normalized:
            return normalized

    return _compact_project_number(project_number)
