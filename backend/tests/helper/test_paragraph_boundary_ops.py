from __future__ import annotations

import backend.helper.word_helper.paragraph_boundary_ops as boundary_ops


class _FakeAnchorRange:
    def __init__(self, end: int, *, start: int = 0, fail_insert_before: bool = False):
        self.Start = int(start)
        self.End = int(end)
        self.fail_insert_before = bool(fail_insert_before)
        self.insert_paragraph_before_calls = 0

    def InsertParagraphBefore(self) -> None:
        if self.fail_insert_before:
            raise RuntimeError("locked paragraph")
        self.insert_paragraph_before_calls += 1


class _FakeRange:
    def __init__(self, doc, start: int, end: int):
        self._doc = doc
        self.Start = int(start)
        self.End = int(end)

    @property
    def Text(self) -> str:
        return str(self._doc.range_texts.get((self.Start, self.End), ""))

    def InsertBefore(self, text: str) -> None:
        self._doc.insert_before_calls.append((self.Start, self.End, text))

    def InsertParagraphAfter(self) -> None:
        self._doc.insert_paragraph_after_calls.append((self.Start, self.End))


class _FakeDoc:
    def __init__(self, *, doc_end: int = 300, range_texts: dict[tuple[int, int], str] | None = None):
        self.Content = type("_FakeContent", (), {"End": int(doc_end)})()
        self.range_texts = dict(range_texts or {})
        self.insert_before_calls: list[tuple[int, int, str]] = []
        self.insert_paragraph_after_calls: list[tuple[int, int]] = []

    def Range(self, start: int, end: int):
        return _FakeRange(self, start, end)


class _FakeParagraphCollection:
    def __init__(self, paragraph_range):
        self._paragraph_range = paragraph_range

    def __call__(self, _index: int):
        return type("_FakeParagraph", (), {"Range": self._paragraph_range})()


class _FakeInnerRange:
    def __init__(self, full_paragraph_range):
        self.Start = int(full_paragraph_range.Start) + 2
        self.End = int(full_paragraph_range.End)
        self.Text = "交付日期：合同签订后30天"
        self.Paragraphs = _FakeParagraphCollection(full_paragraph_range)


def test_ensure_paragraph_break_after_paragraph_inserts_before_safe_slot(monkeypatch) -> None:
    """字段段末没有 \r（delete 场景）时，弱契约下补齐 \r 即视为成功。"""
    doc = _FakeDoc(range_texts={(128, 129): "二"})
    paragraph_range = _FakeAnchorRange(128, start=100)

    captured_field_names: list[str] = []

    def _fake_find_safe_insert_position(doc, candidates, **kwargs):
        del doc, candidates
        captured_field_names.append(str(kwargs.get("field_name") or ""))
        return 132

    monkeypatch.setattr(
        boundary_ops,
        "find_safe_insert_position",
        _fake_find_safe_insert_position,
    )

    def _unexpected_is_writable(*args, **kwargs):
        raise AssertionError("弱契约下不应调用可写性校验")

    monkeypatch.setattr(
        boundary_ops,
        "is_writable_body_paragraph_pos",
        _unexpected_is_writable,
    )

    inserted_break, boundary_pos = boundary_ops.ensure_paragraph_break_after_paragraph(
        doc,
        paragraph_range,
        scan_bound_end=200,
        tender_type="xjcg",
        field_name="付款方式",
    )

    assert inserted_break is True
    assert boundary_pos == 132
    assert captured_field_names == ["付款方式"]
    assert doc.insert_before_calls == [(132, 132, "\r")]


def test_ensure_paragraph_break_after_paragraph_reuses_existing_writable_boundary(
    monkeypatch,
) -> None:
    """字段段末已有 \r，弱契约下直接复用，不做任何写入、不做可写性校验。"""
    doc = _FakeDoc(range_texts={(128, 129): "\r"})
    paragraph_range = _FakeAnchorRange(128, start=100)

    def _unexpected_find_safe_insert_position(*args, **kwargs):
        raise AssertionError("已有段落边界时不应继续扫描可编辑位置")

    monkeypatch.setattr(
        boundary_ops,
        "find_safe_insert_position",
        _unexpected_find_safe_insert_position,
    )

    def _unexpected_is_writable(*args, **kwargs):
        raise AssertionError("弱契约下不应调用可写性校验")

    monkeypatch.setattr(
        boundary_ops,
        "is_writable_body_paragraph_pos",
        _unexpected_is_writable,
    )

    inserted_break, boundary_pos = boundary_ops.ensure_paragraph_break_after_paragraph(
        doc,
        paragraph_range,
        scan_bound_end=200,
        tender_type="xjcg",
        field_name="付款方式",
    )

    assert inserted_break is False
    assert boundary_pos == 128
    assert doc.insert_before_calls == []


def test_insert_paragraph_break_before_paragraph_does_not_scan_into_field_value(
    monkeypatch,
) -> None:
    doc = _FakeDoc()
    paragraph_range = _FakeAnchorRange(128, start=100, fail_insert_before=True)
    calls: list[tuple[list[int], int]] = []

    def _fake_find_safe_insert_position(doc, candidates, **kwargs):
        del doc
        candidate_list = [int(candidate) for candidate in candidates]
        max_forward = int(kwargs.get("max_forward_scan_chars") or 0)
        calls.append((candidate_list, max_forward))
        if candidate_list == [100, 100]:
            return None
        return 96

    monkeypatch.setattr(
        boundary_ops,
        "find_safe_insert_position",
        _fake_find_safe_insert_position,
    )

    restored = boundary_ops.insert_paragraph_break_before_paragraph(
        doc,
        paragraph_range,
        fallback_pos=96,
        tender_type="gngk_hw_zc",
        field_name="交付日期",
    )

    assert restored is True
    assert calls == [([100, 100], 0), ([96], 0)]
    assert paragraph_range.insert_paragraph_before_calls == 0
    assert doc.insert_before_calls == []
    assert doc.insert_paragraph_after_calls == [(96, 96)]


def test_insert_paragraph_break_before_paragraph_uses_paragraph_before_when_label_start_locked(
    monkeypatch,
) -> None:
    doc = _FakeDoc()
    paragraph_range = _FakeAnchorRange(128, start=100)
    calls: list[tuple[list[int], int]] = []

    def _fake_find_safe_insert_position(doc, candidates, **kwargs):
        del doc
        candidate_list = [int(candidate) for candidate in candidates]
        max_forward = int(kwargs.get("max_forward_scan_chars") or 0)
        calls.append((candidate_list, max_forward))
        return None

    monkeypatch.setattr(
        boundary_ops,
        "find_safe_insert_position",
        _fake_find_safe_insert_position,
    )

    restored = boundary_ops.insert_paragraph_break_before_paragraph(
        doc,
        paragraph_range,
        fallback_pos=96,
        tender_type="xjcg",
        field_name="交付日期",
    )

    assert restored is True
    assert calls == [([100, 100], 0)]
    assert paragraph_range.insert_paragraph_before_calls == 1
    assert doc.insert_before_calls == []
    assert doc.insert_paragraph_after_calls == []


def test_insert_paragraph_break_before_paragraph_uses_full_paragraph_for_split_range(
    monkeypatch,
) -> None:
    doc = _FakeDoc()
    full_paragraph_range = _FakeAnchorRange(128, start=100)
    inner_range = _FakeInnerRange(full_paragraph_range)
    calls: list[tuple[list[int], int]] = []

    def _fake_find_safe_insert_position(doc, candidates, **kwargs):
        del doc
        candidate_list = [int(candidate) for candidate in candidates]
        max_forward = int(kwargs.get("max_forward_scan_chars") or 0)
        calls.append((candidate_list, max_forward))
        return None

    monkeypatch.setattr(
        boundary_ops,
        "find_safe_insert_position",
        _fake_find_safe_insert_position,
    )

    restored = boundary_ops.insert_paragraph_break_before_paragraph(
        doc,
        inner_range,
        fallback_pos=96,
        tender_type="xjcg",
        field_name="交付日期",
    )

    assert restored is True
    assert calls == [([100, 100], 0)]
    assert full_paragraph_range.insert_paragraph_before_calls == 1


def test_ensure_paragraph_break_after_paragraph_splits_current_paragraph_when_next_is_heading(
    monkeypatch,
) -> None:
    """
    付款方式典型场景：字段段末已有 \r，但紧邻段是标题（不可写正文段）。
    只有 require_writable=True 时才会在字段段 pilcrow 之前拆段，
    返回新空正文段的可写落点。
    """
    doc = _FakeDoc(range_texts={(128, 129): "\r"})
    paragraph_range = _FakeAnchorRange(128, start=100)

    writable_queries: list[int] = []

    def _fake_is_writable(doc, pos: int) -> bool:
        writable_queries.append(int(pos))
        # 首次查询紧邻段 → 不可写（标题段）；
        # 拆段后再次查询 → 可写（新拆出的空正文段）。
        return len(writable_queries) > 1

    def _fake_is_range_locked(doc, rng) -> bool:
        return False

    monkeypatch.setattr(
        boundary_ops, "is_writable_body_paragraph_pos", _fake_is_writable
    )
    monkeypatch.setattr(boundary_ops, "is_range_locked", _fake_is_range_locked)

    inserted_break, boundary_pos = boundary_ops.ensure_paragraph_break_after_paragraph(
        doc,
        paragraph_range,
        scan_bound_end=200,
        tender_type="xjcg",
        field_name="付款方式",
        require_writable=True,
    )

    assert inserted_break is True
    # pilcrow 在 127（paragraph_end - 1），拆段后新段可写落点 = 128。
    assert boundary_pos == 128
    # 只应产生一次 InsertBefore("\r")，且是在 pilcrow 前。
    assert doc.insert_before_calls == [(127, 127, "\r")]


def test_ensure_paragraph_break_after_paragraph_weak_contract_does_not_split_when_next_is_heading(
    monkeypatch,
) -> None:
    """
    弱契约（pre-ensure / delete 等 caller）遇到“段末有 \r、下一段是标题”
    的场景时，应直接返回成功并复用已有边界，**不得**触发拆段动作——
    否则会在付款方式字段前后造出多余的空白正文段。
    """
    doc = _FakeDoc(range_texts={(128, 129): "\r"})
    paragraph_range = _FakeAnchorRange(128, start=100)

    monkeypatch.setattr(
        boundary_ops,
        "is_writable_body_paragraph_pos",
        lambda doc, pos: False,  # 即便下一段不可写，弱契约也不拆段。
    )

    inserted_break, boundary_pos = boundary_ops.ensure_paragraph_break_after_paragraph(
        doc,
        paragraph_range,
        scan_bound_end=200,
        tender_type="xjcg",
        field_name="付款方式",
    )

    assert inserted_break is False
    assert boundary_pos == 128
    # 关键：弱契约下不应触发任何 InsertBefore("\r")。
    assert doc.insert_before_calls == []
