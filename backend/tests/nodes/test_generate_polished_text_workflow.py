from __future__ import annotations

import importlib
from pathlib import Path

import pytest

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


def test_generate_polished_text_fails_when_table_placeholder_missing(
    monkeypatch, tmp_path: Path
) -> None:
    def _fake_render_generate_prompt(data: GeneratePromptInput) -> RenderedPrompt:
        return RenderedPrompt(system_prompt="system prompt", user_prompt="user prompt")

    async def _fake_stream_llm_completion(**kwargs):
        return "技术参数\n普通表格文本"

    monkeypatch.setattr(node_module, "render_generate_prompt", _fake_render_generate_prompt)
    monkeypatch.setattr(node_module, "stream_llm_completion", _fake_stream_llm_completion)
    monkeypatch.setattr(
        node_module,
        "get_generate_context_log_dir",
        lambda _anchor_file: tmp_path,
    )

    with pytest.raises(ValueError, match="TP1_5"):
        node_module.generate_polished_text(
            {
                "tender_type": "xjcg",
                "generation_style": "param",
                "project_content": "project info",
                "tender_params": "技术参数\n[[TABLE:TP1_5]]",
                "template_reference_text": "template shell",
            },
            {"configurable": {"model_provider": "qwen", "suppress_llm_stdout": True}},
        )


def test_generate_polished_text_fails_with_all_missing_table_ids(
    monkeypatch, tmp_path: Path
) -> None:
    def _fake_render_generate_prompt(data: GeneratePromptInput) -> RenderedPrompt:
        return RenderedPrompt(system_prompt="system prompt", user_prompt="user prompt")

    async def _fake_stream_llm_completion(**kwargs):
        return "技术参数\n[[TABLE:TP1_5]]"

    monkeypatch.setattr(node_module, "render_generate_prompt", _fake_render_generate_prompt)
    monkeypatch.setattr(node_module, "stream_llm_completion", _fake_stream_llm_completion)
    monkeypatch.setattr(
        node_module,
        "get_generate_context_log_dir",
        lambda _anchor_file: tmp_path,
    )

    with pytest.raises(ValueError, match="TP1_6"):
        node_module.generate_polished_text(
            {
                "tender_type": "xjcg",
                "generation_style": "param",
                "project_content": "project info",
                "tender_params": "技术参数\n[[TABLE:TP1_5]]\n[[TABLE:TP1_6]]",
                "template_reference_text": "template shell",
            },
            {"configurable": {"model_provider": "qwen", "suppress_llm_stdout": True}},
        )


def test_generate_polished_text_allows_non_table_tender_params(
    monkeypatch, tmp_path: Path
) -> None:
    def _fake_render_generate_prompt(data: GeneratePromptInput) -> RenderedPrompt:
        return RenderedPrompt(system_prompt="system prompt", user_prompt="user prompt")

    async def _fake_stream_llm_completion(**kwargs):
        return "普通技术参数正文"

    monkeypatch.setattr(node_module, "render_generate_prompt", _fake_render_generate_prompt)
    monkeypatch.setattr(node_module, "stream_llm_completion", _fake_stream_llm_completion)
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
            "tender_params": "普通技术参数",
            "template_reference_text": "template shell",
        },
        {"configurable": {"model_provider": "qwen", "suppress_llm_stdout": True}},
    )

    assert result["polished_text"] == "普通技术参数正文"


def test_generate_polished_text_allows_removed_table_section_when_context_absent(
    monkeypatch, tmp_path: Path
) -> None:
    def _fake_render_generate_prompt(data: GeneratePromptInput) -> RenderedPrompt:
        return RenderedPrompt(system_prompt="system prompt", user_prompt="user prompt")

    async def _fake_stream_llm_completion(**kwargs):
        return "正文仅保留其他章节，不再包含附件表单"

    monkeypatch.setattr(node_module, "render_generate_prompt", _fake_render_generate_prompt)
    monkeypatch.setattr(node_module, "stream_llm_completion", _fake_stream_llm_completion)
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
            "tender_params": "附件三：保洁耗材\n序号 / 名称 / 费用\n[[TABLE:TP1_5]]",
            "template_reference_text": "template shell",
        },
        {"configurable": {"model_provider": "qwen", "suppress_llm_stdout": True}},
    )

    assert result["polished_text"] == "正文仅保留其他章节，不再包含附件表单"


def test_generate_polished_text_still_fails_when_context_kept_but_placeholder_missing(
    monkeypatch, tmp_path: Path
) -> None:
    def _fake_render_generate_prompt(data: GeneratePromptInput) -> RenderedPrompt:
        return RenderedPrompt(system_prompt="system prompt", user_prompt="user prompt")

    async def _fake_stream_llm_completion(**kwargs):
        return "附件三：保洁耗材\n序号 / 名称 / 费用\n这里只剩普通文本"

    monkeypatch.setattr(node_module, "render_generate_prompt", _fake_render_generate_prompt)
    monkeypatch.setattr(node_module, "stream_llm_completion", _fake_stream_llm_completion)
    monkeypatch.setattr(
        node_module,
        "get_generate_context_log_dir",
        lambda _anchor_file: tmp_path,
    )

    with pytest.raises(ValueError, match="TP1_5"):
        node_module.generate_polished_text(
            {
                "tender_type": "xjcg",
                "generation_style": "param",
                "project_content": "project info",
                "tender_params": "附件三：保洁耗材\n序号 / 名称 / 费用\n[[TABLE:TP1_5]]",
                "template_reference_text": "template shell",
            },
            {"configurable": {"model_provider": "qwen", "suppress_llm_stdout": True}},
        )
