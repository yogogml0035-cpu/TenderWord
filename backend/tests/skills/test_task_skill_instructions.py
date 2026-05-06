from pathlib import Path

from backend.skills.loader import load_skill_definitions


def _load_instruction(skill_id: str) -> str:
    skills_root = Path(__file__).resolve().parents[2] / "skills"
    definitions = {item.name: item for item in load_skill_definitions(skills_root)}
    return definitions[skill_id].instruction


def test_rewrite_and_edit_instructions_preserve_full_output_scope() -> None:
    for skill_id in ("rewrite", "edit"):
        instruction = _load_instruction(skill_id)

        assert "输出范围默认必须等于" in instruction
        assert "不能理解为只输出该范围" in instruction
        assert "不得省略、裁剪或用省略号代替未修改内容" in instruction
        assert "只输出完整最终正文文本" in instruction
