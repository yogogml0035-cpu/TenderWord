from __future__ import annotations

import importlib
from dataclasses import dataclass

replace_content_module = importlib.import_module(
    "backend.nodes.common_word_nodes.replace_content"
)


class _FakeFind:
    def __init__(self, target_range: "_FakeRange") -> None:
        self._target_range = target_range
        self.Text = ""
        self.Forward = True
        self.Wrap = None
        self.MatchCase = False
        self.MatchWholeWord = False

    def ClearFormatting(self) -> None:
        return None

    def Execute(self) -> bool:
        query = str(self.Text or "")
        if not query:
            return False

        text = self._target_range.story.text
        start = int(self._target_range._start_local)
        end = len(text)
        index = text.find(query, start, end)
        if index < 0:
            return False

        self._target_range._start_local = index
        self._target_range._end_local = index + len(query)
        return True


@dataclass
class _FakeStory:
    story_type: int
    text: str
    page_number: int
    offset: int
    next_story: "_FakeStory | None" = None

    @property
    def root_range(self) -> "_FakeRange":
        return _FakeRange(self, 0, len(self.text), is_root=True)


class _FakeRange:
    def __init__(self, story: _FakeStory, start_local: int, end_local: int, *, is_root: bool = False) -> None:
        self.story = story
        self._start_local = int(start_local)
        self._end_local = int(end_local)
        self._is_root = bool(is_root)
        self.Find = _FakeFind(self)

    @property
    def StoryType(self) -> int:
        return int(self.story.story_type)

    @property
    def Start(self) -> int:
        return int(self.story.offset + self._start_local)

    @Start.setter
    def Start(self, value: int) -> None:
        self._start_local = max(0, int(value) - int(self.story.offset))

    @property
    def End(self) -> int:
        if self._is_root:
            return int(self.story.offset + len(self.story.text))
        return int(self.story.offset + self._end_local)

    @End.setter
    def End(self, value: int) -> None:
        self._end_local = max(self._start_local, int(value) - int(self.story.offset))

    @property
    def Duplicate(self) -> "_FakeRange":
        end_local = len(self.story.text) if self._is_root else self._end_local
        return _FakeRange(
            self.story,
            self._start_local,
            end_local,
            is_root=False,
        )

    @property
    def NextStoryRange(self) -> "_FakeRange | None":
        if self.story.next_story is None:
            return None
        return self.story.next_story.root_range

    @property
    def Text(self) -> str:
        return self.story.text[self._start_local : self._end_local]

    @Text.setter
    def Text(self, value: str) -> None:
        new_text = str(value or "")
        old_len = self._end_local - self._start_local
        self.story.text = (
            self.story.text[: self._start_local]
            + new_text
            + self.story.text[self._end_local :]
        )
        self._end_local = self._start_local + len(new_text)
        if self._is_root:
            self._end_local = len(self.story.text)
        elif len(new_text) != old_len:
            self._end_local = self._start_local + len(new_text)

    def Collapse(self, *_args) -> None:
        self._start_local = self._end_local

    def Information(self, _code) -> int:
        return int(self.story.page_number)


class _FakeCommentRange:
    def __init__(self, owner: "_FakeComment", start: int, end: int) -> None:
        self._owner = owner
        self.Start = int(start)
        self.End = int(end)

    @property
    def Text(self) -> str:
        return self._owner.Text

    @Text.setter
    def Text(self, value: str) -> None:
        if self._owner.fail_on_rewrite:
            raise RuntimeError("simulated rewrite failure")
        self._owner.Text = str(value)


class _FakeComment:
    def __init__(self, start: int, end: int, text: str, *, fail_on_rewrite: bool = False) -> None:
        self.Text = str(text)
        self.fail_on_rewrite = bool(fail_on_rewrite)
        self.Range = _FakeCommentRange(self, start, end)
        self.Scope = self.Range
        self.Reference = self.Range


class _FakeCommentsCollection:
    def __init__(self) -> None:
        self._items: list[_FakeComment] = []
        self.fail_on_add_starts: set[int] = set()

    @property
    def Count(self) -> int:
        return len(self._items)

    def __call__(self, index: int) -> _FakeComment:
        return self._items[int(index) - 1]

    def Add(self, Range, Text: str) -> _FakeComment:
        start = int(Range.Start)
        if start in self.fail_on_add_starts:
            raise RuntimeError("simulated add failure")
        comment = _FakeComment(int(Range.Start), int(Range.End), str(Text))
        self._items.append(comment)
        return comment

    def append_existing_comment(
        self,
        *,
        start: int,
        end: int,
        text: str,
        fail_on_rewrite: bool = False,
    ) -> _FakeComment:
        comment = _FakeComment(start, end, text, fail_on_rewrite=fail_on_rewrite)
        self._items.append(comment)
        return comment


class _FakeDocument:
    def __init__(self, stories: list[_FakeStory]) -> None:
        if not stories:
            raise ValueError("stories cannot be empty")

        for idx in range(len(stories) - 1):
            stories[idx].next_story = stories[idx + 1]

        self._stories = stories
        self.StoryRanges = [stories[0].root_range]
        self.Comments = _FakeCommentsCollection()
        self.saved = False

    def Save(self) -> None:
        self.saved = True


def _run_replace_content(monkeypatch, *, tmp_path, doc: _FakeDocument, state_overrides: dict | None = None):
    doc_path = tmp_path / "prepared.docx"
    doc_path.write_text("fake", encoding="utf-8")

    monkeypatch.setattr(
        replace_content_module,
        "create_word_application",
        lambda **_kwargs: (object(), True),
    )
    monkeypatch.setattr(
        replace_content_module,
        "open_document_with_retry",
        lambda **_kwargs: doc,
    )
    monkeypatch.setattr(
        replace_content_module,
        "unprotect_document",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        replace_content_module,
        "close_word_application",
        lambda **_kwargs: None,
    )

    base_state = {
        "prepared_doc_path": str(doc_path),
        "tender_type": "xjcg",
        "placeholder_mapping": {"project_name": "<PN>", "project_number": "<NO>"},
        "replacements": [("<PN>", "P001")],
    }
    if state_overrides:
        base_state.update(state_overrides)

    return replace_content_module.replace_content(base_state, config={})


def test_project_name_first_hit_uses_special_then_erp(monkeypatch, tmp_path) -> None:
    body = _FakeStory(story_type=1, text="A <PN> B <PN> C", page_number=3, offset=0)
    doc = _FakeDocument([body])

    result = _run_replace_content(monkeypatch, tmp_path=tmp_path, doc=doc)

    assert result["replace_content_done"] is True
    assert doc.Comments.Count == 2
    assert doc.Comments(1).Text == replace_content_module.PROJECT_NAME_FIRST_HIT_COMMENT
    assert doc.Comments(2).Text == replace_content_module.ERP_COMMENT_LABEL
    assert "首个候选是否命中: 是" in result["replacement_log"]
    assert "特殊批注最终落位: 第 1 个正文 project_name 命中" in result["replacement_log"]


def test_project_name_first_hit_preserves_existing_comment_and_adds_ai_comment(monkeypatch, tmp_path) -> None:
    body_text = "X <PN> Y"
    body = _FakeStory(story_type=1, text=body_text, page_number=5, offset=0)
    doc = _FakeDocument([body])
    first_start = body_text.find("<PN>")
    doc.Comments.append_existing_comment(
        start=first_start,
        end=first_start + len("<PN>"),
        text="人工批注",
    )

    result = _run_replace_content(monkeypatch, tmp_path=tmp_path, doc=doc)

    assert doc.Comments.Count == 2
    assert doc.Comments(1).Text == "人工批注"
    assert doc.Comments(2).Text == replace_content_module.PROJECT_NAME_FIRST_HIT_COMMENT
    assert "首个候选处理方式: 新增批注" in result["replacement_log"]


def test_project_name_first_hit_dedupes_existing_ai_comment_on_nearby_anchor(monkeypatch, tmp_path) -> None:
    body_text = "X <PN> Y"
    body = _FakeStory(story_type=1, text=body_text, page_number=6, offset=0)
    doc = _FakeDocument([body])
    first_start = body_text.find("<PN>")
    ai_comment_start = first_start + len("<PN>")
    doc.Comments.append_existing_comment(
        start=first_start,
        end=first_start + len("<PN>"),
        text="人工批注",
    )
    doc.Comments.append_existing_comment(
        start=ai_comment_start,
        end=ai_comment_start + 1,
        text=replace_content_module.PROJECT_NAME_FIRST_HIT_COMMENT,
    )

    result = _run_replace_content(monkeypatch, tmp_path=tmp_path, doc=doc)

    assert doc.Comments.Count == 2
    assert doc.Comments(1).Text == "人工批注"
    assert doc.Comments(2).Text == replace_content_module.PROJECT_NAME_FIRST_HIT_COMMENT
    assert "首个候选处理方式: 已存在同文案，跳过重复新增" in result["replacement_log"]


def test_project_name_first_hit_retries_on_nearby_anchor(monkeypatch, tmp_path) -> None:
    body_text = "Head <PN> Tail"
    body = _FakeStory(story_type=1, text=body_text, page_number=7, offset=0)
    doc = _FakeDocument([body])
    first_start = body_text.find("<PN>")
    doc.Comments.fail_on_add_starts.add(first_start)

    result = _run_replace_content(monkeypatch, tmp_path=tmp_path, doc=doc)

    assert doc.Comments.Count == 1
    assert doc.Comments(1).Text == replace_content_module.PROJECT_NAME_FIRST_HIT_COMMENT
    assert doc.Comments(1).Range.Start == first_start + len("P001")
    assert "首个候选处理方式: 邻位新增批注" in result["replacement_log"]


def test_project_name_first_hit_failure_falls_back_to_next_match(monkeypatch, tmp_path) -> None:
    body_text = "Head <PN> Mid <PN> Tail"
    body = _FakeStory(story_type=1, text=body_text, page_number=8, offset=0)
    doc = _FakeDocument([body])
    first_start = body_text.find("<PN>")
    second_start = body_text.find("<PN>", first_start + 1)
    doc.Comments.fail_on_add_starts.update(
        {
            first_start - 1,
            first_start,
            first_start + len("P001"),
        }
    )

    result = _run_replace_content(monkeypatch, tmp_path=tmp_path, doc=doc)

    assert doc.Comments.Count == 1
    assert doc.Comments(1).Text == replace_content_module.PROJECT_NAME_FIRST_HIT_COMMENT
    assert doc.Comments(1).Range.Start == second_start
    assert "是否发生 fallback 到后续 project_name: 是" in result["replacement_log"]
    assert "特殊批注最终落位: 第 2 个正文 project_name 命中" in result["replacement_log"]


def test_header_project_name_does_not_trigger_first_hit_special_comment(monkeypatch, tmp_path) -> None:
    body = _FakeStory(story_type=1, text="Body without token", page_number=1, offset=0)
    header = _FakeStory(story_type=7, text="Header <PN>", page_number=1, offset=10000)
    doc = _FakeDocument([body, header])

    result = _run_replace_content(monkeypatch, tmp_path=tmp_path, doc=doc)

    assert doc.Comments.Count == 0
    assert "首个候选是否命中: 否" in result["replacement_log"]
    assert "特殊批注最终落位: 未成功落位" in result["replacement_log"]


def test_non_project_name_replacements_keep_erp_comment_behavior(monkeypatch, tmp_path) -> None:
    body = _FakeStory(story_type=1, text="A <OT> B <OT> C", page_number=2, offset=0)
    doc = _FakeDocument([body])

    result = _run_replace_content(
        monkeypatch,
        tmp_path=tmp_path,
        doc=doc,
        state_overrides={
            "placeholder_mapping": {"project_name": "<PN>", "project_number": "<NO>"},
            "replacements": [("<OT>", "O001")],
        },
    )

    assert doc.Comments.Count == 2
    assert doc.Comments(1).Text == replace_content_module.ERP_COMMENT_LABEL
    assert doc.Comments(2).Text == replace_content_module.ERP_COMMENT_LABEL
    assert replace_content_module.PROJECT_NAME_FIRST_HIT_COMMENT not in result["replacement_log"]
