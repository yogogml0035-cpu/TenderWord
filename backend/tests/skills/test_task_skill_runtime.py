from backend.graphs.skill_graph import SkillGraph
from backend.graphs.task_skill_workflows import get_task_skill_workflow
from backend.skills import get_skill_guide


def test_rewrite_skill_guide_exposes_runtime_instruction() -> None:
    rewrite = get_skill_guide("rewrite")

    assert rewrite.name == "rewrite"
    assert "create_rewrite_task_tool" in rewrite.instruction
    assert "上传文件" in rewrite.instruction


def test_rewrite_skill_graph_compiles_from_direct_workflow_registry() -> None:
    workflow = get_task_skill_workflow("rewrite")

    assert workflow.start_node == "resolve_rewrite_target"
    assert workflow.end_node == "update_word"
    assert SkillGraph.for_skill("rewrite")().compile() is not None
