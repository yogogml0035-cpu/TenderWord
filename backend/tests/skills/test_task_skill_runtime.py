from langgraph.graph import END, START, StateGraph

from backend.graphs.skill_graph import SkillGraph
from backend.graphs.task_skill_workflows import get_task_skill_workflow
from backend.skills import get_skill_guide
from backend.skills.rewrite.scripts.runtime import select_resolve_branch
from backend.states import TaskSkillGraphState


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


def test_uploaded_rewrite_source_survives_task_skill_graph_state() -> None:
    observed_branches: list[str] = []

    def capture_branch(state: TaskSkillGraphState) -> TaskSkillGraphState:
        observed_branches.append(select_resolve_branch(state))
        return TaskSkillGraphState()

    builder = StateGraph(TaskSkillGraphState)
    builder.add_node("capture_branch", capture_branch)
    builder.add_edge(START, "capture_branch")
    builder.add_edge("capture_branch", END)

    builder.compile().invoke(
        {
            "conversation_id": "conv-1",
            "rewrite_user_prompt": "请修改已上传文件",
            "rewrite_source": "uploaded_file",
            "source_document_path": "D:/UploadFiles/source.docx",
        }
    )

    assert observed_branches == ["extract_rewrite_context"]


def test_uploaded_rewrite_workflow_deletes_section_once_after_rewrite_text() -> None:
    workflow = get_task_skill_workflow("rewrite")
    visited_nodes: list[str] = []

    def make_node(node_name: str):
        def node(_state: TaskSkillGraphState, _config=None) -> TaskSkillGraphState:
            visited_nodes.append(node_name)
            return TaskSkillGraphState()

        return node

    builder = StateGraph(workflow.state_cls)
    for workflow_node in workflow.nodes:
        builder.add_node(workflow_node.name, make_node(workflow_node.name))
    builder.add_edge(START, workflow.start_node)
    for start, end in workflow.edges:
        builder.add_edge(start, end)
    for starts, end in workflow.waiting_edges:
        builder.add_edge(list(starts), end)
    for conditional_edge in workflow.conditional_edges:
        builder.add_conditional_edges(
            conditional_edge.start,
            conditional_edge.condition,
            dict(conditional_edge.mapping),
        )
    builder.add_edge(workflow.end_node, END)

    builder.compile().invoke(
        {
            "conversation_id": "conv-1",
            "rewrite_user_prompt": "请修改已上传文件",
            "rewrite_source": "uploaded_file",
            "source_document_path": "D:/UploadFiles/source.docx",
        }
    )

    assert visited_nodes == [
        "resolve_rewrite_target",
        "extract_rewrite_context",
        "rewrite_text",
        "delete_section",
        "update_word",
    ]
