from __future__ import annotations

import os

from dataclasses import dataclass, field, fields
from typing import Any, Dict

from langchain_core.runnables import RunnableConfig
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AgentConfig:
    """Runtime configuration for the tender document graph."""

    template_dir: str = field(
        default_factory=lambda: os.getenv("TENDER_TEMPLATE_DIR", "TenderFile")
    )
    llm_model: str = field(
        default_factory=lambda: os.getenv("TENDER_LLM_MODEL", "deepseek-chat")
    )
    llm_temperature: float = field(
        default_factory=lambda: float(os.getenv("TENDER_LLM_TEMPERATURE", "0.1"))
    )

    @classmethod
    def from_runnable_config(cls, config: RunnableConfig | None) -> "AgentConfig":
        base = cls()
        if not config:
            return base
        configurable: Dict[str, Any] = config.get("configurable", {})  # type: ignore[arg-type]
        if not configurable:
            return base
        valid_field_names = {f.name for f in fields(cls)}
        filtered = {
            key: value for key, value in configurable.items() if key in valid_field_names
        }
        return cls(**{**base.__dict__, **filtered})

    def resolve_template_path(self) -> str:
        return f"{self.template_dir}/{self.template_name}"
