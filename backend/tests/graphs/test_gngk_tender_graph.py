from __future__ import annotations

from backend.graphs.gngk_fw_zc_tender_graph import GngkFwZcTenderGraph
from backend.graphs.gngk_hw_zc_tender_graph import GngkHwZcTenderGraph
from backend.nodes.common_word_nodes import delete_tender_param, update_word
from backend.nodes.gngk_word_nodes import (
    gngk_fw_zc_delete_tender_param,
    gngk_fw_zc_get_replacements,
    gngk_fw_zc_update_word,
    gngk_hw_zc_get_replacements,
)


def test_gngk_hw_zc_graph_keeps_hw_specific_replacement_wrapper() -> None:
    assert GngkHwZcTenderGraph.NODE_DELETE_TENDER_PARAM is delete_tender_param
    assert GngkHwZcTenderGraph.NODE_GET_REPLACEMENTS is gngk_hw_zc_get_replacements
    assert GngkHwZcTenderGraph.NODE_UPDATE_WORD is update_word


def test_gngk_fw_zc_graph_overrides_service_specific_word_nodes() -> None:
    assert GngkFwZcTenderGraph.NODE_DELETE_TENDER_PARAM is gngk_fw_zc_delete_tender_param
    assert GngkFwZcTenderGraph.NODE_GET_REPLACEMENTS is gngk_fw_zc_get_replacements
    assert GngkFwZcTenderGraph.NODE_UPDATE_WORD is gngk_fw_zc_update_word
