from __future__ import annotations

from langchain_openai import ChatOpenAI

from backend.config.settings import settings
from backend.util.common_util import MODEL_CONFIGS, ensure_llm_env, get_llm_timeout_seconds


def create_generation_chat_model(model_provider: str) -> ChatOpenAI:
    provider = str(model_provider or "deepseek")
    model_config = MODEL_CONFIGS.get(provider, MODEL_CONFIGS["deepseek"])
    ensure_llm_env(provider)
    llm_config = settings.get_llm_config(provider)

    params = dict(model_config.extra_params)
    max_tokens = params.pop("max_tokens", None)
    temperature = params.pop("temperature", None)

    return ChatOpenAI(
        model=str(llm_config["model"]),
        api_key=llm_config["api_key"],
        base_url=str(llm_config["base_url"]),
        timeout=float(get_llm_timeout_seconds()),
        max_retries=0,
        max_tokens=max_tokens,
        temperature=temperature,
        model_kwargs=params,
        extra_body=dict(model_config.extra_body),
    )


__all__ = ["create_generation_chat_model"]
