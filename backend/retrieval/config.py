from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):  # type: ignore[no-untyped-def]
        return False


BACKEND_DIR = Path(__file__).resolve().parents[1]
BACKEND_ENV_FILE = BACKEND_DIR / ".env"
DEFAULT_SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-large-zh-v1.5"


@dataclass(frozen=True)
class RetrievalConfig:
    qdrant_url: str
    qdrant_api_key: Optional[str]
    collection_name: str
    embedding_base_url: str
    embedding_api_key: str
    embedding_model: str
    embedding_dimensions: Optional[int]


def _optional_int(value: str | None) -> Optional[int]:
    value = str(value or "").strip()
    if not value:
        return None
    return int(value)


def _strip_wrapped_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _load_env_file_fallback(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = _strip_wrapped_value(value)


def load_retrieval_config(
    *,
    collection_name: str | None = None,
    qdrant_url: str | None = None,
) -> RetrievalConfig:
    """Load retrieval config from environment variables and backend/.env."""

    loaded = load_dotenv(BACKEND_ENV_FILE, override=False)
    if not loaded:
        _load_env_file_fallback(BACKEND_ENV_FILE)

    base_url = (
        os.getenv("EMBEDDING_BASE_URL")
        or os.getenv("SILICONFLOW_BASE_URL")
        or DEFAULT_SILICONFLOW_BASE_URL
    )
    api_key = (
        os.getenv("EMBEDDING_API_KEY")
        or os.getenv("DASHSCOPE_API_KEY")
        or ""
    )
    if not api_key.strip():
        raise RuntimeError(
            "Missing embedding API key. Set EMBEDDING_API_KEY."
        )

    return RetrievalConfig(
        qdrant_url=(qdrant_url or os.getenv("QDRANT_URL") or "http://127.0.0.1:6333").rstrip("/"),
        qdrant_api_key=os.getenv("QDRANT_API_KEY") or None,
        collection_name=(
            collection_name
            or os.getenv("COMMENT_BAD_CASE_COLLECTION")
            or "tenderword_comment_bad_cases_demo"
        ),
        embedding_base_url=base_url.rstrip("/"),
        embedding_api_key=api_key.strip(),
        embedding_model=os.getenv("EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL,
        embedding_dimensions=_optional_int(os.getenv("EMBEDDING_DIMENSIONS")),
    )
