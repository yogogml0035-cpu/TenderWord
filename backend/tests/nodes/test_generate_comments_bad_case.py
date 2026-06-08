from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace


generate_comments_module = importlib.import_module(
    "backend.nodes.common_word_nodes.generate_comments"
)


def _base_state() -> dict[str, object]:
    return {
        "tender_type": "gngk_hw_zc",
        "polished_text": "1、心率检测精度为12.5。",
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


def test_generate_comments_injects_bad_case_context_before_llm_call(
    tmp_path: Path,
    monkeypatch,
) -> None:
    retrieval_calls: list[str] = []
    llm_calls: list[dict[str, object]] = []

    def _fake_retrieve_bad_case_hits(polished_text: str):
        retrieval_calls.append(polished_text)
        return SimpleNamespace(warnings=[])

    def _fake_build_bad_case_prompt_context(_result):
        return [
            {
                "risk_type": "参数指纹",
                "risk_pattern": "精确小数参数可能形成供应商指向性",
                "recommended_comment_policy": "建议提示：改为合理区间。",
                "applicability_boundary": "适用于技术参数过细场景。",
                "anchor_policy": "锚定当前文本中的精确小数参数。",
                "case_id": "TW_COMMENT_SHOULD_NOT_APPEAR",
                "score": 0.99,
            }
        ]

    async def _fake_stream_llm_completion(**kwargs):
        llm_calls.append(kwargs)
        return "[]"

    monkeypatch.setattr(
        generate_comments_module, "get_generate_prompt_log_dir", lambda _anchor: tmp_path
    )
    monkeypatch.setattr(
        generate_comments_module,
        "retrieve_bad_case_hits",
        _fake_retrieve_bad_case_hits,
    )
    monkeypatch.setattr(
        generate_comments_module,
        "build_bad_case_prompt_context",
        _fake_build_bad_case_prompt_context,
    )
    monkeypatch.setattr(
        generate_comments_module, "stream_llm_completion", _fake_stream_llm_completion
    )

    result = generate_comments_module.generate_comments(_base_state(), _base_config())

    assert retrieval_calls == ["1、心率检测精度为12.5。"]
    assert len(llm_calls) == 1
    combined_prompt = f"{llm_calls[0]['system_prompt']}\n{llm_calls[0]['user_prompt']}"
    assert "可能包含【bad_case参考规则】" in combined_prompt
    assert "【bad_case参考规则】" in combined_prompt
    assert "精确小数参数可能形成供应商指向性" in combined_prompt
    assert "TW_COMMENT_SHOULD_NOT_APPEAR" not in combined_prompt
    assert "0.99" not in combined_prompt
    assert result["generated_comment_count"] == 0

    prompt_files = list(tmp_path.glob("*_comments_prompt_*.txt"))
    assert len(prompt_files) == 1
    saved_prompt = prompt_files[0].read_text(encoding="utf-8")
    assert saved_prompt == combined_prompt


def test_generate_comments_uses_base_prompt_when_bad_case_has_no_hits(
    tmp_path: Path,
    monkeypatch,
) -> None:
    llm_calls: list[dict[str, object]] = []

    async def _fake_stream_llm_completion(**kwargs):
        llm_calls.append(kwargs)
        return "[]"

    monkeypatch.setattr(
        generate_comments_module, "get_generate_prompt_log_dir", lambda _anchor: tmp_path
    )
    monkeypatch.setattr(
        generate_comments_module,
        "retrieve_bad_case_hits",
        lambda _polished_text: SimpleNamespace(warnings=[]),
    )
    monkeypatch.setattr(
        generate_comments_module,
        "build_bad_case_prompt_context",
        lambda _result: [],
    )
    monkeypatch.setattr(
        generate_comments_module, "stream_llm_completion", _fake_stream_llm_completion
    )

    result = generate_comments_module.generate_comments(_base_state(), _base_config())

    assert len(llm_calls) == 1
    combined_prompt = f"{llm_calls[0]['system_prompt']}\n{llm_calls[0]['user_prompt']}"
    assert "【bad_case参考规则】" not in combined_prompt
    assert result["generated_comment_count"] == 0


def test_generate_comments_warns_and_continues_when_bad_case_retrieval_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    llm_calls: list[dict[str, object]] = []
    warnings: list[str] = []

    async def _fake_stream_llm_completion(**kwargs):
        llm_calls.append(kwargs)
        return "[]"

    def _raise_retrieval_failure(_polished_text: str):
        raise RuntimeError("vector search unavailable")

    monkeypatch.setattr(
        generate_comments_module, "get_generate_prompt_log_dir", lambda _anchor: tmp_path
    )
    monkeypatch.setattr(
        generate_comments_module,
        "retrieve_bad_case_hits",
        _raise_retrieval_failure,
    )
    monkeypatch.setattr(
        generate_comments_module, "stream_llm_completion", _fake_stream_llm_completion
    )
    monkeypatch.setattr(
        generate_comments_module.progress_log,
        "warning",
        lambda message, *args, **kwargs: warnings.append(str(message)),
    )

    result = generate_comments_module.generate_comments(_base_state(), _base_config())

    assert len(llm_calls) == 1
    combined_prompt = f"{llm_calls[0]['system_prompt']}\n{llm_calls[0]['user_prompt']}"
    assert "【bad_case参考规则】" not in combined_prompt
    assert any("bad case 检索失败" in message for message in warnings)
    assert result["generated_comment_count"] == 0


def test_generate_comments_logs_retrieval_warnings_without_blocking_llm(
    tmp_path: Path,
    monkeypatch,
) -> None:
    llm_calls: list[dict[str, object]] = []
    warnings: list[str] = []

    async def _fake_stream_llm_completion(**kwargs):
        llm_calls.append(kwargs)
        return "[]"

    monkeypatch.setattr(
        generate_comments_module, "get_generate_prompt_log_dir", lambda _anchor: tmp_path
    )
    monkeypatch.setattr(
        generate_comments_module,
        "retrieve_bad_case_hits",
        lambda _polished_text: SimpleNamespace(warnings=["falling back to bm25_only"]),
    )
    monkeypatch.setattr(
        generate_comments_module,
        "build_bad_case_prompt_context",
        lambda _result: [],
    )
    monkeypatch.setattr(
        generate_comments_module, "stream_llm_completion", _fake_stream_llm_completion
    )
    monkeypatch.setattr(
        generate_comments_module.progress_log,
        "warning",
        lambda message, *args, **kwargs: warnings.append(str(message)),
    )

    result = generate_comments_module.generate_comments(_base_state(), _base_config())

    assert len(llm_calls) == 1
    assert any("falling back to bm25_only" in message for message in warnings)
    assert result["generated_comment_count"] == 0
