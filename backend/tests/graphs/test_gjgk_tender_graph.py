from __future__ import annotations

from backend.graphs.gjgk_tender_graph import GjgkTenderGraph


def test_gjgk_estimate_total_nodes_ignores_source_document_path() -> None:
    graph = GjgkTenderGraph()

    # prepare + extract + generate + annotate_corrections + generate_comments + update + word ops
    assert graph.estimate_total_nodes({"source_document_path": "D:/UploadFiles/review.docx"}) == 9


def test_gjgk_estimate_total_nodes_counts_workflow_comment_generation() -> None:
    graph = GjgkTenderGraph()

    assert graph.estimate_total_nodes({}) == 9
