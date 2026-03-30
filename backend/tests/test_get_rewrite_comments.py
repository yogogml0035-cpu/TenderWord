import importlib.util
import sys
import tempfile
import types
from dataclasses import dataclass, field
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


@dataclass
class DocumentAnalysisResultStub:
    comments: list = field(default_factory=list)
    strikethroughs: list = field(default_factory=list)
    non_black_fonts: list = field(default_factory=list)
    total_comments: int = 0
    total_strikethroughs: int = 0
    total_non_black_fonts: int = 0


class ProgressLogStub:
    def debug(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


class DummyDoc:
    def __init__(self):
        self.closed = False

    def Close(self, SaveChanges=False):
        self.closed = True


class _SelectionStub:
    def __init__(self):
        self.Start = 0

    def GoTo(self, _what, _which, page):
        self.Start = int(page) * 100


class _WordStub:
    def __init__(self):
        self.Selection = _SelectionStub()


def _make_package(name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__path__ = []
    return module


def _load_module(monkeypatch, module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_rewrite_comment_modules(monkeypatch):
    for package_name in (
        "backend",
        "backend.config",
        "backend.nodes",
        "backend.nodes.common_word_nodes",
        "backend.util",
        "backend.util.log_util",
    ):
        monkeypatch.setitem(sys.modules, package_name, _make_package(package_name))

    states_module = types.ModuleType("backend.states")
    states_module.TenderGraphStateBase = dict
    states_module.TaskSkillGraphState = dict
    monkeypatch.setitem(sys.modules, "backend.states", states_module)

    word_util_module = types.ModuleType("backend.util.word_util")
    word_util_module.__path__ = []
    word_util_module.WordDocumentInspector = object
    word_util_module.DocumentAnalysisResult = DocumentAnalysisResultStub
    word_util_module.create_word_application = lambda **kwargs: (object(), True)
    word_util_module.close_word_application = lambda **kwargs: None
    word_util_module.open_document_with_retry = lambda *args, **kwargs: DummyDoc()
    word_util_module.wdGoToPage = 1
    word_util_module.wdGoToAbsolute = 1
    word_util_module.wdActiveEndPageNumber = 1
    monkeypatch.setitem(sys.modules, "backend.util.word_util", word_util_module)

    anchor_utils_module = types.ModuleType("backend.util.word_util.anchor_utils")
    anchor_utils_module.find_anchor_range = lambda **_kwargs: (None, None)
    anchor_utils_module.resolve_anchor_content_range = lambda **_kwargs: {
        "range_start": 0,
        "range_end": 0,
    }
    monkeypatch.setitem(
        sys.modules,
        "backend.util.word_util.anchor_utils",
        anchor_utils_module,
    )

    progress_log_module = types.ModuleType("backend.util.log_util.progress_log")
    progress_log_module.progress_log = ProgressLogStub()
    monkeypatch.setitem(
        sys.modules,
        "backend.util.log_util.progress_log",
        progress_log_module,
    )

    tender_config_module = types.ModuleType("backend.config.tender_config")
    tender_config_module.get_anchor_target_sizes = lambda *_args, **_kwargs: (22.0, 22.0)
    monkeypatch.setitem(
        sys.modules,
        "backend.config.tender_config",
        tender_config_module,
    )

    get_comments_module = _load_module(
        monkeypatch,
        "backend.nodes.common_word_nodes.get_comments",
        ROOT / "backend/nodes/common_word_nodes/get_comments.py",
    )
    get_rewrite_comments_module = _load_module(
        monkeypatch,
        "backend.nodes.common_word_nodes.get_rewrite_comments",
        ROOT / "backend/nodes/common_word_nodes/get_rewrite_comments.py",
    )
    return get_comments_module, get_rewrite_comments_module


def _patch_word_dependencies(monkeypatch, comments_module, *, doc, inspector_cls, range_result):
    monkeypatch.setattr(
        comments_module,
        "create_word_application",
        lambda **kwargs: (object(), True),
    )
    monkeypatch.setattr(
        comments_module,
        "open_document_with_retry",
        lambda *args, **kwargs: doc,
    )
    monkeypatch.setattr(
        comments_module,
        "close_word_application",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        comments_module,
        "_get_insertion_range",
        lambda *args, **kwargs: range_result,
    )
    monkeypatch.setattr(comments_module, "WordDocumentInspector", inspector_cls)


def _create_stub_doc() -> Path:
    runtime_dir = ROOT / ".runtime" / "pytest-temp"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = tempfile.mkdtemp(dir=runtime_dir)
    file_path = Path(temp_dir) / "rewrite.docx"
    file_path.write_text("stub", encoding="utf-8")
    return file_path


def test_get_rewrite_comments_maps_comments_to_polished_comments(monkeypatch):
    comments_module, rewrite_module = _load_rewrite_comment_modules(monkeypatch)
    file_path = _create_stub_doc()
    doc = DummyDoc()
    captured = {}

    class InspectorStub:
        def __init__(self, word_app, doc, node_name):
            captured["node_name"] = node_name

        def analyze_document(self, range_start=None, range_end=None):
            captured["range"] = (range_start, range_end)
            return DocumentAnalysisResultStub(
                comments=[
                    types.SimpleNamespace(content="原批注一", scope_text="范围一", reference_text="引用一"),
                    types.SimpleNamespace(content="原批注二", scope_text="范围二", reference_text="引用二"),
                ],
                total_comments=2,
            )

    _patch_word_dependencies(
        monkeypatch,
        comments_module,
        doc=doc,
        inspector_cls=InspectorStub,
        range_result=(10, 20),
    )

    result = rewrite_module.get_rewrite_comments(
        {
            "prepared_doc_path": str(file_path),
            "insertion_before_text": "第三章 采购需求",
            "insertion_after_text": "第四章 投标文件有关格式",
            "tender_type": "gngk",
        },
        config={},
    )

    assert result == {
        "polished_comments": [
            {"reference_text": "引用一", "comment_text": "原批注一"},
            {"reference_text": "引用二", "comment_text": "原批注二"},
        ]
    }
    assert set(result.keys()) == {"polished_comments"}
    assert captured["node_name"] == "get_rewrite_comments"
    assert captured["range"] == (10, 20)
    assert doc.closed is True


def test_get_rewrite_comments_returns_empty_list_when_no_comments(monkeypatch):
    comments_module, rewrite_module = _load_rewrite_comment_modules(monkeypatch)
    file_path = _create_stub_doc()
    doc = DummyDoc()

    class InspectorStub:
        def __init__(self, word_app, doc, node_name):
            pass

        def analyze_document(self, range_start=None, range_end=None):
            return DocumentAnalysisResultStub(comments=[], total_comments=0)

    _patch_word_dependencies(
        monkeypatch,
        comments_module,
        doc=doc,
        inspector_cls=InspectorStub,
        range_result=(30, 80),
    )

    result = rewrite_module.get_rewrite_comments(
        {
            "prepared_doc_path": str(file_path),
            "insertion_before_text": "A",
            "insertion_after_text": "B",
            "tender_type": "xjcg",
        },
        config={},
    )

    assert result == {"polished_comments": []}
    assert doc.closed is True


def test_get_rewrite_comments_raises_when_anchor_range_missing(monkeypatch):
    comments_module, rewrite_module = _load_rewrite_comment_modules(monkeypatch)
    file_path = _create_stub_doc()
    doc = DummyDoc()

    class InspectorStub:
        def __init__(self, word_app, doc, node_name):
            pass

        def analyze_document(self, range_start=None, range_end=None):
            raise AssertionError("strict 锚点缺失时不应继续分析文档")

    _patch_word_dependencies(
        monkeypatch,
        comments_module,
        doc=doc,
        inspector_cls=InspectorStub,
        range_result=(None, None),
    )

    with pytest.raises(ValueError, match="未能定位锚点范围"):
        rewrite_module.get_rewrite_comments(
            {
                "prepared_doc_path": str(file_path),
                "insertion_before_text": "A",
                "insertion_after_text": "B",
                "tender_type": "xjcg",
            },
            config={},
        )

    assert doc.closed is True


def test_get_rewrite_comments_propagates_inspector_errors(monkeypatch):
    comments_module, rewrite_module = _load_rewrite_comment_modules(monkeypatch)
    file_path = _create_stub_doc()
    doc = DummyDoc()

    class InspectorStub:
        def __init__(self, word_app, doc, node_name):
            pass

        def analyze_document(self, range_start=None, range_end=None):
            raise RuntimeError("boom")

    _patch_word_dependencies(
        monkeypatch,
        comments_module,
        doc=doc,
        inspector_cls=InspectorStub,
        range_result=(10, 20),
    )

    with pytest.raises(RuntimeError, match="boom"):
        rewrite_module.get_rewrite_comments(
            {
                "prepared_doc_path": str(file_path),
                "insertion_before_text": "A",
                "insertion_after_text": "B",
                "tender_type": "xjcg",
            },
            config={},
        )

    assert doc.closed is True


def test_get_insertion_range_gjgk_keeps_same_anchor_page(monkeypatch):
    get_comments_module, _rewrite_module = _load_rewrite_comment_modules(monkeypatch)

    monkeypatch.setattr(
        get_comments_module,
        "find_anchor_range",
        lambda **_kwargs: (
            {"page": 22, "start": 2200, "end": 2250, "font": "宋体", "size": 16.0},
            {"page": 24, "start": 2900, "end": 2950, "font": "宋体", "size": 14.0},
        ),
    )
    monkeypatch.setattr(
        get_comments_module,
        "resolve_anchor_content_range",
        lambda **_kwargs: {"range_start": 2250, "range_end": 2900},
    )

    range_start, range_end = get_comments_module._get_insertion_range(
        DummyDoc(),
        _WordStub(),
        "技术规格及要求",
        "附件1：投标文件封面（格式）",
        16.0,
        14.0,
        tender_type="gjgk",
    )

    assert range_start == 2250
    assert range_end == 2900


def test_get_insertion_range_xjcg_still_uses_next_page_start(monkeypatch):
    get_comments_module, _rewrite_module = _load_rewrite_comment_modules(monkeypatch)

    monkeypatch.setattr(
        get_comments_module,
        "find_anchor_range",
        lambda **_kwargs: (
            {"page": 22, "start": 2200, "end": 2250, "font": "宋体", "size": 18.0},
            {"page": 24, "start": 2900, "end": 2950, "font": "宋体", "size": 18.0},
        ),
    )
    monkeypatch.setattr(
        get_comments_module,
        "resolve_anchor_content_range",
        lambda **_kwargs: {"range_start": 2300, "range_end": 2900},
    )

    range_start, range_end = get_comments_module._get_insertion_range(
        DummyDoc(),
        _WordStub(),
        "第三章 采购需求",
        "第四章 投标文件有关格式",
        18.0,
        18.0,
        tender_type="xjcg",
    )

    assert range_start == 2300
    assert range_end == 2900
