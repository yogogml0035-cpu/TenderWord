from pathlib import Path


def _load_instruction(skill_id: str) -> str:
    skill_file = Path(__file__).resolve().parents[2] / "skills" / skill_id / "SKILL.md"
    content = skill_file.read_text(encoding="utf-8")
    if content.startswith("---\n"):
        _, _, remainder = content.partition("\n---\n")
        return remainder
    return content


def test_rewrite_and_edit_instructions_preserve_full_output_scope() -> None:
    rewrite_instruction = _load_instruction("rewrite")

    assert "create_rewrite_task_tool" in rewrite_instruction
    assert "rewrite history" in rewrite_instruction
    assert "不要直接操作 Word COM" in rewrite_instruction

    edit_instruction = _load_instruction("edit")

    assert "输出范围默认必须等于" in edit_instruction
    assert "不能理解为只输出该范围" in edit_instruction
    assert "不得省略、裁剪或用省略号代替未修改内容" in edit_instruction
    assert "只输出完整最终正文文本" in edit_instruction
