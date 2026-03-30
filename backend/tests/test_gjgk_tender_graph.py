"""测试 GjgkTenderGraph 工作流图。"""

import inspect

from backend.graphs.gjgk_tender_graph import GjgkTenderGraph


def test_gjgk_graph_can_be_built():
    graph = GjgkTenderGraph()
    assert graph.compile() is not None


def test_gjgk_graph_exposes_replace_content_as_post_update_node():
    graph = GjgkTenderGraph()
    builder = graph.build_graph()

    assert "replace_content" in builder.nodes


def test_gjgk_graph_estimate_total_nodes_matches_standard_tracked_count():
    graph = GjgkTenderGraph()

    assert graph.estimate_total_nodes({"origin_tender_path": ""}) == 7
    assert graph.estimate_total_nodes({"origin_tender_path": "D:/origin.docx"}) == 10


def test_gjgk_graph_uses_unbound_functions_for_subgraph_and_post_update_steps():
    graph = GjgkTenderGraph()
    delete_step = graph.get_word_operation_steps()[0][1]
    replace_step = graph.get_post_update_steps()[0][1]

    assert not inspect.ismethod(delete_step)
    assert not inspect.ismethod(replace_step)
