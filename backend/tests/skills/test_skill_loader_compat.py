from backend.graphs.skill_graph import SkillGraph
from backend.skills.loader import load_skill_definitions


def test_rewrite_skill_loader_infers_task_runtime_defaults() -> None:
    definitions = {definition.name: definition for definition in load_skill_definitions()}

    rewrite = definitions["rewrite"]

    assert rewrite.executor_binding is not None
    assert rewrite.executor_binding.executor_kind == "task"
    assert rewrite.executor_binding.dispatch_key == "rewrite"
    assert rewrite.executor_binding.route_literal == "rewrite"
    assert rewrite.workflow_entry == "scripts.workflow:get_workflow"


def test_rewrite_skill_graph_compiles_without_legacy_frontmatter() -> None:
    graph = SkillGraph.for_skill("rewrite")()

    compiled_graph = graph.compile()

    assert compiled_graph is not None
