import importlib
import sys
import types

import pytest

delete_tender_param_module = importlib.import_module(
    "backend.nodes.common_word_nodes.delete_tender_param"
)
anchor_utils_module = importlib.import_module("backend.util.word_util.anchor_utils")


class _FakeSelection:
    def __init__(self):
        self.Start = 20

    def GoTo(self, *_args, **_kwargs):
        self.Start = 20


class _FakeWord:
    def __init__(self):
        self.Selection = _FakeSelection()
        self.ScreenUpdating = True


class _FakeContent:
    End = 1000


class _FakeDocument:
    def __init__(self):
        self.Content = _FakeContent()


class _DeleteRangeCollection:
    Count = 0

    def __call__(self, _index):
        raise IndexError


class _DeleteRange:
    def __init__(self, doc, start, end):
        self._doc = doc
        self.Start = int(start)
        self.End = int(end)
        self.Tables = _DeleteRangeCollection()
        self.Paragraphs = _DeleteRangeCollection()

    def Delete(self):
        self._doc.delete_calls.append((self.Start, self.End))


class _DeleteFlowDocument:
    def __init__(self, content_end=1000):
        self.Content = type("Content", (), {"End": int(content_end)})()
        self.delete_calls = []

    def Range(self, start, end):
        return _DeleteRange(self, start, end)


class _CancelledQueue:
    @staticmethod
    def is_task_cancelled(_task_id: str) -> bool:
        return True


class _FakeTaskCancelledException(Exception):
    pass


class _RepairFields:
    Count = 0

    def __call__(self, _index):
        raise IndexError


class _RepairRange:
    def __init__(self, doc, start, end, text=""):
        self._doc = doc
        self.Start = start
        self.End = end
        self._text = text
        self.Locked = False
        self.Fields = _RepairFields()

    @property
    def Text(self):
        return self._doc._range_texts.get((self.Start, self.End), self._text)

    def InsertBefore(self, text):
        self._doc.insert_before_calls.append((self.Start, text))

    def InsertAfter(self, text):
        self._doc.insert_after_calls.append((self.Start, self.End, text))

    def InsertParagraphAfter(self):
        self._doc.insert_paragraph_after_calls.append((self.Start, self.End))

    def Delete(self):
        self._doc.delete_calls.append((self.Start, self.End))


class _RepairParagraph:
    def __init__(self, doc, start, end, text):
        self.Range = _RepairRange(doc, start, end, text)


class _RepairParagraphCollection:
    def __init__(self, paragraphs):
        self._paragraphs = list(paragraphs)
        self.Count = len(self._paragraphs)

    def __iter__(self):
        return iter(self._paragraphs)

    def __call__(self, index):
        return self._paragraphs[index - 1]


class _RepairDocument:
    def __init__(self, paragraphs, range_texts=None, content_end=1000):
        self._paragraphs = [_RepairParagraph(self, *paragraph) for paragraph in paragraphs]
        self._range_texts = dict(range_texts or {})
        self.insert_before_calls = []
        self.insert_after_calls = []
        self.insert_paragraph_after_calls = []
        self.delete_calls = []
        self.Content = type("Content", (), {"End": content_end})()

    @property
    def Paragraphs(self):
        return _RepairParagraphCollection(self._paragraphs)

    def Range(self, start, end):
        text = self._range_texts.get((start, end), "")
        for para in self._paragraphs:
            if para.Range.Start == start and para.Range.End == end:
                text = para.Range.Text
                break
        return _RepairRange(self, start, end, text)


class _AnchorFont:
    def __init__(self, name: str, size: float):
        self.Name = name
        self.Size = float(size)


class _AnchorRange:
    def __init__(
        self,
        text: str,
        start: int,
        end: int,
        page: int,
        font_name: str,
        font_size: float,
    ):
        self.Text = text
        self.Start = int(start)
        self.End = int(end)
        self._page = int(page)
        self.Font = _AnchorFont(font_name, font_size)

    def Information(self, _kind):
        return self._page


class _AnchorParagraph:
    def __init__(
        self,
        text: str,
        start: int,
        end: int,
        page: int,
        font_name: str,
        font_size: float,
    ):
        self.Range = _AnchorRange(text, start, end, page, font_name, font_size)


class _AnchorDocument:
    def __init__(self, paragraphs):
        self.Paragraphs = [_AnchorParagraph(*p) for p in paragraphs]
        self.Content = type("Content", (), {"End": 5000})()


class _FindFont:
    def __init__(self):
        self.Name = ""
        self.Size = 0.0


class _FindObject:
    def __init__(self, range_obj):
        self._range = range_obj
        self.Text = ""
        self.Forward = True
        self.Wrap = None
        self.MatchCase = False
        self.MatchWholeWord = False

    def ClearFormatting(self):
        return None

    def Execute(self):
        for match in self._range._matches:
            if str(match["text"]) != str(self.Text):
                continue
            if int(match["start"]) < int(self._range.Start):
                continue
            if int(match["start"]) >= int(self._range.End):
                continue
            self._range._current = match
            self._range.Start = int(match["start"])
            self._range.End = int(match["end"])
            self._range.Font.Name = str(match["font"])
            self._range.Font.Size = float(match["size"])
            return True
        return False


class _FindRange:
    def __init__(self, matches, doc_end: int):
        self._matches = list(matches)
        self._current = None
        self.Start = 0
        self.End = int(doc_end)
        self.Font = _FindFont()
        self.Find = _FindObject(self)

    def Information(self, _kind):
        return int(self._current["page"])

    def Collapse(self, _kind):
        if self._current is not None:
            self.Start = int(self._current["end"])


class _FindDocContent:
    def __init__(self, matches, doc_end: int = 5000):
        self._matches = list(matches)
        self.End = int(doc_end)

    @property
    def Duplicate(self):
        return _FindRange(self._matches, self.End)


def test_calculate_elapsed_seconds_uses_monotonic_values():
    elapsed = delete_tender_param_module._calculate_elapsed_seconds(10.0, 12.5)
    assert elapsed == pytest.approx(2.5)


def test_delete_tender_param_fail_fast_when_before_anchor_missing(monkeypatch):
    save_called = {"value": False}

    monkeypatch.setattr(
        delete_tender_param_module,
        "create_word_application",
        lambda **_kwargs: (_FakeWord(), False),
    )
    monkeypatch.setattr(
        delete_tender_param_module,
        "open_document_with_retry",
        lambda **_kwargs: _FakeDocument(),
    )
    monkeypatch.setattr(
        delete_tender_param_module,
        "unprotect_document",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        delete_tender_param_module,
        "find_anchor_range",
        lambda **_kwargs: (
            None,
            {"page": 3, "start": 100, "end": 110, "font": "宋体", "size": 18.0},
        ),
    )
    monkeypatch.setattr(
        delete_tender_param_module, "close_word_application", lambda **_kwargs: None
    )

    def mark_save(*_args, **_kwargs):
        save_called["value"] = True

    monkeypatch.setattr(delete_tender_param_module, "save_document_with_retry", mark_save)

    with pytest.raises(RuntimeError, match="未找到前置锚点"):
        delete_tender_param_module.delete_tender_param(
            {
                "prepared_doc_path": __file__,
                "insertion_before_text": "第三章 采购需求",
                "insertion_after_text": "第四章 响应文件有关格式",
                "tender_type": "xjcg",
            },
            config={},
        )

    assert save_called["value"] is False


def test_delete_tender_param_fail_fast_when_after_anchor_missing(monkeypatch):
    save_called = {"value": False}

    monkeypatch.setattr(
        delete_tender_param_module,
        "create_word_application",
        lambda **_kwargs: (_FakeWord(), False),
    )
    monkeypatch.setattr(
        delete_tender_param_module,
        "open_document_with_retry",
        lambda **_kwargs: _FakeDocument(),
    )
    monkeypatch.setattr(
        delete_tender_param_module,
        "unprotect_document",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        delete_tender_param_module,
        "find_anchor_range",
        lambda **_kwargs: (
            {"page": 1, "end": 10, "font": "宋体", "size": 18.0},
            None,
        ),
    )
    monkeypatch.setattr(
        delete_tender_param_module, "close_word_application", lambda **_kwargs: None
    )

    def mark_save(*_args, **_kwargs):
        save_called["value"] = True

    monkeypatch.setattr(delete_tender_param_module, "save_document_with_retry", mark_save)

    with pytest.raises(RuntimeError, match="未找到后置锚点"):
        delete_tender_param_module.delete_tender_param(
            {
                "prepared_doc_path": __file__,
                "insertion_before_text": "第三章 采购需求",
                "insertion_after_text": "第四章 响应文件有关格式",
                "tender_type": "xjcg",
            },
            config={},
        )

    assert save_called["value"] is False


def test_delete_tender_param_fail_fast_when_anchor_pages_invalid(monkeypatch):
    save_called = {"value": False}

    monkeypatch.setattr(
        delete_tender_param_module,
        "create_word_application",
        lambda **_kwargs: (_FakeWord(), False),
    )
    monkeypatch.setattr(
        delete_tender_param_module,
        "open_document_with_retry",
        lambda **_kwargs: _FakeDocument(),
    )
    monkeypatch.setattr(
        delete_tender_param_module,
        "unprotect_document",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        delete_tender_param_module,
        "find_anchor_range",
        lambda **_kwargs: (
            {"page": 2, "end": 10, "font": "宋体", "size": 18.0},
            {"page": 2, "start": 100, "end": 110, "font": "宋体", "size": 18.0},
        ),
    )
    monkeypatch.setattr(
        delete_tender_param_module, "close_word_application", lambda **_kwargs: None
    )

    def mark_save(*_args, **_kwargs):
        save_called["value"] = True

    monkeypatch.setattr(delete_tender_param_module, "save_document_with_retry", mark_save)

    with pytest.raises(RuntimeError, match="后置锚点页码不大于前置锚点页码"):
        delete_tender_param_module.delete_tender_param(
            {
                "prepared_doc_path": __file__,
                "insertion_before_text": "第三章 采购需求",
                "insertion_after_text": "第四章 响应文件有关格式",
                "tender_type": "xjcg",
            },
            config={},
        )

    assert save_called["value"] is False


def test_delete_tender_param_checks_cancellation_inside_long_loop(monkeypatch):
    save_called = {"value": False}

    monkeypatch.setattr(
        delete_tender_param_module,
        "create_word_application",
        lambda **_kwargs: (_FakeWord(), False),
    )
    monkeypatch.setattr(
        delete_tender_param_module,
        "open_document_with_retry",
        lambda **_kwargs: _FakeDocument(),
    )
    monkeypatch.setattr(
        delete_tender_param_module,
        "unprotect_document",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        delete_tender_param_module,
        "find_anchor_range",
        lambda **_kwargs: (
            {"page": 1, "end": 10, "font": "宋体", "size": 18.0},
            {"page": 3, "start": 100, "end": 110, "font": "宋体", "size": 18.0},
        ),
    )
    monkeypatch.setattr(
        delete_tender_param_module, "close_word_application", lambda **_kwargs: None
    )
    monkeypatch.setitem(
        sys.modules,
        "backend.graphs.base_graph",
        types.SimpleNamespace(TaskCancelledException=_FakeTaskCancelledException),
    )
    monkeypatch.setitem(
        sys.modules,
        "backend.task.task_queue_manager",
        types.SimpleNamespace(get_task_queue=lambda: _CancelledQueue()),
    )

    def mark_save(*_args, **_kwargs):
        save_called["value"] = True

    monkeypatch.setattr(delete_tender_param_module, "save_document_with_retry", mark_save)

    with pytest.raises(_FakeTaskCancelledException):
        delete_tender_param_module.delete_tender_param(
            {
                "prepared_doc_path": __file__,
                "insertion_before_text": "第三章 采购需求",
                "insertion_after_text": "第四章 响应文件有关格式",
                "tender_type": "xjcg",
            },
            config={"configurable": {"task_id": "task-1"}},
        )

    assert save_called["value"] is False


def test_find_anchor_fast_uses_find_execute_variants_and_format():
    doc_content = _FindDocContent(
        [
            {
                "text": "第四章响应文件有关格式",
                "start": 120,
                "end": 138,
                "page": 2,
                "font": "Calibri",
                "size": 18.0,
            },
            {
                "text": "第四章响应文件有关格式",
                "start": 280,
                "end": 298,
                "page": 5,
                "font": "宋体",
                "size": 18.0,
            },
        ],
        doc_end=800,
    )

    hit = delete_tender_param_module._find_anchor_fast(
        doc_content,
        "第四章  响应文件有关格式",
        min_start=0,
        target_size=18.0,
    )

    assert hit == {"start": 280, "end": 298}


def test_restore_protected_field_paragraph_boundaries_inserts_break_before_delivery():
    doc = _RepairDocument(
        [
            (10, 20, "第三章 采购需求\r"),
            (100, 130, "    2、交付日期：自合同签订后 90 天\r"),
        ]
    )

    delete_tender_param_module._restore_protected_field_paragraph_boundaries(
        doc=doc,
        before_text="第三章 采购需求",
        before_end_pos=60,
        log=None,
    )

    assert doc.insert_before_calls == [(104, "\r")]
    assert doc.insert_paragraph_after_calls == []


def test_insert_paragraph_break_before_delivery_probes_for_safe_position(monkeypatch):
    doc = _RepairDocument([(100, 130, "    2、交付日期：自合同签订后 90 天\r")])
    delivery_para = doc.Paragraphs(1).Range

    monkeypatch.setattr(
        delete_tender_param_module,
        "_is_range_locked",
        lambda rng, _doc: int(rng.Start) in {104, 105},
    )

    inserted = delete_tender_param_module._insert_paragraph_break_before_delivery(
        doc,
        delivery_para,
        fallback_pos=60,
        tender_type="gngk",
        log=None,
    )

    assert inserted is True
    assert doc.insert_before_calls == [(106, "\r")]
    assert doc.insert_paragraph_after_calls == []


def test_insert_paragraph_break_before_delivery_falls_back_to_delete_start(monkeypatch):
    doc = _RepairDocument([(100, 130, "    2、交付日期：自合同签订后 90 天\r")])
    delivery_para = doc.Paragraphs(1).Range

    monkeypatch.setattr(
        delete_tender_param_module,
        "_is_range_locked",
        lambda rng, _doc: 100 <= int(rng.Start) <= 124,
    )

    inserted = delete_tender_param_module._insert_paragraph_break_before_delivery(
        doc,
        delivery_para,
        fallback_pos=60,
        tender_type="gngk",
        log=None,
    )

    assert inserted is True
    assert doc.insert_before_calls == []
    assert doc.insert_paragraph_after_calls == [(60, 60)]


def test_ensure_paragraph_break_after_payment_skips_locked_positions(monkeypatch):
    doc = _RepairDocument(
        [(140, 180, "4、付款方式：验收后 90 日付款\r")],
        range_texts={(180, 181): "X"},
        content_end=220,
    )
    payment_para = doc.Paragraphs(1).Range

    monkeypatch.setattr(
        delete_tender_param_module,
        "_is_range_locked",
        lambda rng, _doc: int(rng.Start) == 180,
    )

    inserted = delete_tender_param_module._ensure_paragraph_break_after_payment(
        doc, payment_para
    )

    assert inserted is True
    assert doc.insert_before_calls == [(181, "\r")]


def test_restore_protected_field_paragraph_boundaries_skips_missing_payment_field():
    doc = _RepairDocument(
        [
            (10, 20, "第三章 采购需求\r"),
            (100, 124, "2、交付日期：签订后 90 天\r"),
        ]
    )

    delete_tender_param_module._restore_protected_field_paragraph_boundaries(
        doc=doc,
        before_text="第三章 采购需求",
        before_end_pos=60,
        log=None,
    )

    assert doc.insert_before_calls == [(100, "\r")]
    assert doc.insert_paragraph_after_calls == []


def test_restore_protected_field_paragraph_boundaries_uses_delete_start_without_refind(
    monkeypatch,
):
    doc = _RepairDocument(
        [
            (10, 20, "第三章 采购需求\r"),
            (100, 130, "    2、交付日期：自合同签订后 90 天\r"),
        ]
    )

    monkeypatch.setattr(
        delete_tender_param_module,
        "_find_anchor_fast",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not refind")),
    )

    delete_tender_param_module._restore_protected_field_paragraph_boundaries(
        doc=doc,
        before_text="第三章 采购需求",
        before_end_pos=60,
        log=None,
    )

    assert doc.insert_before_calls == [(104, "\r")]


def test_find_paragraph_containing_any_respects_max_start():
    doc = _RepairDocument(
        [
            (10, 20, "第三章 采购需求\r"),
            (120, 140, "2、交付日期：签订后 90 天\r"),
            (260, 290, "4、付款方式：验收后付款\r"),
        ]
    )

    hit = delete_tender_param_module._find_paragraph_containing_any(
        doc,
        ("付款方式：",),
        min_start=60,
        max_start=200,
    )

    assert hit is None


@pytest.mark.parametrize("tender_type", ["xjcg", "gngk"])
def test_delete_tender_param_runs_layout_repair_and_save(monkeypatch, tender_type):
    word = _FakeWord()
    doc = _DeleteFlowDocument(content_end=1000)
    save_called = {"value": False}
    repair_calls = []
    after_hits = iter(
        [
            {"start": 100, "end": 110},
            {"start": 20, "end": 30},
        ]
    )

    monkeypatch.setattr(
        delete_tender_param_module,
        "create_word_application",
        lambda **_kwargs: (word, False),
    )
    monkeypatch.setattr(
        delete_tender_param_module,
        "open_document_with_retry",
        lambda **_kwargs: doc,
    )
    monkeypatch.setattr(
        delete_tender_param_module,
        "unprotect_document",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        delete_tender_param_module,
        "find_anchor_range",
        lambda **_kwargs: (
            {
                "page": 1,
                "end": 10,
                "font": "宋体",
                "size": 18.0 if tender_type == "xjcg" else 22.0,
                "used_text": "第三章 采购需求",
            },
            {
                "page": 3,
                "start": 100,
                "end": 110,
                "font": "宋体",
                "size": 18.0 if tender_type == "xjcg" else 22.0,
                "used_text": "第四章 响应文件有关格式",
            },
        ),
    )
    monkeypatch.setattr(
        delete_tender_param_module,
        "_find_anchor_fast",
        lambda *_args, **_kwargs: next(after_hits),
    )
    monkeypatch.setattr(
        delete_tender_param_module,
        "_restore_protected_field_paragraph_boundaries",
        lambda **kwargs: repair_calls.append(kwargs),
    )
    monkeypatch.setattr(
        delete_tender_param_module,
        "close_word_application",
        lambda **_kwargs: None,
    )

    def mark_save(*_args, **_kwargs):
        save_called["value"] = True

    monkeypatch.setattr(delete_tender_param_module, "save_document_with_retry", mark_save)

    result = delete_tender_param_module.delete_tender_param(
        {
            "prepared_doc_path": __file__,
            "insertion_before_text": "第三章 采购需求",
            "insertion_after_text": "第四章 响应文件有关格式",
            "tender_type": tender_type,
        },
        config={},
    )

    assert result["tender_type"] == tender_type
    assert doc.delete_calls == [(20, 100)]
    assert save_called["value"] is True
    assert len(repair_calls) == 1
    assert repair_calls[0]["tender_type"] == tender_type


def test_find_anchor_range_supports_master_variants_and_candidate_selection():
    doc = _AnchorDocument(
        [
            ("第三章采购需求\r", 20, 40, 1, "宋体", 18.0),
            ("第三章采购需求\r", 320, 340, 4, "宋体", 18.0),
            ("第三章采购需求\r", 520, 540, 7, "Calibri", 18.0),
            ("第四章响应文件有关格式\r", 460, 490, 5, "宋体", 18.0),
            ("第四章响应文件有关格式\r", 780, 810, 8, "宋体", 18.0),
            ("第四章响应文件有关格式\r", 900, 930, 9, "Calibri", 18.0),
        ]
    )

    before_hit, after_hit = anchor_utils_module.find_anchor_range(
        doc=doc,
        before_text="第三章  采购需求",
        after_text="第四章  响应文件有关格式",
        target_size=18.0,
        prefer_before="last",
        prefer_after="first",
    )

    assert before_hit is not None
    assert after_hit is not None
    assert before_hit["page"] == 4
    assert before_hit["used_text"] == "第三章采购需求"
    assert after_hit["page"] == 5
    assert after_hit["used_text"] == "第四章响应文件有关格式"


def test_find_anchor_range_falls_back_to_find_word_anchor(monkeypatch):
    calls = []

    class _DocWithoutParagraphs:
        Paragraphs = []
        Content = object()

    def _fake_find_word_anchor(doc_content, text, start_pos=0, target_size=18.0, fonts=None):
        calls.append((doc_content, text, int(start_pos), float(target_size)))
        if len(calls) == 1:
            return {
                "page": 2,
                "start": 100,
                "end": 160,
                "used_text": "第三章采购需求",
                "font": "宋体",
                "size": 18.0,
                "is_font": True,
                "is_size": True,
            }
        return {
            "page": 4,
            "start": 420,
            "end": 480,
            "used_text": "第四章响应文件有关格式",
            "font": "宋体",
            "size": 18.0,
            "is_font": True,
            "is_size": True,
        }

    monkeypatch.setattr(anchor_utils_module, "find_word_anchor", _fake_find_word_anchor)

    before_hit, after_hit = anchor_utils_module.find_anchor_range(
        doc=_DocWithoutParagraphs(),
        before_text="第三章  采购需求",
        after_text="第四章  响应文件有关格式",
        target_size=18.0,
    )

    assert before_hit is not None
    assert after_hit is not None
    assert calls[0][1:] == ("第三章  采购需求", 0, 18.0)
    assert calls[1][1:] == ("第四章  响应文件有关格式", 160, 18.0)


def test_find_word_anchor_uses_find_execute_with_variants_and_strict_format():
    doc_content = _FindDocContent(
        [
            {
                "text": "第四章响应文件有关格式",
                "start": 120,
                "end": 138,
                "page": 2,
                "font": "Calibri",
                "size": 18.0,
            },
            {
                "text": "第四章响应文件有关格式",
                "start": 280,
                "end": 298,
                "page": 5,
                "font": "宋体",
                "size": 18.0,
            },
        ],
        doc_end=800,
    )

    hit = anchor_utils_module.find_word_anchor(
        doc_content=doc_content,
        text="第四章  响应文件有关格式",
        start_pos=0,
        target_size=18.0,
    )

    assert hit is not None
    assert hit["start"] == 280
    assert hit["page"] == 5
    assert hit["used_text"] == "第四章响应文件有关格式"
