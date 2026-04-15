from __future__ import annotations

import importlib

from backend.config.tender_config import get_protected_field_profile

delete_module = importlib.import_module(
    "backend.nodes.common_word_nodes.delete_tender_param"
)


class _FakeDoc:
    Content = type("_FakeContent", (), {"End": 200})()


def test_restore_protected_field_paragraph_boundaries_uses_profile_marker_variants(
    monkeypatch,
) -> None:
    profile = get_protected_field_profile("xjcg")
    captured_texts: list[tuple[str, ...]] = []

    def fake_find(doc, texts, min_start=0, max_start=None):
        del doc, min_start, max_start
        captured_texts.append(tuple(texts))
        return None

    monkeypatch.setattr(delete_module, "_find_paragraph_containing_any", fake_find)
    monkeypatch.setattr(
        delete_module,
        "_insert_paragraph_break_before_delivery",
        lambda *args, **kwargs: False,
    )
    monkeypatch.setattr(
        delete_module,
        "_ensure_paragraph_break_after_payment",
        lambda *args, **kwargs: False,
    )

    delete_module._restore_protected_field_paragraph_boundaries(
        _FakeDoc(),
        before_text="第三章  采购需求",
        before_end_pos=10,
        log=None,
    )

    assert captured_texts == [
        (
            profile.ordered_markers[0],
            profile.ordered_markers[0].replace("：", ":"),
        ),
        (
            profile.ordered_markers[1],
            profile.ordered_markers[1].replace("：", ":"),
        ),
    ]
