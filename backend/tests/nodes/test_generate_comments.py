from __future__ import annotations

import importlib
from pathlib import Path


generate_comments_module = importlib.import_module(
    "backend.nodes.common_word_nodes.generate_comments"
)


def _base_state() -> dict[str, object]:
    return {
        "tender_type": "gngk_hw_zc",
        "polished_text": "设备保修期3年。",
        "comment_plan_detail": [{"content": "LEGACY_COMMENT_PLAN_SHOULD_NOT_APPEAR"}],
        "strikethrough_plan": [{"content": "LEGACY_STRIKE_PLAN_SHOULD_NOT_APPEAR"}],
        "non_black_font_plan": [{"content": "LEGACY_FONT_PLAN_SHOULD_NOT_APPEAR"}],
        "project_number": "261127",
        "project_name": "便携式人体成分分析仪",
    }


def _base_config() -> dict[str, object]:
    return {
        "configurable": {
            "model_provider": "deepseek",
            "suppress_llm_stdout": True,
        }
    }


def test_generate_comments_parses_valid_json_once(tmp_path, monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    async def _fake_stream_llm_completion(**kwargs):
        calls.append(kwargs)
        return (
            '[{"reference_text": "设备保修期3年", '
            '"comment_text": "建议提示：建议补充量化指标。"}]'
        )

    monkeypatch.setattr(
        generate_comments_module, "get_generate_prompt_log_dir", lambda _anchor: tmp_path
    )
    monkeypatch.setattr(
        generate_comments_module, "stream_llm_completion", _fake_stream_llm_completion
    )

    result = generate_comments_module.generate_comments(_base_state(), _base_config())

    assert len(calls) == 1
    assert calls[0]["model_override"] is None
    assert calls[0]["extra_params_override"] == {"temperature": 1.3}
    combined_prompt = f"{calls[0]['system_prompt']}\n{calls[0]['user_prompt']}"
    assert "LEGACY_COMMENT_PLAN_SHOULD_NOT_APPEAR" not in combined_prompt
    assert "LEGACY_STRIKE_PLAN_SHOULD_NOT_APPEAR" not in combined_prompt
    assert "LEGACY_FONT_PLAN_SHOULD_NOT_APPEAR" not in combined_prompt
    assert "批注计划详情" not in combined_prompt
    assert "删除线计划" not in combined_prompt
    assert "非黑色字体计划" not in combined_prompt
    assert result["generated_comment_count"] == 1
    assert result["polished_comments"] == [
        {
            "reference_text": "设备保修期3年",
            "comment_text": "建议提示：建议补充量化指标。",
        }
    ]


def test_generate_comments_accepts_empty_json_array(tmp_path: Path, monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    async def _fake_stream_llm_completion(**kwargs):
        calls.append(kwargs)
        return "[]"

    monkeypatch.setattr(
        generate_comments_module, "get_generate_prompt_log_dir", lambda _anchor: tmp_path
    )
    monkeypatch.setattr(
        generate_comments_module, "stream_llm_completion", _fake_stream_llm_completion
    )

    result = generate_comments_module.generate_comments(_base_state(), _base_config())

    assert len(calls) == 1
    assert result["generated_comment_count"] == 0
    assert result["polished_comments"] == []


def test_generate_comments_repairs_invalid_escape_without_retry(
    tmp_path: Path, monkeypatch
) -> None:
    calls: list[dict[str, object]] = []

    async def _fake_stream_llm_completion(**kwargs):
        calls.append(kwargs)
        return (
            "```json\n"
            + r'[{"reference_text": "设备保修期3年", "comment_text": "建议提示：路径 C:\Temp 需人工复核。"}]'
            + "\n```"
        )

    monkeypatch.setattr(
        generate_comments_module, "get_generate_prompt_log_dir", lambda _anchor: tmp_path
    )
    monkeypatch.setattr(
        generate_comments_module, "stream_llm_completion", _fake_stream_llm_completion
    )

    result = generate_comments_module.generate_comments(_base_state(), _base_config())

    assert len(calls) == 1
    assert result["generated_comment_count"] == 1
    assert result["polished_comments"][0] == {
        "reference_text": "设备保修期3年",
        "comment_text": r"建议提示：路径 C:\Temp 需人工复核。",
    }


def test_generate_comments_retries_with_json_repair_prompt(
    tmp_path: Path, monkeypatch
) -> None:
    calls: list[dict[str, object]] = []

    async def _fake_stream_llm_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return '[{"reference_text": "设备保修期3年", "comment_text" "建议删除：主观表述。"}]'
        return (
            '[{"reference_text": "设备保修期3年", '
            '"comment_text": "建议删除：主观表述。"}]'
        )

    monkeypatch.setattr(
        generate_comments_module, "get_generate_prompt_log_dir", lambda _anchor: tmp_path
    )
    monkeypatch.setattr(
        generate_comments_module, "stream_llm_completion", _fake_stream_llm_completion
    )

    result = generate_comments_module.generate_comments(_base_state(), _base_config())

    assert len(calls) == 2
    assert "【原始输出】" in str(calls[1]["user_prompt"])
    assert result["generated_comment_count"] == 1
    assert result["polished_comments"] == [
        {
            "reference_text": "设备保修期3年",
            "comment_text": "建议删除：主观表述。",
        }
    ]
