from __future__ import annotations

import os

from backend.config.settings import Settings


def test_apply_langsmith_environment_exports_sdk_variables(monkeypatch) -> None:
    for key in (
        "LANGSMITH_TRACING",
        "LANGSMITH_ENDPOINT",
        "LANGSMITH_API_KEY",
        "LANGSMITH_PROJECT",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = Settings(
        LANGSMITH_TRACING="true",
        LANGSMITH_ENDPOINT="https://api.smith.langchain.com",
        LANGSMITH_API_KEY="test-key",
        LANGSMITH_PROJECT="DsAgent",
    )

    settings.apply_langsmith_environment()

    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_ENDPOINT"] == "https://api.smith.langchain.com"
    assert os.environ["LANGSMITH_API_KEY"] == "test-key"
    assert os.environ["LANGSMITH_PROJECT"] == "DsAgent"
