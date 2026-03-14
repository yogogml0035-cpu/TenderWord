import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _make_package(name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__path__ = []
    return module


def _load_module(monkeypatch, module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_rewrite_graph_module(monkeypatch):
    for package_name in (
        "backend",
        "backend.graphs",
        "backend.nodes",
        "backend.nodes.skills_nodes",
        "backend.nodes.common_word_nodes",
        "langgraph",
    ):
        monkeypatch.setitem(sys.modules, package_name, _make_package(package_name))

    langgraph_graph_module = types.ModuleType("langgraph.graph")
    langgraph_graph_module.START = "__start__"
    langgraph_graph_module.END = "__end__"

    class StateGraphStub:
        def __init__(self, state_cls):
            self.state_cls = state_cls
            self.nodes = {}
            self.edges = set()
            self.waiting_edges = set()

        def add_node(self, node_name, node_func):
            self.nodes[node_name] = node_func
            return self

        def add_edge(self, start, end):
            if isinstance(start, (list, tuple, set)):
                self.waiting_edges.add((tuple(start), end))
            else:
                self.edges.add((start, end))
            return self

        def compile(self):
            return self

    langgraph_graph_module.StateGraph = StateGraphStub
    monkeypatch.setitem(sys.modules, "langgraph.graph", langgraph_graph_module)

    base_graph_module = types.ModuleType("backend.graphs.base_graph")

    class BaseGraphStub:
        def __init__(self):
            self._graph = None

        def wrap_node(self, node_name, node_func):
            return node_func

        def compile(self):
            if self._graph is None:
                self._graph = self.build_graph().compile()
            return self._graph

    base_graph_module.BaseGraph = BaseGraphStub
    monkeypatch.setitem(sys.modules, "backend.graphs.base_graph", base_graph_module)

    common_word_nodes_module = types.ModuleType("backend.nodes.common_word_nodes")
    common_word_nodes_module.delete_tender_param = object()
    common_word_nodes_module.get_rewrite_comments = object()
    common_word_nodes_module.update_word = object()
    monkeypatch.setitem(
        sys.modules,
        "backend.nodes.common_word_nodes",
        common_word_nodes_module,
    )

    rewrite_nodes_module = types.ModuleType("backend.nodes.skills_nodes.rewrite_nodes")
    rewrite_nodes_module.resolve_rewrite_target = object()
    rewrite_nodes_module.rewrite_text = object()
    monkeypatch.setitem(
        sys.modules,
        "backend.nodes.skills_nodes.rewrite_nodes",
        rewrite_nodes_module,
    )

    states_module = types.ModuleType("backend.states")
    states_module.RewriteGraphState = dict
    monkeypatch.setitem(sys.modules, "backend.states", states_module)

    return _load_module(
        monkeypatch,
        "backend.graphs.rewrite_graph",
        ROOT / "backend/graphs/rewrite_graph.py",
    )


def test_rewrite_graph_can_be_built(monkeypatch):
    rewrite_graph_module = _load_rewrite_graph_module(monkeypatch)
    graph = rewrite_graph_module.RewriteGraph()

    compiled_graph = graph.compile()

    assert compiled_graph is not None


def test_rewrite_graph_has_get_rewrite_comments_node(monkeypatch):
    rewrite_graph_module = _load_rewrite_graph_module(monkeypatch)
    graph = rewrite_graph_module.RewriteGraph()
    builder = graph.build_graph()

    assert "get_rewrite_comments" in builder.nodes


def test_rewrite_graph_orders_comment_extraction_before_delete_section(monkeypatch):
    rewrite_graph_module = _load_rewrite_graph_module(monkeypatch)
    builder = rewrite_graph_module.RewriteGraph().build_graph()

    assert ("resolve_rewrite_target", "get_rewrite_comments") in builder.edges
    assert ("get_rewrite_comments", "delete_section") in builder.edges
    assert ("resolve_rewrite_target", "delete_section") not in builder.edges


def test_rewrite_graph_keeps_parallel_join_and_updates_total_nodes(monkeypatch):
    rewrite_graph_module = _load_rewrite_graph_module(monkeypatch)
    graph = rewrite_graph_module.RewriteGraph()
    builder = graph.build_graph()

    assert graph.estimate_total_nodes({}) == 5
    assert ("resolve_rewrite_target", "rewrite_text") in builder.edges
    assert (("delete_section", "rewrite_text"), "update_word") in builder.waiting_edges


def test_rewrite_comment_progress_node_is_tracked_and_named():
    base_graph_source = (ROOT / "backend/graphs/base_graph.py").read_text(encoding="utf-8")
    task_queue_source = (ROOT / "backend/task/task_queue_manager.py").read_text(encoding="utf-8")

    assert '"get_rewrite_comments"' in base_graph_source
    assert 'GET_REWRITE_COMMENTS = "get_rewrite_comments"' in task_queue_source
    assert 'NodeName.GET_REWRITE_COMMENTS: "提取原批注"' in task_queue_source
