from backend.graphs.skill_graph import SkillGraph
from backend.graphs.task_skill_workflows import get_task_skill_workflow
from backend.skills import get_skill_guide


def test_rewrite_skill_guide_exposes_runtime_instruction() -> None:
    rewrite = get_skill_guide("rewrite")

    assert rewrite.name == "rewrite"
    assert "create_rewrite_task_tool" in rewrite.instruction
    assert "rewrite history" in rewrite.instruction


def test_rewrite_skill_graph_compiles_from_direct_workflow_registry() -> None:
    workflow = get_task_skill_workflow("rewrite")

    assert workflow.start_node == "resolve_rewrite_target"
    assert workflow.end_node == "update_word"
    assert SkillGraph.for_skill("rewrite")().compile() is not None


def test_edit_skill_guide_exposes_runtime_instruction() -> None:
    edit = get_skill_guide("edit")

    assert edit.name == "edit"
    assert "create_edit_task_tool" in edit.instruction
    assert "请先上传要修改的 Word 文件" in edit.instruction


def test_edit_skill_graph_compiles_from_direct_workflow_registry() -> None:
    workflow = get_task_skill_workflow("edit")

    assert workflow.start_node == "resolve_edit_target"
    assert workflow.end_node == "update_word"
    assert SkillGraph.for_skill("edit")().compile() is not None
