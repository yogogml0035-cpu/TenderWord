from __future__ import annotations

import pytest
import backend.helper.word_helper.content_ops as content_ops_module

from backend.helper.word_helper.content_ops import (
    ensure_following_body_paragraph_insert_pos,
    resolve_following_insert_pos,
)


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


class _BoundEndRef:
    def __init__(self, value: int):
        self.value = int(value)


class _FakeParagraphRange:
    def __init__(self, end: int, text: str = ""):
        self.Start = 0
        self.End = int(end)
        self.Text = str(text or "")


class _FakeDoc:
    pass


class _FakeParagraphAccessor:
    def __init__(self, paragraph_range: _FakeParagraphRange):
        self._paragraph_range = paragraph_range

    def __call__(self, index: int):
        if index != 1:
            raise IndexError(index)
        return type("_FakeParagraph", (), {"Range": self._paragraph_range})()


class _FakeAnchorRange:
    def __init__(self, start: int, end: int, paragraph_range: _FakeParagraphRange):
        self.Start = int(start)
        self.End = int(end)
        self.Paragraphs = _FakeParagraphAccessor(paragraph_range)


def test_ensure_following_body_paragraph_insert_pos_creates_new_paragraph_when_gap_missing(
    monkeypatch,
) -> None:
    """
    付款方式典型场景：字段段末本就存在 \r（下一段是标题，不可写）。
    resolve_following_insert_pos 会返回 prefer_distinct_paragraph=True，
    但可写性校验不通过，因此走主动造段分支，helper 返回新拆段的可写落点。
    """
    bound_end_ref = _BoundEndRef(140)
    doc = _FakeDoc()
    paragraph_range = _FakeParagraphRange(140)
    anchor_range = _FakeAnchorRange(120, 128, paragraph_range)

    # resolve_following_insert_pos 会调用 find_next_editable_pos_bounded 返回“边界”，
    # 但随后 caller 用 is_writable_body_paragraph_pos 判定其不是可写正文段。
    def _fake_next(start: int, bound_end: int, *, max_lookahead: int = 0) -> int | None:
        return int(start)

    # 模拟：resolve 返回的位置（140）不是可写正文段；而 helper 造出来的位置（139）是。
    def _fake_is_writable(doc, pos: int) -> bool:
        return pos == 139

    def _fake_ensure_break(*args, **kwargs):
        del args, kwargs
        bound_end_ref.value = 148
        return True, 139

    monkeypatch.setattr(
        content_ops_module,
        "ensure_paragraph_break_after_paragraph",
        _fake_ensure_break,
    )
    monkeypatch.setattr(
        content_ops_module,
        "is_writable_body_paragraph_pos",
        _fake_is_writable,
    )

    pos, created_new_paragraph = ensure_following_body_paragraph_insert_pos(
        doc,
        anchor_range,
        bound_end=140,
        get_bound_end=lambda: bound_end_ref.value,
        find_next_editable_pos_bounded=_fake_next,
        find_prev_editable_pos=lambda start, *, max_lookback=0: None,
        field_label="付款方式",
    )

    assert pos == 139
    assert created_new_paragraph is True


def test_ensure_following_body_paragraph_insert_pos_reuses_existing_writable_paragraph(
    monkeypatch,
) -> None:
    """交付日期场景：resolve 已定位现成的可写正文段，无需造段。"""
    bound_end_ref = _BoundEndRef(200)
    doc = _FakeDoc()
    paragraph_range = _FakeParagraphRange(140)
    anchor_range = _FakeAnchorRange(120, 128, paragraph_range)

    def _fake_next(start: int, bound_end: int, *, max_lookahead: int = 0) -> int | None:
        return int(start)

    monkeypatch.setattr(
        content_ops_module,
        "is_writable_body_paragraph_pos",
        lambda doc, pos: True,
    )

    def _unexpected_ensure_break(*args, **kwargs):
        raise AssertionError("已有可写正文段时不应调用 helper 造段")

    monkeypatch.setattr(
        content_ops_module,
        "ensure_paragraph_break_after_paragraph",
        _unexpected_ensure_break,
    )

    pos, created_new_paragraph = ensure_following_body_paragraph_insert_pos(
        doc,
        anchor_range,
        bound_end=200,
        get_bound_end=lambda: bound_end_ref.value,
        find_next_editable_pos_bounded=_fake_next,
        find_prev_editable_pos=lambda start, *, max_lookback=0: None,
        field_label="交付日期",
    )

    assert pos == 140
    assert created_new_paragraph is False


def test_ensure_following_body_paragraph_insert_pos_fails_when_helper_cannot_create(
    monkeypatch,
) -> None:
    """
    helper 无法造段、且向后扫描也找不到任何可编辑位置时才 fail-fast。
    （软回车兜底始终被禁止。）
    """
    bound_end_ref = _BoundEndRef(140)
    doc = _FakeDoc()
    paragraph_range = _FakeParagraphRange(140)
    anchor_range = _FakeAnchorRange(120, 128, paragraph_range)

    monkeypatch.setattr(
        content_ops_module,
        "is_writable_body_paragraph_pos",
        lambda doc, pos: False,
    )
    monkeypatch.setattr(
        content_ops_module,
        "ensure_paragraph_break_after_paragraph",
        lambda *args, **kwargs: (False, None),
    )

    with pytest.raises(ValueError, match="创建正文段落失败"):
        ensure_following_body_paragraph_insert_pos(
            doc,
            anchor_range,
            bound_end=140,
            get_bound_end=lambda: bound_end_ref.value,
            find_next_editable_pos_bounded=lambda start, bound_end, *, max_lookahead=0: None,
            find_prev_editable_pos=lambda start, *, max_lookback=0: None,
            field_label="付款方式",
        )


def test_ensure_following_body_paragraph_insert_pos_falls_back_to_forward_scan_when_split_fails(
    monkeypatch,
) -> None:
    """
    gngk 模板典型场景：helper 无法在字段段内拆段（SDT 锁住 pilcrow 前），
    但向后扫描仍能找到可编辑位置。这种情况下应该走兜底，而不是报“未找到可写独立正文段”。
    """
    bound_end_ref = _BoundEndRef(260)
    doc = _FakeDoc()
    paragraph_range = _FakeParagraphRange(140)
    anchor_range = _FakeAnchorRange(120, 128, paragraph_range)

    monkeypatch.setattr(
        content_ops_module,
        "is_writable_body_paragraph_pos",
        lambda doc, pos: False,  # resolve 判不可写 → 走 create 分支。
    )
    monkeypatch.setattr(
        content_ops_module,
        "ensure_paragraph_break_after_paragraph",
        lambda *args, **kwargs: (False, None),  # helper 也拒绝造段。
    )

    def _forward_scan(start: int, bound_end: int, *, max_lookahead: int = 0) -> int | None:
        return 200  # 兜底扫描命中。

    pos, created_new_paragraph = ensure_following_body_paragraph_insert_pos(
        doc,
        anchor_range,
        bound_end=260,
        get_bound_end=lambda: bound_end_ref.value,
        find_next_editable_pos_bounded=_forward_scan,
        find_prev_editable_pos=lambda start, *, max_lookback=0: None,
        field_label="付款方式",
    )

    assert pos == 200
    assert created_new_paragraph is True
