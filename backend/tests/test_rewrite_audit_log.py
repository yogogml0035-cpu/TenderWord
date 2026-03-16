from __future__ import annotations

import json
from pathlib import Path

import backend.nodes.common_word_nodes.generate_polished_text as generate_polished_text_module
import backend.nodes.skills_nodes.rewrite_nodes as rewrite_nodes_module
import backend.util.log_util.rewrite_audit_log as rewrite_audit_log_module
from backend.services.conversation_service import RewriteMessage
from backend.util.log_util.rewrite_audit_log import (
    REWRITE_STAGE_ROUTE_OR_REPLY,
    REWRITE_STAGE_TARGET_SELECTION,
    REWRITE_STAGE_TEXT,
    create_rewrite_audit_log,
    write_rewrite_audit_stage,
)


def _set_rewrite_log_root(monkeypatch, tmp_path: Path) -> Path:
    fake_module_path = tmp_path / "backend" / "util" / "log_util" / "rewrite_audit_log.py"
    fake_module_path.parent.mkdir(parents=True, exist_ok=True)
    fake_module_path.touch()
    monkeypatch.setattr(rewrite_audit_log_module, "__file__", str(fake_module_path))
    return tmp_path / "backend" / "prompts_log" / "rewrite_log"


def test_rewrite_audit_log_creates_and_updates_grouped_json(monkeypatch, tmp_path):
    audit_dir = _set_rewrite_log_root(monkeypatch, tmp_path)
    log_path = create_rewrite_audit_log("conv-1", now=1234567890.0)

    write_rewrite_audit_stage(
        log_path,
        REWRITE_STAGE_ROUTE_OR_REPLY,
        [{"role": "system", "content": "route"}],
    )
    write_rewrite_audit_stage(
        log_path,
        REWRITE_STAGE_TARGET_SELECTION,
        [{"role": "user", "content": "target"}],
    )
    write_rewrite_audit_stage(
        log_path,
        REWRITE_STAGE_ROUTE_OR_REPLY,
        [{"role": "system", "content": "route-updated"}],
    )

    payload = json.loads(Path(log_path).read_text(encoding="utf-8"))
    assert payload == {
        REWRITE_STAGE_ROUTE_OR_REPLY: [{"role": "system", "content": "route-updated"}],
        REWRITE_STAGE_TARGET_SELECTION: [{"role": "user", "content": "target"}],
    }
    assert Path(log_path).parent == audit_dir


def test_rewrite_audit_log_initializes_from_invalid_existing_json(monkeypatch, tmp_path):
    _set_rewrite_log_root(monkeypatch, tmp_path)
    target = tmp_path / "backend" / "prompts_log" / "rewrite_log" / "broken.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{broken", encoding="utf-8")

    write_rewrite_audit_stage(
        str(target),
        REWRITE_STAGE_TEXT,
        [{"role": "user", "content": "rewrite"}],
    )

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload == {
        REWRITE_STAGE_TEXT: [{"role": "user", "content": "rewrite"}],
    }


def test_create_rewrite_audit_log_avoids_filename_collision(monkeypatch, tmp_path):
    _set_rewrite_log_root(monkeypatch, tmp_path)

    first_path = create_rewrite_audit_log("conv-1", now=1234567890.0)
    second_path = create_rewrite_audit_log("conv-1", now=1234567890.0)

    assert first_path != second_path
    assert Path(first_path).is_file()
    assert Path(second_path).is_file()


def test_select_rewrite_target_index_writes_messages_to_existing_log(monkeypatch, tmp_path):
    _set_rewrite_log_root(monkeypatch, tmp_path)
    log_path = create_rewrite_audit_log("conv-2", now=1234567890.0)
    request_messages = [
        {"role": "system", "content": "pick a version"},
        {"role": "user", "content": "choose latest"},
    ]

    async def _fake_stream_llm_completion(*_args, callbacks=None, **_kwargs):
        if callbacks and callbacks.on_request_messages:
            callbacks.on_request_messages(request_messages)
        return "0"

    monkeypatch.setattr(
        rewrite_nodes_module,
        "stream_llm_completion",
        _fake_stream_llm_completion,
    )

    selected_index = rewrite_nodes_module._select_rewrite_target_index(
        "把上一版写正式",
        [
            RewriteMessage(
                role="assistant",
                content="rewrite_success",
                rewrite_state={
                    "tender_type": "xjcg",
                    "prepared_doc_path": "D:/rewrite.docx",
                    "polished_text": "第一版",
                },
            )
        ],
        {"configurable": {"model_provider": "deepseek", "rewrite_log_path": log_path}},
    )

    payload = json.loads(Path(log_path).read_text(encoding="utf-8"))
    assert selected_index == 0
    assert payload[REWRITE_STAGE_TARGET_SELECTION] == request_messages


def test_generate_polished_text_writes_rewrite_messages_to_existing_log(monkeypatch, tmp_path):
    _set_rewrite_log_root(monkeypatch, tmp_path)
    fake_node_path = (
        tmp_path / "backend" / "nodes" / "common_word_nodes" / "generate_polished_text.py"
    )
    fake_node_path.parent.mkdir(parents=True, exist_ok=True)
    fake_node_path.touch()
    monkeypatch.setattr(generate_polished_text_module, "__file__", str(fake_node_path))

    log_path = create_rewrite_audit_log("conv-3", now=1234567890.0)
    request_messages = [
        {"role": "system", "content": "rewrite-system"},
        {"role": "user", "content": "rewrite-user"},
    ]

    async def _fake_stream_llm_completion(*_args, callbacks=None, **_kwargs):
        if callbacks and callbacks.on_request_messages:
            callbacks.on_request_messages(request_messages)
        return "改写完成"

    monkeypatch.setattr(
        generate_polished_text_module,
        "stream_llm_completion",
        _fake_stream_llm_completion,
    )

    result = generate_polished_text_module.generate_polished_text(
        {
            "rewrite_mode": True,
            "rewrite_user_prompt": "请改写第三章",
            "rewrite_base_text": "原始正文",
        },
        {
            "configurable": {
                "model_provider": "deepseek",
                "rewrite_log_path": log_path,
            }
        },
    )

    payload = json.loads(Path(log_path).read_text(encoding="utf-8"))
    assert result["polished_text"] == "改写完成"
    assert payload[REWRITE_STAGE_TEXT] == request_messages
