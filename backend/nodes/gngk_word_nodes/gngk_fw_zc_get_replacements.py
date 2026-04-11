from __future__ import annotations

from backend.nodes.common_word_nodes.get_replacements_core import run_get_replacements
from backend.nodes.gngk_word_nodes.gngk_hw_zc_get_replacements import (
    GNGK_EXTRACTORS,
    GNGK_REPLACEMENT_FIELDS,
)
from backend.states import GngkTenderGraphState


def gngk_fw_zc_get_replacements(
    state: GngkTenderGraphState, config
) -> GngkTenderGraphState:
    """当前先复用 hw_zc replacement 规则，为 fw_zc 预留独立落点。"""
    return run_get_replacements(
        state=state,
        config=config,
        extractors=GNGK_EXTRACTORS,
        replacement_fields=GNGK_REPLACEMENT_FIELDS,
    )


__all__ = ["gngk_fw_zc_get_replacements"]
