from unittest.mock import sentinel, patch

import backend.nodes.gjgk_word_nodes.gjgk_get_replacements as gjgk_module
import backend.nodes.gngk_word_nodes.gngk_get_replacements as gngk_module
import backend.nodes.xjcg_word_nodes.xjcg_get_replacements as xjcg_module
from backend.states import (
    GjgkTenderGraphState,
    GngkTenderGraphState,
    XjcgTenderGraphState,
)


def test_xjcg_wrapper_delegates_to_shared_core():
    state = XjcgTenderGraphState()

    with patch.object(
        xjcg_module, "run_get_replacements", return_value=sentinel.result
    ) as mock_run:
        result = xjcg_module.xjcg_get_replacements(state, config={"k": "v"})

    assert result is sentinel.result
    mock_run.assert_called_once_with(
        state=state,
        config={"k": "v"},
        extractors=xjcg_module.XJCG_EXTRACTORS,
        replacement_fields=xjcg_module.XJCG_REPLACEMENT_FIELDS,
    )


def test_gngk_wrapper_delegates_to_shared_core():
    state = GngkTenderGraphState()

    with patch.object(
        gngk_module, "run_get_replacements", return_value=sentinel.result
    ) as mock_run:
        result = gngk_module.gngk_get_replacements(state, config={"k": "v"})

    assert result is sentinel.result
    mock_run.assert_called_once_with(
        state=state,
        config={"k": "v"},
        extractors=gngk_module.GNGK_EXTRACTORS,
        replacement_fields=gngk_module.GNGK_REPLACEMENT_FIELDS,
    )


def test_gjgk_wrapper_delegates_to_shared_core():
    state = GjgkTenderGraphState()

    with patch.object(
        gjgk_module, "run_get_replacements", return_value=sentinel.result
    ) as mock_run:
        result = gjgk_module.gjgk_get_replacements(state, config={"k": "v"})

    assert result is sentinel.result
    mock_run.assert_called_once_with(
        state=state,
        config={"k": "v"},
        extractors=gjgk_module.GJGK_EXTRACTORS,
        replacement_fields=gjgk_module.GJGK_REPLACEMENT_FIELDS,
    )
