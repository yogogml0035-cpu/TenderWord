from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from backend.config.settings import DEFAULT_DEEPSEEK_MODEL, Settings
from backend.services import chat_stream_service
from backend.util.common_util import llm_stream_utils


def test_deepseek_settings_default_uses_v4_flash() -> None:
    assert Settings.model_fields["DEEPSEEK_MODEL"].default == DEFAULT_DEEPSEEK_MODEL
    assert Settings().get_llm_config("deepseek")["model"] == DEFAULT_DEEPSEEK_MODEL


def test_deepseek_model_config_disables_thinking() -> None:
    assert llm_stream_utils.MODEL_CONFIGS["deepseek"].extra_body == {
        "thinking": {"type": "disabled"}
    }


def test_get_llm_timeout_seconds_uses_settings_by_default(monkeypatch):
    monkeypatch.setattr(llm_stream_utils.settings, "LLM_STREAM_TIMEOUT_SECONDS", 20)

    assert llm_stream_utils.get_llm_timeout_seconds() == 20
    assert llm_stream_utils.get_llm_timeout_seconds(7) == 7
    assert llm_stream_utils.get_llm_timeout_seconds(0) == 1


def test_stream_llm_completion_uses_configured_timeout_when_unspecified(monkeypatch):
    captured: dict[str, int] = {}

    monkeypatch.setattr(llm_stream_utils.settings, "LLM_STREAM_TIMEOUT_SECONDS", 20)
    monkeypatch.setattr(llm_stream_utils, "ensure_llm_env", lambda _provider: None)

    class _FakeHeartbeatMonitor:
        def __init__(self, model_name: str, timeout_seconds: int, check_interval: float):
            captured["heartbeat_timeout"] = timeout_seconds
            self.model_name = model_name

        def start(self) -> None:
            return None

        def stop(self) -> None:
            return None

    async def _fake_stream_openai_compatible(**kwargs):
        captured["stream_timeout"] = kwargs["timeout_seconds"]
        return "ok"

    monkeypatch.setattr(llm_stream_utils, "HeartbeatMonitor", _FakeHeartbeatMonitor)
    monkeypatch.setattr(
        llm_stream_utils,
        "_stream_openai_compatible",
        _fake_stream_openai_compatible,
    )

    result = asyncio.run(
        llm_stream_utils.stream_llm_completion(
            model_provider="deepseek",
            prompt="请生成内容",
        )
    )

    assert result == "ok"
    assert captured["heartbeat_timeout"] == 20
    assert captured["stream_timeout"] == 20


def test_stream_chat_response_uses_configured_timeout(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(chat_stream_service.settings, "LLM_STREAM_TIMEOUT_SECONDS", 20)
    monkeypatch.setattr(chat_stream_service.settings, "DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(
        chat_stream_service.settings,
        "DEEPSEEK_BASE_URL",
        "https://example.com",
    )
    monkeypatch.setattr(
        chat_stream_service.settings,
        "DEEPSEEK_MODEL",
        DEFAULT_DEEPSEEK_MODEL,
    )
    monkeypatch.setattr(chat_stream_service, "ensure_llm_env", lambda _provider: None)

    def _fake_timeout(timeout: float, connect: float):
        captured["timeout"] = timeout
        captured["connect_timeout"] = connect
        return SimpleNamespace(timeout=timeout, connect=connect)

    class _FakeCompletions:
        async def create(self, **kwargs):
            captured["create_params"] = kwargs

            async def _iterator():
                yield SimpleNamespace(
                    choices=[
                        SimpleNamespace(delta=SimpleNamespace(content="测试回复"))
                    ]
                )

            return _iterator()

    class _FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            captured["client_timeout"] = kwargs["timeout"]
            self.chat = SimpleNamespace(completions=_FakeCompletions())

    class _FakeRequest:
        async def is_disconnected(self) -> bool:
            return False

    async def _collect() -> list[dict[str, object]]:
        lines = [
            line
            async for line in chat_stream_service.stream_chat_response(
                _FakeRequest(),
                conversation_id="conv-1",
                model_provider="deepseek",
                normalized_messages=[{"role": "user", "content": "你好"}],
            )
        ]
        return [json.loads(line) for line in lines]

    monkeypatch.setattr(chat_stream_service.httpx, "Timeout", _fake_timeout)
    monkeypatch.setattr(chat_stream_service, "AsyncOpenAI", _FakeAsyncOpenAI)

    payloads = asyncio.run(_collect())

    assert captured["timeout"] == 20
    assert captured["connect_timeout"] == 10.0
    assert captured["create_params"]["model"] == DEFAULT_DEEPSEEK_MODEL
    assert captured["create_params"]["extra_body"] == {
        "thinking": {"type": "disabled"}
    }
    assert payloads[-1] == {"event": "done", "data": {"content": "测试回复"}}
