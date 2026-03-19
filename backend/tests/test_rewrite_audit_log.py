from __future__ import annotations

import json
from pathlib import Path

import backend.nodes.common_word_nodes.generate_polished_text as generate_polished_text_module
import backend.nodes.skills_nodes.rewrite_nodes as rewrite_nodes_module
import backend.util.log_util.rewrite_audit_log as rewrite_audit_log_module
from backend.skills.types import SkillDefinition
from backend.services.conversation_service import RewriteMessage
from backend.util.log_util.rewrite_audit_log import (
    REWRITE_STAGE_SKILL_DIRECTORY_ROUTE,
    REWRITE_STAGE_SKILL_PROMPT_RENDER,
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
        REWRITE_STAGE_SKILL_DIRECTORY_ROUTE,
        [{"role": "system", "content": "route"}],
    )
    write_rewrite_audit_stage(
        log_path,
        REWRITE_STAGE_SKILL_PROMPT_RENDER,
        [{"role": "user", "content": "skill render"}],
    )
    write_rewrite_audit_stage(
        log_path,
        REWRITE_STAGE_TARGET_SELECTION,
        [{"role": "user", "content": "target"}],
    )
    write_rewrite_audit_stage(
        log_path,
        REWRITE_STAGE_SKILL_DIRECTORY_ROUTE,
        [{"role": "system", "content": "route-updated"}],
    )

    payload = json.loads(Path(log_path).read_text(encoding="utf-8"))
    assert payload == {
        REWRITE_STAGE_SKILL_DIRECTORY_ROUTE: [{"role": "system", "content": "route-updated"}],
        REWRITE_STAGE_SKILL_PROMPT_RENDER: [{"role": "user", "content": "skill render"}],
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
    assert payload[REWRITE_STAGE_SKILL_PROMPT_RENDER] == [
        {
            "role": "system",
            "content": generate_polished_text_module.get_skill_registry()
            .get_definition("rewrite")
            .instruction,
        },
        {
            "role": "user",
            "content": "【当前文档内容】\n原始正文\n\n【技术参数参考资料】\n（无）\n\n【用户修改指令】\n请改写第三章",
        },
    ]
    assert payload[REWRITE_STAGE_TEXT] == request_messages


def test_generate_polished_text_writes_prompt_outputs_to_generate_log(monkeypatch, tmp_path):
    fake_node_path = (
        tmp_path / "backend" / "nodes" / "common_word_nodes" / "generate_polished_text.py"
    )
    fake_node_path.parent.mkdir(parents=True, exist_ok=True)
    fake_node_path.touch()
    monkeypatch.setattr(generate_polished_text_module, "__file__", str(fake_node_path))

    async def _fake_stream_llm_completion(*_args, **_kwargs):
        return "生成完成"

    monkeypatch.setattr(
        generate_polished_text_module,
        "stream_llm_completion",
        _fake_stream_llm_completion,
    )

    result = generate_polished_text_module.generate_polished_text(
        {
            "project_number": "260069",
            "project_name": "耳科及鼻科手术器械一批",
            "project_content": "项目概况",
        },
        {"configurable": {"model_provider": "deepseek"}},
    )

    generate_log_dir = tmp_path / "backend" / "prompts_log" / "generate_log"
    assert result["polished_text"] == "生成完成"
    assert generate_log_dir.is_dir()
    assert len(list(generate_log_dir.glob("prompt_*_polish_prompt_*.txt"))) == 1
    assert len(list(generate_log_dir.glob("prompt_*_polished_text_*.txt"))) == 1


def test_generate_polished_text_uses_rewrite_skill_instruction(monkeypatch):
    captured_prompt: dict[str, str] = {}

    class FakeSkillRegistry:
        def get_definition(self, skill_id: str) -> SkillDefinition:
            assert skill_id == "rewrite"
            return SkillDefinition(
                name="rewrite",
                description="desc",
                instruction="自定义 rewrite instruction",
                source_path="D:/fake/rewrite/SKILL.md",
            )

    async def _fake_stream_llm_completion(*_args, system_prompt, user_prompt, **_kwargs):
        captured_prompt["system_prompt"] = system_prompt
        captured_prompt["user_prompt"] = user_prompt
        return "改写完成"

    monkeypatch.setattr(
        generate_polished_text_module,
        "get_skill_registry",
        lambda: FakeSkillRegistry(),
    )
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
            "tender_params": "参考参数",
        },
        {"configurable": {"model_provider": "deepseek"}},
    )

    assert result["polished_text"] == "改写完成"
    assert captured_prompt["system_prompt"] == "自定义 rewrite instruction"
    assert "【当前文档内容】\n原始正文" in captured_prompt["user_prompt"]
    assert "【技术参数参考资料】\n参考参数" in captured_prompt["user_prompt"]
    assert "【用户修改指令】\n请改写第三章" in captured_prompt["user_prompt"]
