import importlib

import pytest

from backend.graphs.base_graph import TaskCancelledException

delete_tender_param_module = importlib.import_module(
    "backend.nodes.common_word_nodes.delete_tender_param"
)


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


class _CancelledQueue:
    @staticmethod
    def is_task_cancelled(_task_id: str) -> bool:
        return True


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
    monkeypatch.setattr(delete_tender_param_module, "close_word_application", lambda **_kwargs: None)
    monkeypatch.setattr(
        "backend.task.task_queue_manager.get_task_queue",
        lambda: _CancelledQueue(),
    )

    def mark_save(*_args, **_kwargs):
        save_called["value"] = True

    monkeypatch.setattr(delete_tender_param_module, "save_document_with_retry", mark_save)

    with pytest.raises(TaskCancelledException):
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
