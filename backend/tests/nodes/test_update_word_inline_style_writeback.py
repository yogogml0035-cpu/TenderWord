from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any

import pytest


common_update_module = importlib.import_module("backend.nodes.common_word_nodes.update_word")
gngk_fw_zc_update_module = importlib.import_module(
    "backend.nodes.gngk_word_nodes.gngk_fw_zc_update_word"
)
gjgk_update_module = importlib.import_module("backend.nodes.gjgk_word_nodes.gjgk_update_word")


class _EmptyCollection:
    Count = 0

    def __iter__(self):
        return iter(())

    def __call__(self, _index: int):
        raise IndexError(_index)


class _FakeFont:
    def __init__(self) -> None:
        self.Name = ""
        self.Size = 0


class _FakeRange:
    def __init__(self, doc: "_FakeDoc", start: int, end: int, text: str = "") -> None:
        self.doc = doc
        self.Start = int(start)
        self.End = int(end)
        self.Text = text
        self.Font = _FakeFont()
        self.Tables = _EmptyCollection()
        self.Paragraphs = _EmptyCollection()
        self.Fields = _EmptyCollection()
        self.Locked = False

    @property
    def Duplicate(self) -> "_FakeRange":
        return _FakeRange(self.doc, self.Start, self.End, self.Text)

    def SetRange(self, start: int, end: int) -> None:
        self.Start = int(start)
        self.End = int(end)
        self.Text = self.doc.resolve_text(self.Start, self.End)

    def Collapse(self, *_args) -> None:
        self.End = self.Start
        self.Text = self.doc.resolve_text(self.Start, self.End)

    def Delete(self) -> None:
        if self.End == self.Start + 1:
            self.doc.inserted.pop(self.Start, None)
        self.Text = ""

    def InsertAfter(self, value: str) -> None:
        self.doc.inserted[int(self.End)] = str(value)

    def InsertBefore(self, value: str) -> None:
        self.doc.inserted[int(self.Start)] = str(value)

    def Information(self, *_args) -> int:
        return 0


class _FakeSelection:
    def __init__(self, doc: "_FakeDoc") -> None:
        self.doc = doc
        self.Start = 0
        self._page = 1
        self.Range = _FakeRange(doc, 0, 0)

    def GoTo(self, _what, _which, page: int) -> None:
        if int(page) <= 1:
            self.Start = 0
            self._page = 1
        else:
            self.Start = int(self.doc.Content.End)
            self._page = int(page)
        self.Range.SetRange(self.Start, self.Start)

    def Information(self, *_args) -> int:
        return self._page


class _FakeWord:
    def __init__(self, doc: "_FakeDoc") -> None:
        self.Selection = _FakeSelection(doc)


class _FakeDoc:
    def __init__(self) -> None:
        self.Content = SimpleNamespace(End=100)
        self.inserted: dict[int, str] = {}
        self.saved = False

    def resolve_text(self, start: int, end: int) -> str:
        if end == start + 1 and start in self.inserted:
            return self.inserted[start]
        if start == 20 and end == 80:
            return "采购需求正文"
        return ""

    def Range(self, start: int, end: int) -> _FakeRange:
        return _FakeRange(self, start, end, self.resolve_text(int(start), int(end)))

    def Save(self) -> None:
        self.saved = True


def _style_result() -> dict[str, Any]:
    return {
        "extracted": 1,
        "attempted": 1,
        "applied": 1,
        "skipped": 0,
        "failed": 0,
        "issues": [],
        "applied_by_style": {"bold": 1},
        "skipped_by_reason": {},
    }


def _patch_update_runtime(
    monkeypatch,
    module,
    fake_doc: _FakeDoc,
    fields: dict[str, _FakeRange],
    *,
    comment_result: dict[str, Any] | None = None,
) -> None:
    fake_word = _FakeWord(fake_doc)
    monkeypatch.setattr(
        module,
        "create_word_application",
        lambda **_kwargs: (fake_word, False),
    )
    monkeypatch.setattr(
        module,
        "open_document_with_retry",
        lambda **_kwargs: fake_doc,
    )
    monkeypatch.setattr(
        module,
        "unprotect_document",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        module,
        "find_anchor_range",
        lambda *_args, **_kwargs: (
            {"start": 10, "end": 20, "page": 1, "font": "宋体", "size": 12},
            {"start": 90, "end": 95, "page": 1, "font": "宋体", "size": 12},
        ),
    )
    monkeypatch.setattr(
        module,
        "resolve_anchor_content_range",
        lambda **_kwargs: {
            "range_start": 20,
            "range_end": 80,
            "start_page": 1,
            "end_page": 1,
        },
    )
    monkeypatch.setattr(
        module,
        "normalize_protected_field_paragraphs",
        lambda *args, **kwargs: 0,
    )
    monkeypatch.setattr(
        module,
        "collect_profile_protected_fields",
        lambda **_kwargs: fields,
    )
    monkeypatch.setattr(
        module,
        "refresh_profile_protected_fields",
        lambda **kwargs: kwargs["existing_fields"],
    )
    monkeypatch.setattr(
        module,
        "refind_protected_paragraph",
        lambda **kwargs: fields.get(kwargs["marker"]),
    )
    monkeypatch.setattr(
        module,
        "ensure_paragraph_break_after_paragraph",
        lambda *args, **kwargs: (False, None),
    )
    monkeypatch.setattr(module, "multi_pass_cleanup", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        module,
        "write_polished_comments",
        lambda **_kwargs: comment_result
        or {"added": 0, "failed": 0, "skipped": 0, "issues": []},
    )
    monkeypatch.setattr(module, "close_word_application", lambda **_kwargs: None)


def _patch_gjgk_update_runtime(
    monkeypatch,
    fake_doc: _FakeDoc,
) -> None:
    fake_word = _FakeWord(fake_doc)
    monkeypatch.setattr(
        gjgk_update_module,
        "create_word_application",
        lambda **_kwargs: (fake_word, False),
    )
    monkeypatch.setattr(
        gjgk_update_module,
        "open_document_with_retry",
        lambda **_kwargs: fake_doc,
    )
    monkeypatch.setattr(
        gjgk_update_module,
        "unprotect_document",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(gjgk_update_module, "get_anchor_target_sizes", lambda *_args: (0, 0))
    monkeypatch.setattr(
        gjgk_update_module,
        "find_anchor_range",
        lambda *_args, **_kwargs: (
            {"start": 10, "end": 20, "page": 1, "font": "宋体", "size": 12},
            {"start": 90, "end": 95, "page": 1, "font": "宋体", "size": 12},
        ),
    )
    monkeypatch.setattr(
        gjgk_update_module,
        "_resolve_gjgk_content_range",
        lambda **_kwargs: {
            "range_start": 20,
            "range_end": 80,
            "start_page": 1,
            "end_page": 1,
        },
    )
    monkeypatch.setattr(
        gjgk_update_module,
        "_build_insert_items",
        lambda _text: [{"type": "text", "line": "国际需求正文"}],
    )
    monkeypatch.setattr(gjgk_update_module, "_delete_original_content", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        gjgk_update_module,
        "_trim_leading_layout_controls",
        lambda *args, **kwargs: 20,
    )
    monkeypatch.setattr(
        gjgk_update_module,
        "_find_first_insert_position_on_anchor_page",
        lambda *args, **kwargs: 20,
    )
    monkeypatch.setattr(
        gjgk_update_module,
        "_describe_range_state",
        lambda *args, **kwargs: "range-state",
    )
    monkeypatch.setattr(gjgk_update_module, "_set_collapsed_range", lambda *args, **kwargs: None)
    monkeypatch.setattr(gjgk_update_module, "_ensure_insert_range", lambda *args, **kwargs: None)

    def _fake_insert_text_line(_doc, insert_range, *_args, **_kwargs):
        insert_range.Start = 40
        insert_range.End = 40

    monkeypatch.setattr(gjgk_update_module, "_insert_text_line", _fake_insert_text_line)
    monkeypatch.setattr(
        gjgk_update_module,
        "_reposition_insert_range_if_locked",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(gjgk_update_module, "cleanup_blank_paragraphs", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        gjgk_update_module,
        "write_polished_comments",
        lambda **_kwargs: {"added": 0, "failed": 0, "skipped": 0, "issues": []},
    )
    monkeypatch.setattr(
        gjgk_update_module,
        "save_document_with_retry",
        lambda doc, **_kwargs: doc.Save(),
    )
    monkeypatch.setattr(gjgk_update_module, "close_word_application", lambda **_kwargs: None)


@pytest.mark.parametrize(
    ("module", "function_name", "polished_text", "marker_ranges", "expected_step"),
    [
        (
            common_update_module,
            "update_word",
            "交付日期：合同签订后30天\n付款方式：按季度结算",
            [
                ("DELIVERY_DATE_MARKER", 30, 42, "交付日期：旧值\r"),
                ("PAYMENT_METHOD_MARKER", 60, 72, "付款方式：旧值\r"),
            ],
            "步骤6",
        ),
        (
            gngk_fw_zc_update_module,
            "gngk_fw_zc_update_word",
            "服务地点：上海院区\n服务期限：12个月\n付款方式：按季度结算",
            [
                ("SERVICE_LOCATION_MARKER", 30, 42, "服务地点：旧值\r"),
                ("SERVICE_TERM_MARKER", 50, 62, "服务期限：旧值\r"),
                ("PAYMENT_METHOD_MARKER", 70, 82, "付款方式：旧值\r"),
            ],
            "步骤5",
        ),
    ],
)
def test_update_word_applies_inline_styles_with_anchor_bounds_and_summary(
    monkeypatch,
    module,
    function_name: str,
    polished_text: str,
    marker_ranges: list[tuple[str, int, int, str]],
    expected_step: str,
) -> None:
    fake_doc = _FakeDoc()
    fields = {
        getattr(module, marker_name): _FakeRange(fake_doc, start, end, text)
        for marker_name, start, end, text in marker_ranges
    }
    style_calls: list[dict[str, Any]] = []
    _patch_update_runtime(monkeypatch, module, fake_doc, fields)

    def _fake_apply_inline_style_fragments(**kwargs):
        style_calls.append(kwargs)
        return _style_result()

    monkeypatch.setattr(
        module,
        "apply_inline_style_fragments",
        _fake_apply_inline_style_fragments,
    )
    monkeypatch.setattr(
        module,
        "summarize_style_writeback_result",
        lambda _result: "样式摘要",
    )

    result = getattr(module, function_name)(
        {
            "prepared_doc_path": "fake.docx",
            "polished_text": polished_text,
            "insertion_before_text": "前锚点",
            "insertion_after_text": "后锚点",
            "inline_style_fragments": [{"source_text": "模板样式"}],
            "style_writeback_mode": "bold_only",
            "generated_comment_count": 0,
            "polished_comments": [],
            "suppress_comment_progress_logs": True,
        },
        config=None,
    )

    assert len(style_calls) == 1
    style_call = style_calls[0]
    assert style_call["doc"] is fake_doc
    assert style_call["inline_style_fragments"] == [{"source_text": "模板样式"}]
    assert style_call["style_writeback_mode"] == "bold_only"
    assert style_call["bound_start"] == 20
    assert style_call["bound_end"] == 90
    assert style_call["step_label"] == expected_step
    assert result["style_writeback_result"] == _style_result()
    assert result["style_writeback_summary"] == "样式摘要"
    assert fake_doc.saved is True


@pytest.mark.parametrize(
    ("module", "function_name", "polished_text", "marker_ranges"),
    [
        (
            common_update_module,
            "update_word",
            "交付日期：合同签订后30天\n付款方式：按季度结算",
            [
                ("DELIVERY_DATE_MARKER", 30, 42, "交付日期：旧值\r"),
                ("PAYMENT_METHOD_MARKER", 60, 72, "付款方式：旧值\r"),
            ],
        ),
        (
            gngk_fw_zc_update_module,
            "gngk_fw_zc_update_word",
            "服务地点：上海院区\n服务期限：12个月\n付款方式：按季度结算",
            [
                ("SERVICE_LOCATION_MARKER", 30, 42, "服务地点：旧值\r"),
                ("SERVICE_TERM_MARKER", 50, 62, "服务期限：旧值\r"),
                ("PAYMENT_METHOD_MARKER", 70, 82, "付款方式：旧值\r"),
            ],
        ),
    ],
)
def test_update_word_warns_instead_of_hard_failing_when_no_comments_written(
    monkeypatch,
    module,
    function_name: str,
    polished_text: str,
    marker_ranges: list[tuple[str, int, int, str]],
) -> None:
    fake_doc = _FakeDoc()
    fields = {
        getattr(module, marker_name): _FakeRange(fake_doc, start, end, text)
        for marker_name, start, end, text in marker_ranges
    }
    _patch_update_runtime(
        monkeypatch,
        module,
        fake_doc,
        fields,
        comment_result={"added": 0, "failed": 2, "skipped": 0, "issues": []},
    )

    progress_warnings: list[str] = []
    progress_errors: list[str] = []
    monkeypatch.setattr(
        module.progress_log,
        "warning",
        lambda message, *args: progress_warnings.append(
            message % args if args else str(message)
        ),
    )
    monkeypatch.setattr(
        module.progress_log,
        "error",
        lambda message, *args: progress_errors.append(message % args if args else str(message)),
    )

    result = getattr(module, function_name)(
        {
            "prepared_doc_path": "fake.docx",
            "polished_text": polished_text,
            "insertion_before_text": "前锚点",
            "insertion_after_text": "后锚点",
            "generated_comment_count": 2,
            "polished_comments": [
                {"reference_text": "条款A", "comment_text": "批注A"},
            ],
        },
        config=None,
    )

    assert result["comment_writeback_result"] == {
        "summary": "AI批注写入: 生成=2, 成功=0, 失败=2, 跳过=0",
        "generated": 2,
        "added": 0,
        "failed": 2,
        "skipped": 0,
        "warning": True,
    }
    assert progress_warnings == ["AI批注写入: 生成=2, 成功=0, 失败=2, 跳过=0"]
    assert progress_errors == []
    assert fake_doc.saved is True


def test_gjgk_update_word_applies_inline_styles_with_anchor_bounds_and_summary(
    monkeypatch,
) -> None:
    fake_doc = _FakeDoc()
    style_calls: list[dict[str, Any]] = []
    _patch_gjgk_update_runtime(monkeypatch, fake_doc)

    def _fake_apply_inline_style_fragments(**kwargs):
        style_calls.append(kwargs)
        return _style_result()

    monkeypatch.setattr(
        gjgk_update_module,
        "apply_inline_style_fragments",
        _fake_apply_inline_style_fragments,
    )
    monkeypatch.setattr(
        gjgk_update_module,
        "summarize_style_writeback_result",
        lambda _result: "样式摘要",
    )

    result = gjgk_update_module.gjgk_update_word(
        {
            "prepared_doc_path": "fake.docx",
            "polished_text": "国际需求正文",
            "insertion_before_text": "前锚点",
            "insertion_after_text": "后锚点",
            "inline_style_fragments": [{"source_text": "模板样式"}],
            "style_writeback_mode": "bold_only",
            "generated_comment_count": 0,
            "polished_comments": [],
            "suppress_comment_progress_logs": True,
        },
        config=None,
    )

    assert len(style_calls) == 1
    style_call = style_calls[0]
    assert style_call["doc"] is fake_doc
    assert style_call["inline_style_fragments"] == [{"source_text": "模板样式"}]
    assert style_call["style_writeback_mode"] == "bold_only"
    assert style_call["bound_start"] == 20
    assert style_call["bound_end"] == 90
    assert style_call["step_label"] == "步骤6"
    assert result["style_writeback_result"] == _style_result()
    assert result["style_writeback_summary"] == "样式摘要"
    assert fake_doc.saved is True
