from langgraph.graph import END, START, StateGraph

from backend.graphs.skill_graph import (
    REWRITE_END_NODE,
    REWRITE_NODE_HANDLERS,
    REWRITE_NODE_NAMES,
    REWRITE_START_NODE,
    RewriteSkillGraph,
)
from backend.skills import get_skill_guide
from backend.skills.rewrite.scripts.runtime import select_resolve_branch
from backend.states import TaskSkillGraphState


def test_rewrite_skill_guide_exposes_runtime_instruction() -> None:
    rewrite = get_skill_guide("rewrite")

    assert rewrite.name == "rewrite"
    assert "create_rewrite_task_tool" in rewrite.instruction
    assert "上传文件" in rewrite.instruction


def test_rewrite_skill_graph_compiles_from_direct_workflow_registry() -> None:
    assert REWRITE_START_NODE == "resolve_rewrite_target"
    assert REWRITE_END_NODE == "update_word"
    assert RewriteSkillGraph().compile() is not None


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


def test_uploaded_rewrite_workflow_deletes_section_once_after_rewrite_text(monkeypatch) -> None:
    visited_nodes: list[str] = []

    def make_node(node_name: str):
        def node(_state: TaskSkillGraphState, _config=None) -> TaskSkillGraphState:
            visited_nodes.append(node_name)
            return TaskSkillGraphState()

        return node

    monkeypatch.setattr(
        "backend.graphs.skill_graph.REWRITE_NODE_HANDLERS",
        {node_name: make_node(node_name) for node_name in REWRITE_NODE_NAMES},
    )

    RewriteSkillGraph().compile().invoke(
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
