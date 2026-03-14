import importlib

import pytest

extract_tender_params_module = importlib.import_module(
    "backend.nodes.common_word_nodes.extract_tender_params"
)


class _FakeSelection:
    def __init__(self):
        self.Start = 0

    def GoTo(self, _what, _which, page):
        # 模拟页码对应的起始偏移
        self.Start = page * 100


class _FakeWord:
    def __init__(self):
        self.Selection = _FakeSelection()


class _FakeRange:
    def __init__(self):
        self.Tables = []


class _FakeDocument:
    def Range(self, _start, _end):
        return _FakeRange()


def _common_monkeypatch(monkeypatch):
    monkeypatch.setattr(
        extract_tender_params_module,
        "create_word_application",
        lambda **_kwargs: (_FakeWord(), False),
    )
    monkeypatch.setattr(
        extract_tender_params_module,
        "open_document_with_retry",
        lambda **_kwargs: _FakeDocument(),
    )
    monkeypatch.setattr(
        extract_tender_params_module,
        "unprotect_document",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        extract_tender_params_module, "close_word_application", lambda **_kwargs: None
    )


def test_extract_tender_params_fail_fast_when_before_anchor_missing(monkeypatch):
    _common_monkeypatch(monkeypatch)
    monkeypatch.setattr(
        extract_tender_params_module,
        "find_anchor_range",
        lambda **_kwargs: (None, {"page": 4, "start": 400, "end": 420}),
    )

    with pytest.raises(RuntimeError, match="未找到前置锚点"):
        extract_tender_params_module.extract_tender_params(
            {
                "clean_draft_path": __file__,
                "insertion_before_text": "第三章 采购需求",
                "insertion_after_text": "第四章 响应文件有关格式",
                "tender_type": "xjcg",
            },
            config={},
        )


def test_extract_tender_params_fail_fast_when_after_anchor_missing(monkeypatch):
    _common_monkeypatch(monkeypatch)
    monkeypatch.setattr(
        extract_tender_params_module,
        "find_anchor_range",
        lambda **_kwargs: ({"page": 2, "start": 200, "end": 220}, None),
    )

    with pytest.raises(RuntimeError, match="未找到后置锚点"):
        extract_tender_params_module.extract_tender_params(
            {
                "clean_draft_path": __file__,
                "insertion_before_text": "第三章 采购需求",
                "insertion_after_text": "第四章 响应文件有关格式",
                "tender_type": "xjcg",
            },
            config={},
        )


def test_extract_tender_params_fail_fast_when_anchor_pages_invalid(monkeypatch):
    _common_monkeypatch(monkeypatch)
    monkeypatch.setattr(
        extract_tender_params_module,
        "find_anchor_range",
        lambda **_kwargs: (
            {"page": 3, "start": 300, "end": 320, "font": "宋体", "size": 18.0},
            {"page": 3, "start": 500, "end": 520, "font": "宋体", "size": 18.0},
        ),
    )

    with pytest.raises(RuntimeError, match="后置锚点页码不大于前置锚点页码"):
        extract_tender_params_module.extract_tender_params(
            {
                "clean_draft_path": __file__,
                "insertion_before_text": "第三章 采购需求",
                "insertion_after_text": "第四章 响应文件有关格式",
                "tender_type": "xjcg",
            },
            config={},
        )


def test_extract_tender_params_success_returns_content_and_pages(monkeypatch):
    _common_monkeypatch(monkeypatch)
    monkeypatch.setattr(
        extract_tender_params_module,
        "find_anchor_range",
        lambda **_kwargs: (
            {"page": 2, "start": 200, "end": 250, "font": "宋体", "size": 18.0},
            {"page": 5, "start": 900, "end": 950, "font": "宋体", "size": 18.0},
        ),
    )
    monkeypatch.setattr(
        extract_tender_params_module,
        "extract_content_with_tables",
        lambda _rng: "提取到的采购需求内容",
    )

    result = extract_tender_params_module.extract_tender_params(
        {
            "clean_draft_path": __file__,
            "insertion_before_text": "第三章 采购需求",
            "insertion_after_text": "第四章 响应文件有关格式",
            "tender_type": "xjcg",
        },
        config={},
    )

    assert result["origin_tender_params"] == "提取到的采购需求内容"
    assert result["start_page"] == 3
    assert result["end_page"] == 4
