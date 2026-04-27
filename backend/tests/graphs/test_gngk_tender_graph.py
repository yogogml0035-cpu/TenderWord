from __future__ import annotations

import pytest

from backend.graphs.base_graph import StandardTenderWorkflowGraph
from backend.graphs.gjgk_tender_graph import GjgkTenderGraph
from backend.graphs.gngk_fw_cz_tender_graph import GngkFwCzTenderGraph
from backend.graphs.gngk_fw_zc_tender_graph import GngkFwZcTenderGraph
from backend.graphs.gngk_hw_cz_tender_graph import GngkHwCzTenderGraph
from backend.graphs.gngk_hw_zc_tender_graph import GngkHwZcTenderGraph
from backend.graphs.xjcg_tender_graph import XjcgTenderGraph
from backend.nodes.common_word_nodes import (
    delete_tender_param,
    extract_tender_params,
    update_word,
)
from backend.nodes.gjgk_word_nodes.gjgk_update_word import gjgk_update_word
from backend.nodes.gngk_word_nodes import (
    gngk_fw_zc_delete_tender_param,
    gngk_fw_zc_get_replacements,
    gngk_fw_zc_update_word,
    gngk_hw_zc_get_replacements,
)
from backend.services import document_service
from backend.states.base_state import TenderGraphStateBase


def test_gngk_hw_zc_graph_keeps_hw_specific_replacement_wrapper() -> None:
    assert GngkHwZcTenderGraph.NODE_DELETE_TENDER_PARAM is delete_tender_param
    assert GngkHwZcTenderGraph.NODE_GET_REPLACEMENTS is gngk_hw_zc_get_replacements
    assert GngkHwZcTenderGraph.NODE_UPDATE_WORD is update_word


def test_gngk_fw_zc_graph_overrides_service_specific_word_nodes() -> None:
    assert GngkFwZcTenderGraph.NODE_DELETE_TENDER_PARAM is gngk_fw_zc_delete_tender_param
    assert GngkFwZcTenderGraph.NODE_GET_REPLACEMENTS is gngk_fw_zc_get_replacements
    assert GngkFwZcTenderGraph.NODE_UPDATE_WORD is gngk_fw_zc_update_word


@pytest.mark.parametrize(
    ("form_type", "graph_cls", "expected_update"),
    [
        ("xjcg_tender", XjcgTenderGraph, update_word),
        ("gngk_hw_zc_tender", GngkHwZcTenderGraph, update_word),
        ("gngk_hw_cz_tender", GngkHwCzTenderGraph, update_word),
        ("gngk_fw_cz_tender", GngkFwCzTenderGraph, update_word),
        ("gngk_fw_zc_tender", GngkFwZcTenderGraph, gngk_fw_zc_update_word),
        ("gjgk_tender", GjgkTenderGraph, gjgk_update_word),
    ],
)
def test_generate_graph_registry_uses_shared_style_extract_and_expected_update_routes(
    form_type: str,
    graph_cls: type,
    expected_update,
) -> None:
    document_service._init_graph_registry()

    assert document_service.GRAPH_REGISTRY[form_type] is graph_cls
    assert graph_cls.NODE_EXTRACT_TENDER_PARAMS is extract_tender_params
    assert graph_cls.NODE_UPDATE_WORD is expected_update


def test_standard_generate_graph_preserves_inline_style_fragments_until_update() -> None:
    seen_by_update: dict[str, object] = {}

    def _identity_node(state, config=None):
        return {}

    def _extract_node(state, config=None):
        return {
            "origin_tender_params": "模板正文",
            "inline_style_fragments": [{"source_text": "模板样式"}],
            "start_page": 1,
            "end_page": 1,
        }

    def _generate_node(state, config=None):
        return {"polished_text": "生成正文"}

    def _update_node(state, config=None):
        seen_by_update["inline_style_fragments"] = state.get("inline_style_fragments")
        return {
            "style_writeback_result": {
                "extracted": len(state.get("inline_style_fragments") or []),
                "attempted": 0,
                "applied": 0,
                "skipped": 0,
                "failed": 0,
                "issues": [],
                "applied_by_style": {},
                "skipped_by_reason": {},
            },
            "style_writeback_summary": "样式摘要",
        }

    class _InlineStylePropagationGraph(StandardTenderWorkflowGraph):
        STATE_CLS = TenderGraphStateBase
        NODE_PREPARE_TEMPLATE = _identity_node
        NODE_GET_COMMENTS = _identity_node
        NODE_COPY_COMMENTS = _identity_node
        NODE_EXTRACT_TENDER_PARAMS = _extract_node
        NODE_DELETE_TENDER_PARAM = _identity_node
        NODE_GET_REPLACEMENTS = _identity_node
        NODE_REPLACE_CONTENT = _identity_node
        NODE_GENERATE_POLISHED_TEXT = _generate_node
        NODE_GENERATE_COMMENTS = _identity_node
        NODE_UPDATE_WORD = _update_node

    result = _InlineStylePropagationGraph().compile().invoke(
        {
            "origin_tender_path": "",
            "prepared_doc_path": "fake.docx",
            "insertion_before_text": "前锚点",
            "insertion_after_text": "后锚点",
        }
    )

    assert seen_by_update["inline_style_fragments"] == [{"source_text": "模板样式"}]
    assert result["inline_style_fragments"] == [{"source_text": "模板样式"}]
    assert result["style_writeback_summary"] == "样式摘要"
