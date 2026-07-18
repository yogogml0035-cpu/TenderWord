# tests/nodes/test_comment_writeback.py

import importlib
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from backend.nodes.common_word_nodes.comment_writeback import (
    _build_search_texts,
    build_comment_writeback_summary_payload,
    write_polished_comments,
)

gjgk_update_word_module = importlib.import_module(
    "backend.nodes.gjgk_word_nodes.gjgk_update_word"
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
        document_text = self._target_range.doc.text[: int(self._target_range.End)]
        index = document_text.find(str(self.Text), int(self._target_range.Start))
        if index < 0:
            return False

        self._target_range.Start = index
        self._target_range.End = index + len(str(self.Text))
        return True


class _FakeRange:
    def __init__(self, doc: "_FakeDocument", start: int, end: int) -> None:
        self.doc = doc
        self.Start = int(start)
        self.End = int(end)
        self.Find = _FakeFind(self)

    @property
    def Text(self) -> str:
        return self.doc.text[int(self.Start) : int(self.End)]

    @property
    def Duplicate(self) -> "_FakeRange":
        return _FakeRange(self.doc, self.Start, self.End)

    def SetRange(self, start: int, end: int) -> None:
        self.Start = int(start)
        self.End = int(end)

    def Collapse(self, *_args) -> None:
        self.End = self.Start


class _FakeComment:
    def __init__(self, doc: "_FakeDocument", start: int, end: int, text: str) -> None:
        self.Scope = _FakeRange(doc, start, end)
        self.Reference = self.Scope
        self.Range = self.Scope
        self.Text = text


class _FakeCommentsCollection:
    def __init__(self, doc: "_FakeDocument") -> None:
        self._doc = doc
        self._items: list[_FakeComment] = []
        self.fail_ranges: set[tuple[int, int]] = set()
        self._call_count: int = 0
        self._fail_count: int = 0
        self._should_fail_forever: bool = False

    @property
    def Count(self) -> int:
        return len(self._items)

    def __call__(self, index: int) -> _FakeComment:
        return self._items[index - 1]

    def Add(self, Range, Text: str) -> None:
        match_range = (int(Range.Start), int(Range.End))
        self._call_count += 1

        if self._should_fail_forever:
            raise RuntimeError("simulated RPC error - permanent failure")

        if self._call_count <= self._fail_count:
            raise RuntimeError("simulated RPC error - retryable")

        if match_range in self.fail_ranges:
            raise RuntimeError("simulated add failure")

        self._items.append(
            _FakeComment(
                self._doc,
                int(Range.Start),
                int(Range.End),
                str(Text),
            )
        )

    def set_fail_count(self, count: int) -> None:
        """Set how many initial calls should fail before succeeding."""
        self._fail_count = count

    def set_fail_forever(self) -> None:
        """Make Add() always fail."""
        self._should_fail_forever = True


class _FakeDocument:
    def __init__(self, text: str) -> None:
        self.text = text
        self.Comments = _FakeCommentsCollection(self)
        self.Content = SimpleNamespace(End=len(text))

    def Range(self, start: int, end: int) -> _FakeRange:
        return _FakeRange(self, start, end)


def test_build_comment_writeback_summary_payload_warns_only_on_generated_failures() -> None:
    payload = build_comment_writeback_summary_payload(
        generated_count=3,
        writeback_result={"added": 0, "failed": 3, "skipped": 0},
    )

    assert payload == {
        "summary": "AI批注写入: 生成=3, 成功=0, 失败=3, 跳过=0",
        "generated": 3,
        "added": 0,
        "failed": 3,
        "skipped": 0,
        "warning": True,
    }


@pytest.mark.parametrize(
    ("generated_count", "writeback_result"),
    [
        (0, {"added": 0, "failed": 2, "skipped": 0}),
        (2, {"added": 0, "failed": 0, "skipped": 2}),
    ],
)
def test_build_comment_writeback_summary_payload_does_not_warn_without_failures(
    generated_count,
    writeback_result,
) -> None:
    payload = build_comment_writeback_summary_payload(
        generated_count=generated_count,
        writeback_result=writeback_result,
    )

    assert payload["warning"] is False


# =============================================================================
# Test Group 1: Retry Logic for Comments.Add Failures
# =============================================================================


class TestCommentWritebackRetryLogic:
    """Tests for retry logic when Comments.Add fails with RPC errors."""

    def test_write_polished_comments_retries_on_rpc_error(self) -> None:
        """Test that Comments.Add failures are retried and eventually succeed."""
        doc = _FakeDocument("Test content here")
        doc.Comments.set_fail_count(2)  # Fail first 2 calls

        log_parts: list[str] = []

        with patch(
            "backend.nodes.common_word_nodes.comment_writeback.time.sleep"
        ) as mock_sleep:
            result = write_polished_comments(
                doc=doc,
                polished_comments=[
                    {"reference_text": "content", "comment_text": "Great content!"},
                ],
                bound_start=0,
                bound_end=len(doc.text),
                log_parts=log_parts,
            )

        # Should succeed after retries
        assert result["added"] == 1
        assert result["failed"] == 0
        assert doc.Comments.Count == 1

        # Verify retry delay was called (exact values depend on calculate_retry_delay)
        assert mock_sleep.call_count == 2
        # Each call should be a positive number (delay)
        for call_args in mock_sleep.call_args_list:
            assert call_args[0][0] > 0

    def test_write_polished_comments_fails_after_max_retries(self) -> None:
        """Test that after MAX_RETRIES, failure is recorded."""
        doc = _FakeDocument("Test content here")
        doc.Comments.set_fail_forever()  # Always fail

        log_parts: list[str] = []

        with patch(
            "backend.nodes.common_word_nodes.comment_writeback.time.sleep"
        ) as mock_sleep:
            result = write_polished_comments(
                doc=doc,
                polished_comments=[
                    {"reference_text": "content", "comment_text": "Great content!"},
                ],
                bound_start=0,
                bound_end=len(doc.text),
                log_parts=log_parts,
            )

        # Should fail after max retries
        assert result["added"] == 0
        assert result["failed"] == 1
        assert doc.Comments.Count == 0

        # Verify retry delays were called (2 retries = 2 sleeps)
        assert mock_sleep.call_count == 2

        # Verify failure reason is recorded
        assert len(result["issues"]) == 1
        assert result["issues"][0]["reason"] == "comment_add_failed"
        assert "RPC error" in result["issues"][0]["error"]

    def test_write_polished_comments_no_retry_on_immediate_success(self) -> None:
        """Test that when Comments.Add succeeds immediately, no retries occur."""
        doc = _FakeDocument("Test content here")
        # Default: no failures

        log_parts: list[str] = []

        with patch(
            "backend.nodes.common_word_nodes.comment_writeback.time.sleep"
        ) as mock_sleep:
            result = write_polished_comments(
                doc=doc,
                polished_comments=[
                    {"reference_text": "content", "comment_text": "Great content!"},
                ],
                bound_start=0,
                bound_end=len(doc.text),
                log_parts=log_parts,
            )

        # Should succeed immediately
        assert result["added"] == 1
        assert result["failed"] == 0

        # No retries = no sleep calls
        mock_sleep.assert_not_called()


# =============================================================================
# Test Group 2: Table-Oriented Reference Matching
# =============================================================================


class TestCommentWritebackTableMatching:
    """Tests for table-oriented reference matching with markdown-style rows."""

    def test_write_polished_comments_matches_markdown_table_row(self) -> None:
        """Test that markdown table rows like 'A | B' can match Word table cells."""
        # Create document where the pipe-separated text would be normalized
        doc = _FakeDocument("A B")  # After normalization "A | B" -> "A B"

        log_parts: list[str] = []

        result = write_polished_comments(
            doc=doc,
            polished_comments=[
                {"reference_text": "A | B", "comment_text": "Comment on row"},
            ],
            bound_start=0,
            bound_end=len(doc.text),
            log_parts=log_parts,
        )

        # Should find the text using table-style matching
        assert result["added"] == 1
        assert result["failed"] == 0
        assert doc.Comments.Count == 1
        assert doc.Comments(1).Text == "Comment on row"

    def test_write_polished_comments_falls_back_to_text_search(self) -> None:
        """Test that when table matching fails, it falls back to normal find."""
        # Document has plain text that won't match table-style normalization
        doc = _FakeDocument("Some normal text here")

        log_parts: list[str] = []

        result = write_polished_comments(
            doc=doc,
            polished_comments=[
                {"reference_text": "normal text", "comment_text": "Found it!"},
            ],
            bound_start=0,
            bound_end=len(doc.text),
            log_parts=log_parts,
        )

        # Should find using normal text search
        assert result["added"] == 1
        assert result["failed"] == 0

    def test_write_polished_comments_table_style_with_multiple_pipes(self) -> None:
        """Test table-style matching with multiple pipes and whitespace."""
        # Normalized: "Cell 1 | Cell 2 | Cell 3" -> "Cell 1 Cell 2 Cell 3"
        doc = _FakeDocument("Cell 1 Cell 2 Cell 3")

        log_parts: list[str] = []

        result = write_polished_comments(
            doc=doc,
            polished_comments=[
                {
                    "reference_text": "Cell 1 | Cell 2 | Cell 3",
                    "comment_text": "Table row!",
                },
            ],
            bound_start=0,
            bound_end=len(doc.text),
            log_parts=log_parts,
        )

        assert result["added"] == 1
        assert doc.Comments.Count == 1

    def test_write_polished_comments_exact_match_priority(self) -> None:
        """Test that exact matches are tried before table-style normalization."""
        # Document has exact match for pipe-separated text
        doc = _FakeDocument("A | B")  # Exact match exists

        log_parts: list[str] = []

        result = write_polished_comments(
            doc=doc,
            polished_comments=[
                {"reference_text": "A | B", "comment_text": "Comment!"},
            ],
            bound_start=0,
            bound_end=len(doc.text),
            log_parts=log_parts,
        )

        # Should find the exact match first
        assert result["added"] == 1
        assert doc.Comments.Count == 1

    def test_write_polished_comments_normalized_match_handles_punctuation_and_newline(
        self,
    ) -> None:
        doc = _FakeDocument("功能：安全\r便捷、智能，运行稳定。")

        log_parts: list[str] = []

        result = write_polished_comments(
            doc=doc,
            polished_comments=[
                {
                    "reference_text": "安全、便捷、智能",
                    "comment_text": "建议删除：主观表述。",
                },
            ],
            bound_start=0,
            bound_end=len(doc.text),
            log_parts=log_parts,
        )

        assert result["added"] == 1
        assert result["failed"] == 0
        assert doc.Comments.Count == 1
        assert doc.Comments(1).Range.Start == doc.text.find("安全")
        assert any("已通过规范化匹配添加" in part for part in log_parts)

    def test_write_polished_comments_uses_full_document_unique_normalized_fallback(
        self,
    ) -> None:
        doc = _FakeDocument("前置锚点\r目标正文：最\r优配置。\r后置锚点")

        log_parts: list[str] = []

        result = write_polished_comments(
            doc=doc,
            polished_comments=[
                {
                    "reference_text": "最优",
                    "comment_text": "建议删除：广告法风险表述。",
                },
            ],
            bound_start=0,
            bound_end=len("前置锚点\r"),
            log_parts=log_parts,
        )

        assert result["added"] == 1
        assert result["failed"] == 0
        assert doc.Comments.Count == 1
        assert doc.Comments(1).Range.Start == doc.text.find("最")
        assert any("已通过全文唯一匹配添加" in part for part in log_parts)

    def test_write_polished_comments_does_not_use_ambiguous_normalized_match(
        self,
    ) -> None:
        doc = _FakeDocument("稳 定 性要求，另有稳 定 性说明。")

        log_parts: list[str] = []

        result = write_polished_comments(
            doc=doc,
            polished_comments=[
                {
                    "reference_text": "稳定性",
                    "comment_text": "建议删除：主观表述。",
                },
            ],
            bound_start=0,
            bound_end=len(doc.text),
            log_parts=log_parts,
        )

        assert result["added"] == 0
        assert result["failed"] == 1
        assert doc.Comments.Count == 0
        assert result["issues"][0]["reason"] == "normalized_reference_not_unique"
        assert any("规范化匹配在锚点范围命中多处" in part for part in log_parts)


class TestBuildSearchTexts:
    """Tests for the _build_search_texts helper function."""

    def test_build_search_texts_plain_text(self) -> None:
        """Test that plain text is returned as-is."""
        result = _build_search_texts("normal text")
        assert "normal text" in result

    def test_build_search_texts_detects_pipe_separator(self) -> None:
        """Test that pipe separator triggers table-style normalization."""
        result = _build_search_texts("A | B")
        # Should have the pipe-stripped version
        assert "A B" in result

    def test_build_search_texts_multiple_pipes(self) -> None:
        """Test multiple pipes are handled correctly."""
        result = _build_search_texts("Header | Value 1 | Value 2")
        # Should normalize to space-separated
        assert "Header Value 1 Value 2" in result

    def test_build_search_texts_extra_whitespace(self) -> None:
        """Test extra whitespace around pipes is collapsed."""
        result = _build_search_texts("A  |  B  |  C")
        assert "A B C" in result

    def test_build_search_texts_no_pipe_no_extra_variants(self) -> None:
        """Test that text without pipes doesn't get extra variants."""
        result = _build_search_texts("normal text without pipes")
        # Should only have original and newline variants
        assert len(result) <= 2

    def test_build_search_texts_empty_string(self) -> None:
        """Test handling of empty string."""
        result = _build_search_texts("")
        # Empty string is filtered out to avoid empty searches
        assert result == []


# =============================================================================
# Test Group 3: Zero-Added Failure Detection
# =============================================================================


class TestCommentWritebackResultStructure:
    """Tests for result structure and failure reason preservation."""

    def test_write_polished_comments_result_contains_all_fields(self) -> None:
        """Test that result contains all expected fields."""
        doc = _FakeDocument("Test content")

        log_parts: list[str] = []

        result = write_polished_comments(
            doc=doc,
            polished_comments=[
                {"reference_text": "content", "comment_text": "Comment!"},
            ],
            bound_start=0,
            bound_end=len(doc.text),
            log_parts=log_parts,
        )

        # Verify all expected fields exist
        assert "total" in result
        assert "attempted" in result
        assert "added" in result
        assert "failed" in result
        assert "skipped" in result
        assert "issues" in result

        # Verify types
        assert isinstance(result["total"], int)
        assert isinstance(result["attempted"], int)
        assert isinstance(result["added"], int)
        assert isinstance(result["failed"], int)
        assert isinstance(result["skipped"], int)
        assert isinstance(result["issues"], list)

    def test_write_polished_comments_preserves_missing_reference_reason(self) -> None:
        """Test that empty reference text gets correct failure reason."""
        doc = _FakeDocument("Test content")

        log_parts: list[str] = []

        result = write_polished_comments(
            doc=doc,
            polished_comments=[
                {"reference_text": "", "comment_text": "Has comment but no ref"},
            ],
            bound_start=0,
            bound_end=len(doc.text),
            log_parts=log_parts,
        )

        assert result["skipped"] == 1
        assert len(result["issues"]) == 1
        assert result["issues"][0]["reason"] == "missing_reference_or_comment_text"

    def test_write_polished_comments_preserves_not_found_reason(self) -> None:
        """Test that unfound reference gets correct failure reason."""
        doc = _FakeDocument("Test content")

        log_parts: list[str] = []

        result = write_polished_comments(
            doc=doc,
            polished_comments=[
                {
                    "reference_text": "nonexistent text",
                    "comment_text": "Won't find this",
                },
            ],
            bound_start=0,
            bound_end=len(doc.text),
            log_parts=log_parts,
        )

        assert result["failed"] == 1
        assert len(result["issues"]) == 1
        assert result["issues"][0]["reason"] == "reference_text_not_found"

    def test_write_polished_comments_preserves_overlapping_reason(self) -> None:
        """Test that overlapping comment gets correct failure reason."""
        doc = _FakeDocument("Alpha content here")
        # Add existing comment on "Alpha"
        doc.Comments._items.append(_FakeComment(doc, 0, 5, "existing comment"))

        log_parts: list[str] = []

        result = write_polished_comments(
            doc=doc,
            polished_comments=[
                {"reference_text": "Alpha", "comment_text": "New comment"},
            ],
            bound_start=0,
            bound_end=len(doc.text),
            log_parts=log_parts,
        )

        assert result["skipped"] == 1
        assert len(result["issues"]) == 1
        assert result["issues"][0]["reason"] == "overlapping_comment_exists"

    def test_write_polished_comments_preserves_add_failed_reason(self) -> None:
        """Test that Comments.Add failure gets correct failure reason."""
        doc = _FakeDocument("Test content")
        doc.Comments.set_fail_forever()

        log_parts: list[str] = []

        with patch("backend.nodes.common_word_nodes.comment_writeback.time.sleep"):
            result = write_polished_comments(
                doc=doc,
                polished_comments=[
                    {"reference_text": "content", "comment_text": "Will fail"},
                ],
                bound_start=0,
                bound_end=len(doc.text),
                log_parts=log_parts,
            )

        assert result["failed"] == 1
        assert len(result["issues"]) == 1
        assert result["issues"][0]["reason"] == "comment_add_failed"

    def test_write_polished_comments_multiple_different_failures(self) -> None:
        """Test that multiple different failure reasons are all preserved."""
        doc = _FakeDocument("Alpha content")
        # Add existing comment
        doc.Comments._items.append(_FakeComment(doc, 0, 5, "existing"))
        doc.Comments.set_fail_forever()

        log_parts: list[str] = []

        with patch("backend.nodes.common_word_nodes.comment_writeback.time.sleep"):
            result = write_polished_comments(
                doc=doc,
                polished_comments=[
                    {"reference_text": "", "comment_text": "Empty ref"},  # missing ref
                    {
                        "reference_text": "Alpha",
                        "comment_text": "Overlap",
                    },  # overlapping
                    {
                        "reference_text": "content",
                        "comment_text": "Add fail",
                    },  # add fails
                    {
                        "reference_text": "nonexistent",
                        "comment_text": "Not found",
                    },  # not found
                ],
                bound_start=0,
                bound_end=len(doc.text),
                log_parts=log_parts,
            )

        # Verify all reasons are captured
        reasons = {issue["reason"] for issue in result["issues"]}
        assert "missing_reference_or_comment_text" in reasons
        assert "overlapping_comment_exists" in reasons
        assert "comment_add_failed" in reasons
        assert "reference_text_not_found" in reasons

        # Verify counts
        assert result["total"] == 4
        assert result["skipped"] == 2  # missing ref + overlapping
        assert result["failed"] == 2  # add failed + not found
        assert len(result["issues"]) == 4


# =============================================================================
# Original Existing Tests (Kept for backward compatibility)
# =============================================================================


class TestExistingCommentWriteback:
    """Original tests from before the hardened version."""

    def test_write_polished_comments_skips_overlapping_ranges_and_uses_later_match(
        self,
    ) -> None:
        doc = _FakeDocument("Alpha middle Alpha")
        doc.Comments._items.append(_FakeComment(doc, 0, 5, "existing"))
        log_parts: list[str] = []

        result = write_polished_comments(
            doc=doc,
            polished_comments=[
                {"reference_text": "Alpha", "comment_text": "new comment"},
            ],
            bound_start=0,
            bound_end=len(doc.text),
            log_parts=log_parts,
        )

        assert result["added"] == 1
        assert result["failed"] == 0
        assert result["skipped"] == 0
        assert doc.Comments.Count == 2
        assert doc.Comments(2).Range.Start == doc.text.rfind("Alpha")
        assert any("位置已存在批注" in part for part in log_parts)

    def test_write_polished_comments_supports_newline_matching_and_partial_failures(
        self,
    ) -> None:
        doc = _FakeDocument("Line1\rLine2 and Next")
        doc.Comments.fail_ranges.add((0, len("Line1\rLine2")))
        log_parts: list[str] = []

        result = write_polished_comments(
            doc=doc,
            polished_comments=[
                {"reference_text": "Line1\nLine2", "comment_text": "first comment"},
                {"reference_text": "Next", "comment_text": "second comment"},
            ],
            bound_start=0,
            bound_end=len(doc.text),
            log_parts=log_parts,
        )

        assert result["added"] == 1
        assert result["failed"] == 1
        assert result["skipped"] == 0
        assert doc.Comments.Count == 1
        assert doc.Comments(1).Range.Start == doc.text.find("Next")
        assert any("comment_add_failed=1" in part for part in log_parts)

    def test_write_polished_comments_reports_empty_and_unmatched_references(
        self,
    ) -> None:
        doc = _FakeDocument("Only visible text")
        log_parts: list[str] = []

        result = write_polished_comments(
            doc=doc,
            polished_comments=[
                {"reference_text": "", "comment_text": "missing ref"},
                {"reference_text": "Missing", "comment_text": "not found"},
            ],
            bound_start=0,
            bound_end=len(doc.text),
            log_parts=log_parts,
        )

        assert result["added"] == 0
        assert result["failed"] == 1
        assert result["skipped"] == 1
        assert {issue["reason"] for issue in result["issues"]} == {
            "missing_reference_or_comment_text",
            "reference_text_not_found",
        }
        assert any("missing_reference_or_comment_text=1" in part for part in log_parts)
        assert any("reference_text_not_found=1" in part for part in log_parts)


# =============================================================================
# Test Group 4: Duplicate Anchor Multi-Write Behavior
# =============================================================================


class TestCommentWritebackDuplicateAnchorMultiWrite:
    """Tests for duplicate anchor handling: write to all non-overlapping positions."""

    def test_write_polished_comments_writes_all_non_overlapping_duplicate_anchors(self) -> None:
        """锚点在多处出现且都没有批注时，对所有重复位置分别写入同一条批注。"""
        doc = _FakeDocument("开头配置项。中间配置项说明。结尾配置项。")
        log_parts: list[str] = []

        result = write_polished_comments(
            doc=doc,
            polished_comments=[
                {"reference_text": "配置项", "comment_text": "建议删除：主观表述。"},
            ],
            bound_start=0,
            bound_end=len(doc.text),
            log_parts=log_parts,
        )

        assert result["added"] == 3
        assert result["failed"] == 0
        assert doc.Comments.Count == 3
        # 三处批注内容一致
        for idx in range(1, 4):
            assert doc.Comments(idx).Text == "建议删除：主观表述。"
        assert any("已在 3 个未批注位置" in part for part in log_parts)

    def test_write_polished_comments_skips_overlapping_and_writes_remaining_duplicates(self) -> None:
        """重复锚点中已有批注的位置跳过，未批注的重复位置继续写入。"""
        doc = _FakeDocument("开头配置项。中间配置项说明。结尾配置项。")
        # 预先在第一个“配置项”位置添加批注
        first_pos = doc.text.find("配置项")
        doc.Comments._items.append(
            _FakeComment(doc, first_pos, first_pos + len("配置项"), "existing")
        )
        log_parts: list[str] = []

        result = write_polished_comments(
            doc=doc,
            polished_comments=[
                {"reference_text": "配置项", "comment_text": "建议删除：主观表述。"},
            ],
            bound_start=0,
            bound_end=len(doc.text),
            log_parts=log_parts,
        )

        # 已有 1 条，本条候选在另外 2 个未批注位置写入，不重复计入 skipped
        assert result["added"] == 2
        assert result["failed"] == 0
        assert doc.Comments.Count == 3

    def test_write_polished_comments_all_duplicate_positions_overlapped_counts_skipped(self) -> None:
        """所有重复位置都已存在批注时，计为 skipped。"""
        doc = _FakeDocument("配置项一 配置项二")
        pos1 = doc.text.find("配置项")
        pos2 = doc.text.rfind("配置项")
        doc.Comments._items.append(
            _FakeComment(doc, pos1, pos1 + len("配置项"), "existing-1")
        )
        doc.Comments._items.append(
            _FakeComment(doc, pos2, pos2 + len("配置项"), "existing-2")
        )
        log_parts: list[str] = []

        result = write_polished_comments(
            doc=doc,
            polished_comments=[
                {"reference_text": "配置项", "comment_text": "建议删除：主观表述。"},
            ],
            bound_start=0,
            bound_end=len(doc.text),
            log_parts=log_parts,
        )

        assert result["added"] == 0
        assert result["skipped"] == 1
        assert result["failed"] == 0
        assert doc.Comments.Count == 2
        assert result["issues"][0]["reason"] == "overlapping_comment_exists"

    def test_write_polished_comments_can_add_on_existing_normalized_anchor(self) -> None:
        """显式放宽时，规范化匹配到已有批注的锚点仍可追加批注。"""
        doc = _FakeDocument("A，B")
        doc.Comments._items.append(_FakeComment(doc, 0, len(doc.text), "existing"))
        log_parts: list[str] = []

        result = write_polished_comments(
            doc=doc,
            polished_comments=[
                {"reference_text": "A B", "comment_text": "追加批注"},
            ],
            bound_start=0,
            bound_end=len(doc.text),
            log_parts=log_parts,
            allow_existing_comments=True,
        )

        assert result["added"] == 1
        assert result["failed"] == 0
        assert result["skipped"] == 0
        assert doc.Comments.Count == 2
        assert doc.Comments(2).Text == "追加批注"
        assert any("规范化匹配添加" in part for part in log_parts)

    def test_write_polished_comments_markdown_pipe_row_matched_across_duplicates(self) -> None:
        """规范化匹配（Markdown pipe 行）仍能处理标点、换行、pipe 表格行。"""
        doc = _FakeDocument("A B 说明，另含 A B 结尾。")
        log_parts: list[str] = []

        result = write_polished_comments(
            doc=doc,
            polished_comments=[
                {"reference_text": "A | B", "comment_text": "表格行批注"},
            ],
            bound_start=0,
            bound_end=len(doc.text),
            log_parts=log_parts,
        )

        # 规范化后 "A B" 在两处出现，都写入
        assert result["added"] >= 1
        assert result["failed"] == 0


# =============================================================================
# Integration Test with gjgk_update_word
# =============================================================================


def test_gjgk_update_word_writes_comments_before_save(monkeypatch) -> None:
    """Test that gjgk_update_word calls write_polished_comments before saving."""
    events: list[object] = []
    fake_doc = _FakeDocument("x" * 120)

    monkeypatch.setattr(
        gjgk_update_word_module,
        "_build_insert_items",
        lambda _text: [{"type": "text", "line": "新的正文"}],
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "create_word_application",
        lambda **_kwargs: ("fake-word", True),
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "open_document_with_retry",
        lambda **_kwargs: fake_doc,
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "unprotect_document",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "find_anchor_range",
        lambda *_args, **_kwargs: (
            {"start": 10, "end": 15, "page": 1},
            {"start": 40, "end": 45, "page": 1},
        ),
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_resolve_gjgk_content_range",
        lambda **_kwargs: {
            "range_start": 20,
            "range_end": 30,
            "start_page": 1,
            "end_page": 1,
        },
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_delete_original_content",
        lambda *_args, **_kwargs: events.append("delete"),
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_trim_leading_layout_controls",
        lambda *_args, **_kwargs: 20,
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_find_first_insert_position_on_anchor_page",
        lambda *_args, **_kwargs: 20,
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_describe_range_state",
        lambda *_args, **_kwargs: "range-state",
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_set_collapsed_range",
        lambda insert_range, position: insert_range.SetRange(position, position),
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_ensure_insert_range",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_insert_text_line",
        lambda _doc, insert_range, line, **_kwargs: insert_range.SetRange(
            int(insert_range.Start) + len(line),
            int(insert_range.Start) + len(line),
        ),
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_reposition_insert_range_if_locked",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "cleanup_blank_paragraphs",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_visible_log",
        lambda *_args, **_kwargs: None,
    )
    def _fake_apply_comments(**kwargs):
        state = kwargs["state"]
        polished = tuple(state.get("polished_comments") or [])
        events.append(
            (
                "write_comments",
                polished,
                kwargs["bound_start"],
                kwargs["bound_end"],
            )
        )
        result = {
            "total": 1,
            "attempted": 1,
            "added": 1,
            "failed": 0,
            "skipped": 0,
            "issues": [],
        }
        summary = {
            "summary": "AI批注写入: 生成=1, 成功=1, 失败=0, 跳过=0",
            "generated": 1,
            "added": 1,
            "failed": 0,
            "skipped": 0,
            "warning": False,
        }
        return result, summary

    monkeypatch.setattr(
        gjgk_update_word_module,
        "apply_correction_and_ai_comments",
        _fake_apply_comments,
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "save_document_with_retry",
        lambda _doc, **_kwargs: events.append("save"),
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "close_word_application",
        lambda **_kwargs: None,
    )

    result = gjgk_update_word_module.gjgk_update_word(
        {
            "prepared_doc_path": "fake.docx",
            "polished_text": "新的正文",
            "polished_comments": [
                {"reference_text": "新的正文", "comment_text": "保留旧批注"},
            ],
            "insertion_before_text": "前锚点",
            "insertion_after_text": "后锚点",
        },
        config=None,
    )

    assert events[0] == "delete"
    assert events[1][0] == "write_comments"
    assert events[2] == "save"
    assert "共解析插入项 1 条" in result["insertion_log"]
    assert "文档已保存" in result["insertion_log"]


# =============================================================================
# Hard-Fail & Partial Success Tests for gjgk_update_word
# =============================================================================


def _patch_gjgk_node(monkeypatch, fake_doc, writeback_result):
    """Shared helper: monkeypatch all gjgk_update_word dependencies."""
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_build_insert_items",
        lambda _text: [{"type": "text", "line": "新的正文"}],
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "create_word_application",
        lambda **_kwargs: ("fake-word", True),
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "open_document_with_retry",
        lambda **_kwargs: fake_doc,
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "unprotect_document",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "find_anchor_range",
        lambda *_args, **_kwargs: (
            {"start": 10, "end": 15, "page": 1},
            {"start": 40, "end": 45, "page": 1},
        ),
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_resolve_gjgk_content_range",
        lambda **_kwargs: {
            "range_start": 20,
            "range_end": 30,
            "start_page": 1,
            "end_page": 1,
        },
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_delete_original_content",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_trim_leading_layout_controls",
        lambda *_args, **_kwargs: 20,
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_find_first_insert_position_on_anchor_page",
        lambda *_args, **_kwargs: 20,
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_describe_range_state",
        lambda *_args, **_kwargs: "range-state",
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_set_collapsed_range",
        lambda insert_range, position: insert_range.SetRange(position, position),
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_ensure_insert_range",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_insert_text_line",
        lambda _doc, insert_range, line, **_kwargs: insert_range.SetRange(
            int(insert_range.Start) + len(line),
            int(insert_range.Start) + len(line),
        ),
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_reposition_insert_range_if_locked",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "cleanup_blank_paragraphs",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "_visible_log",
        lambda *_args, **_kwargs: None,
    )
    def _fake_apply_comments(**kwargs):
        generated = 0
        try:
            generated = int((kwargs.get("state") or {}).get("generated_comment_count") or 0)
        except (TypeError, ValueError):
            generated = 0
        summary = {
            "summary": (
                f"AI批注写入: 生成={generated}, 成功={writeback_result.get('added', 0)}, "
                f"失败={writeback_result.get('failed', 0)}, 跳过={writeback_result.get('skipped', 0)}"
            ),
            "generated": generated,
            "added": writeback_result.get("added", 0),
            "failed": writeback_result.get("failed", 0),
            "skipped": writeback_result.get("skipped", 0),
            "warning": generated > 0 and writeback_result.get("failed", 0) > 0,
        }
        return writeback_result, summary

    monkeypatch.setattr(
        gjgk_update_word_module,
        "apply_correction_and_ai_comments",
        _fake_apply_comments,
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "save_document_with_retry",
        lambda _doc, **_kwargs: None,
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "close_word_application",
        lambda **_kwargs: None,
    )


def test_gjgk_update_word_warns_when_zero_of_n_comments_written(
    monkeypatch,
) -> None:
    """generated_comment_count > 0 but added == 0 → task completes with warning."""
    fake_doc = _FakeDocument("x" * 120)
    zero_added_result = {
        "total": 3,
        "attempted": 3,
        "added": 0,
        "failed": 3,
        "skipped": 0,
        "issues": [
            {
                "index": 1,
                "reason": "reference_text_not_found",
                "reference_text": "a",
                "comment_text": "c1",
            },
            {
                "index": 2,
                "reason": "reference_text_not_found",
                "reference_text": "b",
                "comment_text": "c2",
            },
            {
                "index": 3,
                "reason": "reference_text_not_found",
                "reference_text": "c",
                "comment_text": "c3",
            },
        ],
    }
    _patch_gjgk_node(monkeypatch, fake_doc, zero_added_result)

    progress_warnings: list[str] = []
    progress_errors: list[str] = []
    monkeypatch.setattr(
        gjgk_update_word_module.progress_log,
        "warning",
        lambda message, *args: progress_warnings.append(
            message % args if args else str(message)
        ),
    )
    monkeypatch.setattr(
        gjgk_update_word_module.progress_log,
        "error",
        lambda message, *args: progress_errors.append(message % args if args else str(message)),
    )

    result = gjgk_update_word_module.gjgk_update_word(
        {
            "prepared_doc_path": "fake.docx",
            "polished_text": "新的正文",
            "polished_comments": [
                {"reference_text": "a", "comment_text": "c1"},
            ],
            "generated_comment_count": 3,
            "insertion_before_text": "前锚点",
            "insertion_after_text": "后锚点",
        },
        config=None,
    )

    assert result["comment_writeback_result"] == {
        "summary": "AI批注写入: 生成=3, 成功=0, 失败=3, 跳过=0",
        "generated": 3,
        "added": 0,
        "failed": 3,
        "skipped": 0,
        "warning": True,
    }
    assert result["comment_writeback_added"] == 0
    assert result["comment_writeback_failed"] == 3
    assert progress_warnings == ["AI批注写入: 生成=3, 成功=0, 失败=3, 跳过=0"]
    assert progress_errors == []


def test_gjgk_update_word_partial_writeback_succeeds_with_summary(monkeypatch) -> None:
    """Partial writeback (added > 0, failed > 0) → task succeeds, state has summary."""
    fake_doc = _FakeDocument("x" * 120)
    partial_result = {
        "total": 3,
        "attempted": 3,
        "added": 2,
        "failed": 1,
        "skipped": 0,
        "issues": [
            {
                "index": 3,
                "reason": "reference_text_not_found",
                "reference_text": "z",
                "comment_text": "c3",
            },
        ],
    }
    _patch_gjgk_node(monkeypatch, fake_doc, partial_result)

    result = gjgk_update_word_module.gjgk_update_word(
        {
            "prepared_doc_path": "fake.docx",
            "polished_text": "新的正文",
            "polished_comments": [
                {"reference_text": "a", "comment_text": "c1"},
            ],
            "generated_comment_count": 3,
            "insertion_before_text": "前锚点",
            "insertion_after_text": "后锚点",
        },
        config=None,
    )

    # Task succeeds
    assert "insertion_log" in result
    # Summary is present in state
    assert (
        result["comment_writeback_summary"]
        == "AI批注写入: 生成=3, 成功=2, 失败=1, 跳过=0"
    )
    assert result["comment_writeback_added"] == 2
    assert result["comment_writeback_failed"] == 1
    assert result["comment_writeback_skipped"] == 0
    assert result["comment_writeback_result"]["warning"] is True


def test_gjgk_update_word_no_hard_fail_when_zero_generated(monkeypatch) -> None:
    """generated_comment_count == 0 → no hard-fail even if writeback result shows failures."""
    fake_doc = _FakeDocument("x" * 120)
    # Edge case: writeback returns failures but generated_count was 0 (e.g. generate_comments errored)
    no_comments_result = {
        "total": 0,
        "attempted": 0,
        "added": 0,
        "failed": 0,
        "skipped": 0,
        "issues": [],
    }
    _patch_gjgk_node(monkeypatch, fake_doc, no_comments_result)

    result = gjgk_update_word_module.gjgk_update_word(
        {
            "prepared_doc_path": "fake.docx",
            "polished_text": "新的正文",
            "polished_comments": [],
            "generated_comment_count": 0,
            "insertion_before_text": "前锚点",
            "insertion_after_text": "后锚点",
        },
        config=None,
    )

    # Task succeeds — no hard-fail
    assert "insertion_log" in result
    assert (
        result["comment_writeback_summary"]
        == "AI批注写入: 生成=0, 成功=0, 失败=0, 跳过=0"
    )
    assert result["comment_writeback_result"]["warning"] is False


def test_gjgk_update_word_hides_comment_progress_logs_in_verbose_edit_mode(monkeypatch) -> None:
    fake_doc = _FakeDocument("x" * 120)
    partial_result = {
        "total": 2,
        "attempted": 2,
        "added": 1,
        "failed": 1,
        "skipped": 0,
        "issues": [
            {
                "index": 2,
                "reason": "reference_text_not_found",
                "reference_text": "z",
                "comment_text": "c2",
            },
        ],
    }
    _patch_gjgk_node(monkeypatch, fake_doc, partial_result)

    progress_messages: list[str] = []
    progress_warnings: list[str] = []
    progress_errors: list[str] = []

    monkeypatch.setattr(
        gjgk_update_word_module.progress_log,
        "info",
        lambda message, *args: progress_messages.append(message % args if args else str(message)),
    )
    monkeypatch.setattr(
        gjgk_update_word_module.progress_log,
        "error",
        lambda message, *args: progress_errors.append(message % args if args else str(message)),
    )
    monkeypatch.setattr(
        gjgk_update_word_module.progress_log,
        "warning",
        lambda message, *args: progress_warnings.append(
            message % args if args else str(message)
        ),
    )

    def _fake_apply_inline_style_fragments(**kwargs):
        progress_logger = kwargs.get("progress_logger")
        message = '步骤6：样式回填成功[1/1] 加粗 | "原条款" -> "新条款"'
        kwargs["log_parts"].append(message)
        if callable(progress_logger):
            progress_logger(message)
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

    monkeypatch.setattr(
        gjgk_update_word_module,
        "apply_inline_style_fragments",
        _fake_apply_inline_style_fragments,
    )

    result = gjgk_update_word_module.gjgk_update_word(
        {
            "prepared_doc_path": "fake.docx",
            "polished_text": "新的正文",
            "polished_comments": [
                {"reference_text": "a", "comment_text": "c1"},
            ],
            "generated_comment_count": 2,
            "inline_style_fragments": [{"source_text": "原条款"}],
            "verbose_style_progress_logs": True,
            "suppress_comment_progress_logs": True,
            "insertion_before_text": "前锚点",
            "insertion_after_text": "后锚点",
        },
        config=None,
    )

    assert any("样式回填成功[1/1]" in message for message in progress_messages)
    assert not any("AI批注写入" in message for message in progress_messages)
    assert progress_warnings == []
    assert progress_errors == []
    assert result["comment_writeback_summary"] == "AI批注写入: 生成=2, 成功=1, 失败=1, 跳过=0"
    assert result["style_writeback_result"] == {
        "extracted": 1,
        "attempted": 1,
        "applied": 1,
        "skipped": 0,
        "failed": 0,
        "issues": [],
        "applied_by_style": {"bold": 1},
        "skipped_by_reason": {},
    }
    assert result["style_writeback_summary"] == (
        "样式回填: 抽取=1, 尝试=1, 成功=1, 跳过=0, 失败=0; 命中样式: 加粗=1"
    )


def test_gjgk_update_word_applies_inline_styles_with_resolved_bounds_and_summary(
    monkeypatch,
) -> None:
    fake_doc = _FakeDocument("x" * 120)
    writeback_result = {
        "total": 0,
        "attempted": 0,
        "added": 0,
        "failed": 0,
        "skipped": 0,
        "issues": [],
    }
    style_result = {
        "extracted": 1,
        "attempted": 1,
        "applied": 1,
        "skipped": 0,
        "failed": 0,
        "issues": [],
        "applied_by_style": {"bold": 1},
        "skipped_by_reason": {},
    }
    style_calls: list[dict] = []
    _patch_gjgk_node(monkeypatch, fake_doc, writeback_result)

    def _fake_apply_inline_style_fragments(**kwargs):
        style_calls.append(kwargs)
        return style_result

    monkeypatch.setattr(
        gjgk_update_word_module,
        "apply_inline_style_fragments",
        _fake_apply_inline_style_fragments,
    )
    monkeypatch.setattr(
        gjgk_update_word_module,
        "summarize_style_writeback_result",
        lambda _result: "样式摘要",
    )

    result = gjgk_update_word_module.gjgk_update_word(
        {
            "prepared_doc_path": "fake.docx",
            "polished_text": "新的正文",
            "polished_comments": [],
            "generated_comment_count": 0,
            "inline_style_fragments": [{"source_text": "原条款"}],
            "insertion_before_text": "前锚点",
            "insertion_after_text": "后锚点",
        },
        config=None,
    )

    assert len(style_calls) == 1
    assert style_calls[0]["doc"] is fake_doc
    assert style_calls[0]["inline_style_fragments"] == [{"source_text": "原条款"}]
    assert style_calls[0]["bound_start"] == 20
    assert style_calls[0]["bound_end"] == 40
    assert style_calls[0]["step_label"] == "步骤6"
    assert result["style_writeback_result"] == style_result
    assert result["style_writeback_summary"] == "样式摘要"


def test_gjgk_update_word_keeps_comment_progress_logs_outside_edit_verbose_mode(monkeypatch) -> None:
    fake_doc = _FakeDocument("x" * 120)
    partial_result = {
        "total": 2,
        "attempted": 2,
        "added": 1,
        "failed": 1,
        "skipped": 0,
        "issues": [],
    }
    _patch_gjgk_node(monkeypatch, fake_doc, partial_result)

    progress_messages: list[str] = []
    progress_warnings: list[str] = []
    monkeypatch.setattr(
        gjgk_update_word_module.progress_log,
        "info",
        lambda message, *args: progress_messages.append(message % args if args else str(message)),
    )
    monkeypatch.setattr(
        gjgk_update_word_module.progress_log,
        "warning",
        lambda message, *args: progress_warnings.append(
            message % args if args else str(message)
        ),
    )

    result = gjgk_update_word_module.gjgk_update_word(
        {
            "prepared_doc_path": "fake.docx",
            "polished_text": "新的正文",
            "polished_comments": [
                {"reference_text": "a", "comment_text": "c1"},
            ],
            "generated_comment_count": 2,
            "insertion_before_text": "前锚点",
            "insertion_after_text": "后锚点",
        },
        config=None,
    )

    assert not any("AI批注写入" in message for message in progress_messages)
    assert progress_warnings == ["AI批注写入: 生成=2, 成功=1, 失败=1, 跳过=0"]
    assert result["comment_writeback_summary"] == "AI批注写入: 生成=2, 成功=1, 失败=1, 跳过=0"
