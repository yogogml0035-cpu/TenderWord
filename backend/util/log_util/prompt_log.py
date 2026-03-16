from __future__ import annotations

from pathlib import Path


def get_generate_prompt_log_dir(anchor_file: str) -> Path:
    target = Path(anchor_file).resolve().parents[2] / "prompts_log" / "generate_log"
    target.mkdir(parents=True, exist_ok=True)
    return target


__all__ = ["get_generate_prompt_log_dir"]
