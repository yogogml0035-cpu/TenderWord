from __future__ import annotations

import importlib
from pathlib import Path

from backend.prompts.types import GeneratePromptInput, RenderedPrompt

node_module = importlib.import_module(
    "backend.nodes.common_word_nodes.generate_polished_text"
)


def test_generate_polished_text_uses_generate_prompt_and_stream_llm(
    monkeypatch, tmp_path: Path
) -> None:
    captured_prompt: dict[str, GeneratePromptInput] = {}
    captured_stream: dict[str, object] = {}
    snapshots: list[str] = []
    completions: list[str] = []

    def _fake_render_generate_prompt(data: GeneratePromptInput) -> RenderedPrompt:
        captured_prompt["data"] = data
        return RenderedPrompt(system_prompt="system prompt", user_prompt="user prompt")

    async def _fake_stream_llm_completion(**kwargs):
        captured_stream.update(kwargs)
        callbacks = kwargs["callbacks"]
        callbacks.on_update("stream snapshot")
        return "final polished text"

    monkeypatch.setattr(
        node_module,
        "render_generate_prompt",
        _fake_render_generate_prompt,
    )
    monkeypatch.setattr(
        node_module,
        "stream_llm_completion",
        _fake_stream_llm_completion,
    )
    monkeypatch.setattr(
        node_module,
        "get_generate_context_log_dir",
        lambda _anchor_file: tmp_path,
    )

    result = node_module.generate_polished_text(
        {
            "tender_type": "xjcg",
            "generation_style": "param",
            "project_content": "project info",
            "tender_params": "new tender params",
            "template_reference_text": "template shell",
            "project_number": "P-001",
            "project_name": "Workflow Project",
        },
        {
            "configurable": {
                "model_provider": "qwen",
                "llm_stream_callback": snapshots.append,
                "llm_stream_complete_callback": completions.append,
                "suppress_llm_stdout": True,
            }
        },
    )

    assert captured_prompt["data"] == GeneratePromptInput(
        tender_type="xjcg",
        generation_style="param",
        project_info="project info",
        tender_params="new tender params",
        template_reference_text="template shell",
    )
    assert captured_stream["model_provider"] == "qwen"
    assert captured_stream["system_prompt"] == "system prompt"
    assert captured_stream["user_prompt"] == "user prompt"
    assert captured_stream["check_interval"] == 3.0
    assert snapshots == ["stream snapshot"]
    assert completions == ["final polished text"]
    assert result["polished_text"] == "final polished text"
    assert result["generate_polished_done"] is True
