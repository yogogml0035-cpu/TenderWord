from __future__ import annotations

from backend.nodes.skills_nodes import tender_aware_word_dispatch
from backend.skills.edit.scripts.workflow import get_workflow as get_edit_workflow
from backend.skills.rewrite.scripts.workflow import get_workflow as get_rewrite_workflow


def test_dispatch_tender_aware_delete_section_routes_all_gjgk_variants(monkeypatch) -> None:
    called: list[str] = []

    monkeypatch.setattr(
        tender_aware_word_dispatch,
        "gjgk_delete_tender_param",
        lambda state, config: called.append(f"gjgk:{state.get('tender_lx')}") or {"route": "gjgk"},
    )
    monkeypatch.setattr(
        tender_aware_word_dispatch,
        "delete_tender_param",
        lambda state, config: called.append("common") or {"route": "common"},
    )

    result = tender_aware_word_dispatch.dispatch_tender_aware_delete_section(
        {"tender_type": "gjgk", "tender_lx": 1},
        config=None,
    )

    assert result["route"] == "gjgk"
    assert called == ["gjgk:1"]


def test_dispatch_tender_aware_delete_section_routes_gngk_fw_zc_to_service_handler(
    monkeypatch,
) -> None:
    called: list[str] = []

    monkeypatch.setattr(
        tender_aware_word_dispatch,
        "gngk_fw_zc_delete_tender_param",
        lambda state, config: called.append(str(state.get("tender_type")))
        or {"route": "gngk_fw_zc"},
    )
    monkeypatch.setattr(
        tender_aware_word_dispatch,
        "delete_tender_param",
        lambda state, config: called.append("common") or {"route": "common"},
    )

    result = tender_aware_word_dispatch.dispatch_tender_aware_delete_section(
        {"tender_type": "gngk_fw_zc"},
        config=None,
    )

    assert result["route"] == "gngk_fw_zc"
    assert called == ["gngk_fw_zc"]


def test_dispatch_tender_aware_update_word_falls_back_to_common_for_non_gjgk(monkeypatch) -> None:
    called: list[str] = []

    monkeypatch.setattr(
        tender_aware_word_dispatch,
        "gjgk_update_word",
        lambda state, config: called.append("gjgk") or {"route": "gjgk"},
    )
    monkeypatch.setattr(
        tender_aware_word_dispatch,
        "update_word",
        lambda state, config: called.append("common") or {"route": "common"},
    )

    result = tender_aware_word_dispatch.dispatch_tender_aware_update_word(
        {"tender_type": "xjcg"},
        config=None,
    )

    assert result["route"] == "common"
    assert called == ["common"]


def test_dispatch_tender_aware_update_word_routes_gngk_fw_zc_to_service_handler(
    monkeypatch,
) -> None:
    called: list[str] = []

    monkeypatch.setattr(
        tender_aware_word_dispatch,
        "gngk_fw_zc_update_word",
        lambda state, config: called.append(str(state.get("tender_type")))
        or {"route": "gngk_fw_zc"},
    )
    monkeypatch.setattr(
        tender_aware_word_dispatch,
        "update_word",
        lambda state, config: called.append("common") or {"route": "common"},
    )

    result = tender_aware_word_dispatch.dispatch_tender_aware_update_word(
        {"tender_type": "gngk_fw_zc"},
        config=None,
    )

    assert result["route"] == "gngk_fw_zc"
    assert called == ["gngk_fw_zc"]


def test_edit_workflow_keeps_public_node_names_and_uses_shared_dispatch_handlers() -> None:
    workflow = get_edit_workflow()
    node_map = {node.name: node.handler for node in workflow.nodes}

    assert workflow.start_node == "resolve_edit_target"
    assert workflow.end_node == "update_word"
    assert list(node_map) == [
        "resolve_edit_target",
        "extract_edit_context",
        "delete_section",
        "edit_text",
        "update_word",
    ]
    assert node_map["delete_section"] is tender_aware_word_dispatch.dispatch_tender_aware_delete_section
    assert node_map["update_word"] is tender_aware_word_dispatch.dispatch_tender_aware_update_word


def test_rewrite_workflow_keeps_public_node_names_and_uses_shared_dispatch_handlers() -> None:
    workflow = get_rewrite_workflow()
    node_map = {node.name: node.handler for node in workflow.nodes}

    assert workflow.start_node == "resolve_rewrite_target"
    assert workflow.end_node == "update_word"
    assert list(node_map) == [
        "resolve_rewrite_target",
        "get_rewrite_comments",
        "delete_section",
        "rewrite_text",
        "update_word",
    ]
    assert node_map["delete_section"] is tender_aware_word_dispatch.dispatch_tender_aware_delete_section
    assert node_map["update_word"] is tender_aware_word_dispatch.dispatch_tender_aware_update_word
