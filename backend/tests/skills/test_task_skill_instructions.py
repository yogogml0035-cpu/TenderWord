from pathlib import Path


def _load_instruction(skill_id: str) -> str:
    skill_file = Path(__file__).resolve().parents[2] / "skills" / skill_id / "SKILL.md"
    content = skill_file.read_text(encoding="utf-8")
    if content.startswith("---\n"):
        _, _, remainder = content.partition("\n---\n")
        return remainder
    return content


def test_rewrite_instruction_preserves_full_output_scope_and_uploaded_file_contract() -> None:
    rewrite_instruction = _load_instruction("rewrite")

    assert "create_rewrite_task_tool" in rewrite_instruction
    assert "rewrite history" in rewrite_instruction
    assert "上传 Word 文件" in rewrite_instruction
    assert "form_type" in rewrite_instruction
    assert "insertion_config" in rewrite_instruction
    assert "上传文件优先于会话 history" in rewrite_instruction
    assert "不要直接操作 Word COM" in rewrite_instruction
    assert "输出范围默认必须等于" in rewrite_instruction
    assert "不能理解为只输出该范围" in rewrite_instruction
    assert "不得省略、裁剪或用省略号代替未修改内容" in rewrite_instruction
    assert "只输出完整最终正文文本" in rewrite_instruction


def test_rewrite_skill_guide_does_not_restore_legacy_workflow_frontmatter() -> None:
    skill_file = Path(__file__).resolve().parents[2] / "skills" / "rewrite" / "SKILL.md"
    content = skill_file.read_text(encoding="utf-8")

    for legacy_key in (
        "executor_kind:",
        "dispatch_key:",
        "route_literal:",
        "workflow" "_entry:",
    ):
        assert legacy_key not in content
