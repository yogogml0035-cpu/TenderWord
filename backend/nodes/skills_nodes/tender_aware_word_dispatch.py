from __future__ import annotations

from backend.nodes.common_word_nodes.delete_tender_param import delete_tender_param
from backend.nodes.common_word_nodes.update_word import update_word
from backend.nodes.gngk_word_nodes.gngk_fw_zc_delete_tender_param import (
    gngk_fw_zc_delete_tender_param,
)
from backend.nodes.gngk_word_nodes.gngk_fw_zc_update_word import (
    gngk_fw_zc_update_word,
)
from backend.nodes.gjgk_word_nodes.gjgk_delete_tender_param import (
    gjgk_delete_tender_param,
)
from backend.nodes.gjgk_word_nodes.gjgk_update_word import gjgk_update_word
from backend.states import TaskSkillGraphState


def _should_use_gjgk_route(state: TaskSkillGraphState) -> bool:
    return str(state.get("tender_type") or "").strip() == "gjgk"


def _should_use_gngk_fw_zc_route(state: TaskSkillGraphState) -> bool:
    return str(state.get("tender_type") or "").strip() == "gngk_fw_zc"


def dispatch_tender_aware_delete_section(
    state: TaskSkillGraphState,
    config,
) -> TaskSkillGraphState:
    if _should_use_gjgk_route(state):
        handler = gjgk_delete_tender_param
    elif _should_use_gngk_fw_zc_route(state):
        handler = gngk_fw_zc_delete_tender_param
    else:
        handler = delete_tender_param
    return TaskSkillGraphState(**handler(TaskSkillGraphState(**dict(state)), config))


def dispatch_tender_aware_update_word(
    state: TaskSkillGraphState,
    config,
) -> TaskSkillGraphState:
    if _should_use_gjgk_route(state):
        handler = gjgk_update_word
    elif _should_use_gngk_fw_zc_route(state):
        handler = gngk_fw_zc_update_word
    else:
        handler = update_word
    return TaskSkillGraphState(**handler(TaskSkillGraphState(**dict(state)), config))


__all__ = [
    "dispatch_tender_aware_delete_section",
    "dispatch_tender_aware_update_word",
]
