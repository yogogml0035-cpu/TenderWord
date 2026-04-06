from __future__ import annotations

from backend.graphs.gjgk_tender_graph import GjgkTenderGraph


def test_gjgk_estimate_total_nodes_includes_comment_branch_when_origin_tender_exists() -> None:
    graph = GjgkTenderGraph()

    assert graph.estimate_total_nodes({"origin_tender_path": "D:/UploadFiles/review.docx"}) == 10


def test_gjgk_estimate_total_nodes_skips_comment_branch_without_origin_tender() -> None:
    graph = GjgkTenderGraph()

    assert graph.estimate_total_nodes({}) == 7
