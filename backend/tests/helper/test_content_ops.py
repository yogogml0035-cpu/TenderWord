from __future__ import annotations

from backend.helper.word_helper.content_ops import resolve_following_insert_pos


def test_resolve_following_insert_pos_prefers_distinct_paragraph_boundary() -> None:
    calls: list[tuple[int, int, int]] = []

    def _fake_next(start: int, bound_end: int, *, max_lookahead: int = 0) -> int | None:
        calls.append((int(start), int(bound_end), int(max_lookahead)))
        return int(start)

    pos, prefer_distinct_paragraph = resolve_following_insert_pos(
        content_end=120,
        paragraph_end=136,
        bound_end=260,
        find_next_editable_pos_bounded=_fake_next,
    )

    assert pos == 136
    assert prefer_distinct_paragraph is True
    assert calls == [(136, 260, 20000)]


def test_resolve_following_insert_pos_falls_back_to_after_content_when_paragraph_boundary_missing() -> None:
    calls: list[int] = []

    def _fake_next(start: int, bound_end: int, *, max_lookahead: int = 0) -> int | None:
        calls.append(int(start))
        if int(start) == 136:
            return None
        return 124

    pos, prefer_distinct_paragraph = resolve_following_insert_pos(
        content_end=120,
        paragraph_end=136,
        bound_end=260,
        find_next_editable_pos_bounded=_fake_next,
    )

    assert pos == 124
    assert prefer_distinct_paragraph is False
    assert calls == [136, 121]


def test_resolve_following_insert_pos_uses_backward_fallback_when_forward_scan_is_blocked() -> None:
    def _fake_next(start: int, bound_end: int, *, max_lookahead: int = 0) -> int | None:
        return None

    def _fake_prev(start: int, *, max_lookback: int = 0) -> int | None:
        return 180

    pos, prefer_distinct_paragraph = resolve_following_insert_pos(
        content_end=120,
        paragraph_end=136,
        bound_end=260,
        find_next_editable_pos_bounded=_fake_next,
        find_prev_editable_pos=_fake_prev,
    )

    assert pos == 180
    assert prefer_distinct_paragraph is False
