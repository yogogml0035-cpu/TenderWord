"""
Tests for special comment handling in replace_content.

Covers the project_name first-hit-in-body logic (story_type=1):
- First body hit receives SPECIAL_PROJECT_NAME_COMMENT
- Subsequent body hits receive "ERP数据" comment
- Header hits never receive the special comment
- Fallback when special comment Add fails on first hit
- Non-project_name fields always use "ERP数据"
"""

import importlib
import os
import tempfile
import unittest
from unittest.mock import patch

replace_content_module = importlib.import_module(
    "backend.nodes.common_word_nodes.replace_content"
)

SPECIAL_PROJECT_NAME_COMMENT = replace_content_module.SPECIAL_PROJECT_NAME_COMMENT
ERP_COMMENT = "ERP数据"


class _FakeComment:
    """Fake Word Comment with Scope and Delete support."""

    def __init__(self, scope_start, scope_end, text):
        self._scope_start = scope_start
        self._scope_end = scope_end
        self._text = text
        self._deleted = False

    @property
    def Scope(self):
        return type("Scope", (), {"Start": self._scope_start, "End": self._scope_end})()

    @property
    def Range(self):
        return type("Range", (), {"Text": self._text})()

    def Delete(self):
        self._deleted = True


class _FakeCommentsCollection:
    """Fake Word Comments collection (1-indexed, Count, Add, __call__)."""

    def __init__(self, fail_on_add_call=None):
        self._comments: list[_FakeComment] = []
        self._add_call_count = 0
        self._fail_on_add_call = fail_on_add_call  # 1-based; raise on this Add call index

    @property
    def Count(self):
        return sum(1 for c in self._comments if not c._deleted)

    def __call__(self, index):
        active = [c for c in self._comments if not c._deleted]
        return active[index - 1]

    def Add(self, Range, Text):
        self._add_call_count += 1
        if self._fail_on_add_call is not None and self._add_call_count == self._fail_on_add_call:
            raise Exception("Simulated comment add failure")
        comment = _FakeComment(Range.Start, Range.End, Text)
        self._comments.append(comment)
        return comment

    def add_existing(self, scope_start, scope_end, text):
        """Pre-populate an existing comment for test setup."""
        comment = _FakeComment(scope_start, scope_end, text)
        self._comments.append(comment)
        return comment

    @property
    def all_comments(self):
        """Return all comments (including deleted) for verification."""
        return list(self._comments)


class _FakeFind:
    """Fake Word Find object. Returns hits from a shared list on Execute()."""

    def __init__(self, parent_range):
        self._parent = parent_range
        self.Text = ""
        self.Forward = True
        self.Wrap = 0
        self.MatchCase = False
        self.MatchWholeWord = False

    def ClearFormatting(self):
        pass

    def Execute(self):
        return self._parent._consume_hit()


class _FakeRange:
    """Fake Word Range with Find support and position-based hit tracking."""

    def __init__(self, start=0, end=0, text=""):
        self.Start = start
        self.End = end
        self.Text = text
        self._find_hits: list[tuple[int, int]] = []
        self._find_hit_idx = 0
        self._find = _FakeFind(self)

    def _consume_hit(self):
        if self._find_hit_idx < len(self._find_hits):
            start, end = self._find_hits[self._find_hit_idx]
            self._find_hit_idx += 1
            self.Start = start
            self.End = end
            return True
        return False

    def set_find_hits(self, hits):
        self._find_hits = list(hits)
        self._find_hit_idx = 0

    @property
    def Duplicate(self):
        dup = _FakeRange(self.Start, self.End, self.Text)
        dup._find_hits = self._find_hits  # shared reference
        dup._find_hit_idx = 0
        return dup

    @property
    def Find(self):
        return self._find

    def Collapse(self, direction):
        self.Start = self.End

    def Information(self, kind):
        return 1  # page 1


class _FakeStoryRange(_FakeRange):
    """Fake Word StoryRange with StoryType and NextStoryRange."""

    def __init__(self, story_type, find_hits=None, start=0, end=0, text=""):
        super().__init__(start, end, text)
        self.StoryType = story_type
        if find_hits:
            self.set_find_hits(find_hits)
        self._next_story_range = None

    @property
    def NextStoryRange(self):
        if self._next_story_range is not None:
            return self._next_story_range
        raise Exception("No next story range")


class _FakeStoryRanges:
    """Fake Word StoryRanges collection (iterable)."""

    def __init__(self, ranges):
        self._ranges = list(ranges)

    def __iter__(self):
        return iter(self._ranges)


class _FakeDocument:
    """Fake Word Document with Comments and StoryRanges."""

    def __init__(self, story_ranges, comments=None):
        self.Comments = comments if comments is not None else _FakeCommentsCollection()
        self._story_ranges = _FakeStoryRanges(story_ranges)

    @property
    def StoryRanges(self):
        return self._story_ranges

    def Save(self):
        pass


class TestReplaceContentSpecialComment(unittest.TestCase):
    """Test project_name special comment handling in replace_content."""

    def setUp(self):
        # Create a temp file to satisfy prepared_doc_path checks
        self._temp = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
        self._temp.close()
        self.prepared_doc_path = self._temp.name

    def tearDown(self):
        if os.path.exists(self.prepared_doc_path):
            os.unlink(self.prepared_doc_path)

    def _call_replace_content(self, doc, state):
        """Invoke replace_content with all Word/FS dependencies mocked."""
        with patch(
            "backend.nodes.common_word_nodes.replace_content.create_word_application"
        ) as mock_create, patch(
            "backend.nodes.common_word_nodes.replace_content.open_document_with_retry"
        ) as mock_open, patch(
            "backend.nodes.common_word_nodes.replace_content.unprotect_document"
        ) as mock_unprotect, patch(
            "backend.nodes.common_word_nodes.replace_content.close_word_application"
        ) as mock_close:
            mock_create.return_value = (object(), True)
            mock_open.return_value = doc
            return replace_content_module.replace_content(state, config=None)

    def _make_state(self, replacements, placeholder_mapping, tender_type="xjcg"):
        return {
            "prepared_doc_path": self.prepared_doc_path,
            "replacements": replacements,
            "placeholder_mapping": placeholder_mapping,
            "tender_type": tender_type,
        }

    def test_special_comment_placed_on_first_project_name_hit_in_body(self):
        """First body hit gets SPECIAL_PROJECT_NAME_COMMENT; subsequent get ERP数据."""
        pn_placeholder = "{{project_name}}"
        body_range = _FakeStoryRange(
            story_type=1,
            find_hits=[(100, 120), (200, 220)],
        )
        doc = _FakeDocument([body_range])

        state = self._make_state(
            replacements=[(pn_placeholder, "测试项目名称")],
            placeholder_mapping={"project_name": pn_placeholder},
        )
        self._call_replace_content(doc, state)

        comments = doc.Comments.all_comments
        self.assertEqual(len(comments), 2)
        self.assertEqual(comments[0].Scope.Start, 100)
        self.assertEqual(comments[0].Scope.End, 120)
        self.assertEqual(comments[0].Range.Text, SPECIAL_PROJECT_NAME_COMMENT)
        self.assertFalse(comments[0]._deleted)

        self.assertEqual(comments[1].Scope.Start, 200)
        self.assertEqual(comments[1].Scope.End, 220)
        self.assertEqual(comments[1].Range.Text, ERP_COMMENT)
        self.assertFalse(comments[1]._deleted)

    def test_header_project_name_does_not_get_special_comment(self):
        """Header (story_type=7) project_name never receives the special comment;
        allow_comments=False for non-body story types so no comment is added."""
        pn_placeholder = "{{project_name}}"
        header_range = _FakeStoryRange(
            story_type=7,
            find_hits=[(50, 70)],
        )
        body_range = _FakeStoryRange(
            story_type=1,
            find_hits=[(100, 120)],
        )
        doc = _FakeDocument([header_range, body_range])

        state = self._make_state(
            replacements=[(pn_placeholder, "测试项目名称")],
            placeholder_mapping={"project_name": pn_placeholder},
        )
        self._call_replace_content(doc, state)

        comments = [c for c in doc.Comments.all_comments if not c._deleted]
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0].Scope.Start, 100)
        self.assertEqual(comments[0].Scope.End, 120)
        self.assertEqual(comments[0].Range.Text, SPECIAL_PROJECT_NAME_COMMENT)

    def test_special_comment_overwrites_existing_comment(self):
        """If a comment already exists at the first project_name body hit,
        it is deleted and replaced with SPECIAL_PROJECT_NAME_COMMENT."""
        pn_placeholder = "{{project_name}}"
        body_range = _FakeStoryRange(
            story_type=1,
            find_hits=[(100, 120)],
        )
        doc = _FakeDocument([body_range])
        # Pre-existing comment at the same range
        doc.Comments.add_existing(100, 120, "旧批注")

        state = self._make_state(
            replacements=[(pn_placeholder, "测试项目名称")],
            placeholder_mapping={"project_name": pn_placeholder},
        )
        self._call_replace_content(doc, state)

        all_comments = doc.Comments.all_comments
        # Old comment should be deleted
        self.assertTrue(all_comments[0]._deleted)
        # New special comment should be added
        self.assertEqual(len(all_comments), 2)
        self.assertFalse(all_comments[1]._deleted)
        self.assertEqual(all_comments[1].Scope.Start, 100)
        self.assertEqual(all_comments[1].Scope.End, 120)
        self.assertEqual(all_comments[1].Range.Text, SPECIAL_PROJECT_NAME_COMMENT)

    def test_fallback_to_subsequent_hit_on_failure(self):
        """If special comment Add fails on first body hit, no comment is added
        there; the second hit then gets the special comment (flag still False)."""
        pn_placeholder = "{{project_name}}"
        body_range = _FakeStoryRange(
            story_type=1,
            find_hits=[(100, 120), (200, 220)],
        )
        comments = _FakeCommentsCollection(fail_on_add_call=1)
        doc = _FakeDocument([body_range], comments=comments)

        state = self._make_state(
            replacements=[(pn_placeholder, "测试项目名称")],
            placeholder_mapping={"project_name": pn_placeholder},
        )
        self._call_replace_content(doc, state)

        active = [c for c in doc.Comments.all_comments if not c._deleted]
        # First hit: no comment (Add failed)
        # Second hit: special comment (flag still False, so it tries again)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].Scope.Start, 200)
        self.assertEqual(active[0].Scope.End, 220)
        self.assertEqual(active[0].Range.Text, SPECIAL_PROJECT_NAME_COMMENT)

    def test_non_project_name_fields_always_use_erp_comment(self):
        """Non-project_name fields in body always get ERP数据 comment."""
        other_placeholder = "{{other_field}}"
        body_range = _FakeStoryRange(
            story_type=1,
            find_hits=[(100, 120)],
        )
        doc = _FakeDocument([body_range])

        state = self._make_state(
            replacements=[(other_placeholder, "其他值")],
            placeholder_mapping={"project_name": "{{project_name}}"},
        )
        self._call_replace_content(doc, state)

        comments = doc.Comments.all_comments
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0].Scope.Start, 100)
        self.assertEqual(comments[0].Scope.End, 120)
        self.assertEqual(comments[0].Range.Text, ERP_COMMENT)


if __name__ == "__main__":
    unittest.main()
