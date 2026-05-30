from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain_core.messages import AIMessage, ToolMessage

from backend.agents.comments import (
    COMMENT_AGENT_NODE,
    VALIDATE_COMMENT_REFERENCES_TOOL,
    WRITE_VALIDATED_COMMENTS_TOOL,
    create_comment_agent_tools,
    create_comment_agent_runner,
    CommentAgentToolContext,
    CommentAgentToolSnapshot,
    run_comment_agent,
    validate_comment_reference_candidates,
    write_validated_comment_candidates_to_word,
)
from backend.agents.comments import comment_agent as comment_agent_module

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

    @property
    def Count(self) -> int:
        return len(self._items)

    def __call__(self, index: int) -> _FakeComment:
        return self._items[index - 1]

    def Add(self, Range, Text: str) -> None:
        self._items.append(
            _FakeComment(
                self._doc,
                int(Range.Start),
                int(Range.End),
                str(Text),
            )
        )

class _FakeDocument:
    def __init__(self, text: str) -> None:
        self.text = text
        self.Comments = _FakeCommentsCollection(self)
        self.Content = SimpleNamespace(End=len(text))

    def Range(self, start: int, end: int) -> _FakeRange:
        return _FakeRange(self, start, end)

def test_create_comment_agent_runner_uses_named_agent_and_tool_limits(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_create_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(comment_agent_module, "create_agent", fake_create_agent)
    monkeypatch.setattr(
        comment_agent_module,
        "create_generation_chat_model",
        lambda provider: f"model:{provider}",
    )

    runner = create_comment_agent_runner("deepseek", tools=[])

    assert runner is not None
    assert captured["model"] == "model:deepseek"
    assert captured["tools"] == []
    assert captured["name"] == COMMENT_AGENT_NODE
    middleware = captured["middleware"]
    assert all(isinstance(item, ToolCallLimitMiddleware) for item in middleware)
    assert [(item.tool_name, item.run_limit) for item in middleware] == [
        (VALIDATE_COMMENT_REFERENCES_TOOL, 2),
        (WRITE_VALIDATED_COMMENTS_TOOL, 1),
    ]

def test_validate_allows_ai_to_change_only_reference_text_from_polished_text() -> None:
    result = validate_comment_reference_candidates(
        initial_comments=[
            {
                "reference_text": "原厂授权",
                "comment_text": "建议提示：不得要求原厂授权函。",
            }
        ],
        proposed_comments=[
            {
                "reference_text": "投标人须提供原厂授权函",
                "comment_text": "建议提示：不得要求原厂授权函。",
            }
        ],
        polished_text="投标人须提供原厂授权函，并承诺售后。",
    )

    assert result.passed_count == 1
    assert result.failed_count == 0
    assert result.passed[0].index == 1
    assert result.passed[0].original_reference_text == "原厂授权"
    assert result.passed[0].reference_text == "投标人须提供原厂授权函"
    assert result.passed[0].start == 0

def test_validate_rejects_comment_text_changes_with_feedback() -> None:
    result = validate_comment_reference_candidates(
        initial_comments=[
            {
                "reference_text": "原厂授权",
                "comment_text": "建议提示：不得要求原厂授权函。",
            }
        ],
        proposed_comments=[
            {
                "reference_text": "投标人须提供原厂授权函",
                "comment_text": "建议删除：删除原厂授权函要求。",
            }
        ],
        polished_text="投标人须提供原厂授权函，并承诺售后。",
    )

    assert result.passed_count == 0
    assert result.failed_count == 1
    failure = result.failed[0]
    assert failure.index == 1
    assert failure.reason == "comment_text_changed"
    assert failure.original_reference_text == "原厂授权"
    assert "投标人须提供原厂授权函" in failure.candidate_fragments[0]

def test_validate_tool_seeds_initial_candidates_in_generation_mode() -> None:
    context = CommentAgentToolContext(
        initial_comments=[],
        polished_text="投标人须提供原厂授权函，并承诺售后。",
        allow_comment_generation=True,
    )
    validate_tool = next(
        tool
        for tool in create_comment_agent_tools(context)
        if tool.name == VALIDATE_COMMENT_REFERENCES_TOOL
    )

    payload = validate_tool.invoke(
        {
            "proposed_comments": [
                {
                    "reference_text": "投标人须提供原厂授权函",
                    "comment_text": "建议提示：不得要求原厂授权函。",
                }
            ]
        }
    )

    assert context.initial_comments == [
        {
            "reference_text": "投标人须提供原厂授权函",
            "comment_text": "建议提示：不得要求原厂授权函。",
        }
    ]
    assert payload["passed"][0]["reference_text"] == "投标人须提供原厂授权函"
    assert payload["passed"][0]["comment_text"] == "建议提示：不得要求原厂授权函。"

def test_validate_uses_only_polished_text_for_anchor_lookup() -> None:
    result = validate_comment_reference_candidates(
        initial_comments=[
            {
                "reference_text": "原厂授权函",
                "comment_text": "建议提示：不得要求原厂授权函。",
            }
        ],
        proposed_comments=[
            {
                "reference_text": "原厂授权函",
                "comment_text": "建议提示：不得要求原厂授权函。",
            }
        ],
        polished_text="这里只描述售后服务，没有目标锚点。",
    )

    assert result.failed_count == 1
    assert result.failed[0].reason == "reference_text_not_found_in_polished_text"
    assert result.failed[0].candidate_fragments

def test_write_tool_revalidates_and_rejects_comment_text_changes() -> None:
    doc = _FakeDocument("投标人须提供原厂授权函，并承诺售后。")

    validation, writeback = write_validated_comment_candidates_to_word(
        doc=doc,
        initial_comments=[
            {
                "reference_text": "原厂授权",
                "comment_text": "建议提示：不得要求原厂授权函。",
            }
        ],
        proposed_comments=[
            {
                "reference_text": "投标人须提供原厂授权函",
                "comment_text": "建议删除：删除原厂授权函要求。",
            }
        ],
        polished_text=doc.text,
        bound_start=0,
        bound_end=len(doc.text),
    )

    assert validation.failed_count == 1
    assert writeback["added"] == 0
    assert writeback["failed"] == 1
    assert writeback["issues"][0]["reason"] == "comment_text_changed"
    assert doc.Comments.Count == 0

def test_write_tool_adds_only_validated_anchor_inside_word_bound() -> None:
    doc = _FakeDocument("开头。投标人须提供原厂授权函，并承诺售后。结尾。")
    start = doc.text.index("投标人")
    end = doc.text.index("结尾")

    validation, writeback = write_validated_comment_candidates_to_word(
        doc=doc,
        initial_comments=[
            {
                "reference_text": "原厂授权",
                "comment_text": "建议提示：不得要求原厂授权函。",
            }
        ],
        proposed_comments=[
            {
                "reference_text": "投标人须提供原厂授权函",
                "comment_text": "建议提示：不得要求原厂授权函。",
            }
        ],
        polished_text="投标人须提供原厂授权函，并承诺售后。",
        bound_start=start,
        bound_end=end,
    )

    assert validation.passed_count == 1
    assert writeback["attempted"] == 1
    assert writeback["added"] == 1
    assert writeback["failed"] == 0
    assert doc.Comments.Count == 1
    assert doc.Comments(1).Text == "建议提示：不得要求原厂授权函。"

def test_write_tool_counts_existing_comment_as_skipped() -> None:
    doc = _FakeDocument("投标人须提供原厂授权函，并承诺售后。")
    doc.Comments._items.append(_FakeComment(doc, 0, len("投标人须提供原厂授权函"), "existing"))

    _validation, writeback = write_validated_comment_candidates_to_word(
        doc=doc,
        initial_comments=[
            {
                "reference_text": "原厂授权",
                "comment_text": "建议提示：不得要求原厂授权函。",
            }
        ],
        proposed_comments=[
            {
                "reference_text": "投标人须提供原厂授权函",
                "comment_text": "建议提示：不得要求原厂授权函。",
            }
        ],
        polished_text=doc.text,
        bound_start=0,
        bound_end=len(doc.text),
    )

    assert writeback["added"] == 0
    assert writeback["failed"] == 0
    assert writeback["skipped"] == 1
    assert writeback["issues"][0]["reason"] == "overlapping_comment_exists"
    assert doc.Comments.Count == 1

def test_write_validated_comments_tool_submits_candidates_without_touching_word_doc() -> None:
    doc = _FakeDocument("投标人须提供原厂授权函，并承诺售后。")
    context = CommentAgentToolContext(
        initial_comments=[
            {
                "reference_text": "原厂授权",
                "comment_text": "建议提示：不得要求原厂授权函。",
            }
        ],
        polished_text=doc.text,
    )
    write_tool = next(
        tool
        for tool in create_comment_agent_tools(context)
        if tool.name == WRITE_VALIDATED_COMMENTS_TOOL
    )

    payload = write_tool.invoke(
        {
            "proposed_comments": [
                {
                    "reference_text": "投标人须提供原厂授权函",
                    "comment_text": "建议提示：不得要求原厂授权函。",
                }
            ]
        }
    )

    assert payload["submitted"] is True
    assert payload["runtime_writeback"] == "deferred_to_graph_node_thread"
    assert context.final_proposed_comments[0]["reference_text"] == "投标人须提供原厂授权函"
    assert len(context.tool_snapshots) == 0
    assert context.writeback_result is None
    assert doc.Comments.Count == 0

def test_run_comment_agent_pushes_tool_snapshots_and_writes_word_after_runner(tmp_path) -> None:
    doc = _FakeDocument("投标人须提供原厂授权函，并承诺售后。")
    audit_path = tmp_path / "comment-agent-audit.json"

    class FakeRunner:
        def stream(self, _payload, config, **_kwargs):
            context = config["configurable"]["comment_agent_tool_context"]
            proposed = [
                {
                    "reference_text": "投标人须提供原厂授权函",
                    "comment_text": "建议提示：不得要求原厂授权函。",
                }
            ]
            yield AIMessage(content="开始校验批注锚点")
            assert doc.Comments.Count == 0
            context.final_proposed_comments = [
                {
                    "reference_text": proposed[0]["reference_text"],
                    "comment_text": proposed[0]["comment_text"],
                }
            ]
            validation = validate_comment_reference_candidates(
                initial_comments=context.initial_comments,
                proposed_comments=proposed,
                polished_text=context.polished_text,
            )
            context.validation_results.append(validation.model_dump(mode="json"))
            context.tool_snapshots.append(
                CommentAgentToolSnapshot(
                    round=1,
                    proposed_comments=context.final_proposed_comments,
                    validation=validation,
                )
            )
            yield ToolMessage(content="工具内部输出不应展示", tool_call_id="tool-1")
            yield AIMessage(content="批注锚点校验完成")

    events = []
    result = run_comment_agent(
        initial_comments=[
            {
                "reference_text": "原厂授权",
                "comment_text": "建议提示：不得要求原厂授权函。",
            }
        ],
        polished_text=doc.text,
        doc=doc,
        bound_start=0,
        bound_end=len(doc.text),
        task_id="task-1",
        runner=FakeRunner(),
        step_callback=events.append,
        audit_log_path=audit_path,
    )

    assert result.ai_messages == ["开始校验批注锚点", "批注锚点校验完成"]
    assert not any(event.content in result.ai_messages for event in events)
    assert events[0].step_type == "tool_snapshot"
    assert events[0].comment_agent["phase"] == "validation_round"
    assert events[0].comment_agent["rounds"][0]["label"] == "第 1 轮锚点校验"
    assert "第 1 轮锚点校验" in str(events[0].content)
    assert "投标人须提供原厂授权函" not in str(events[0].content)
    assert events[0].comment_agent["rounds"][0]["passed"] == 1
    assert events[0].comment_agent["rounds"][0]["highlights"] == []
    assert events[-1].node == COMMENT_AGENT_NODE
    assert events[-1].step_type == "final"
    assert events[-1].is_complete is True
    assert events[-1].comment_agent["phase"] == "final"
    assert events[-1].comment_agent["final_validation"]["passed"] == 1
    assert events[-1].comment_agent["writeback"]["added"] == 1
    assert "comment_agent 最终写入统计" in str(events[-1].content)
    assert doc.Comments.Count == 1

    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["task_id"] == "task-1"
    assert audit["initial_comments"][0]["comment_text"] == "建议提示：不得要求原厂授权函。"
    assert audit["ai_messages"] == result.ai_messages
    assert audit["tool_snapshots"][0]["validation"]["passed"][0]["reference_text"] == "投标人须提供原厂授权函"
    assert audit["final_proposed_comments"][0]["reference_text"] == "投标人须提供原厂授权函"
    assert audit["final_passed"][0]["reference_text"] == "投标人须提供原厂授权函"
    assert audit["writeback_result"]["added"] == 1

def test_run_comment_agent_can_generate_candidates_in_generation_mode(tmp_path) -> None:
    doc = _FakeDocument("投标人须提供原厂授权函，并承诺售后。")
    audit_path = tmp_path / "comment-agent-audit.json"

    class FakeRunner:
        def stream(self, payload, config, **_kwargs):
            context = config["configurable"]["comment_agent_tool_context"]
            tools = {
                tool.name: tool
                for tool in create_comment_agent_tools(context)
            }
            assert "请直接接手补充批注任务" in str(payload["messages"][0].content)
            proposed = [
                {
                    "reference_text": "投标人须提供原厂授权函",
                    "comment_text": "建议提示：不得要求原厂授权函。",
                }
            ]
            yield AIMessage(content="开始生成补充批注")
            validation = tools[VALIDATE_COMMENT_REFERENCES_TOOL].invoke(
                {"proposed_comments": proposed}
            )
            assert validation["passed"][0]["reference_text"] == "投标人须提供原厂授权函"
            tools[WRITE_VALIDATED_COMMENTS_TOOL].invoke({"proposed_comments": proposed})
            yield AIMessage(content="补充批注生成完成")

    events = []
    result = run_comment_agent(
        initial_comments=[],
        polished_text=doc.text,
        doc=doc,
        bound_start=0,
        bound_end=len(doc.text),
        task_id="task-2",
        runner=FakeRunner(),
        step_callback=events.append,
        audit_log_path=audit_path,
        allow_comment_generation=True,
        comment_generation_instruction="请仅依据修改文本生成纯净 JSON 数组。",
    )

    assert result.ai_messages == ["开始生成补充批注", "补充批注生成完成"]
    assert result.final_proposed_comments[0]["reference_text"] == "投标人须提供原厂授权函"
    assert result.writeback_result["added"] == 1
    assert doc.Comments.Count == 1
    assert events[-1].comment_agent["writeback"]["added"] == 1
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["initial_comments"][0]["reference_text"] == "投标人须提供原厂授权函"
    assert audit["final_proposed_comments"][0]["reference_text"] == "投标人须提供原厂授权函"

def test_run_comment_agent_shows_two_validation_rounds_and_silent_final_recheck(tmp_path) -> None:
    doc = _FakeDocument("7.投标人须提供售后服务承诺。")
    audit_path = tmp_path / "comment-agent-audit.json"

    class FakeRunner:
        def stream(self, _payload, config, **_kwargs):
            context = config["configurable"]["comment_agent_tool_context"]
            validation_1 = validate_comment_reference_candidates(
                initial_comments=context.initial_comments,
                proposed_comments=[
                    {
                        "reference_text": "★7.投标人须提供售后服务承诺",
                        "comment_text": "建议提示：不得设置星号条款。",
                    }
                ],
                polished_text=context.polished_text,
            )
            context.validation_results.append(validation_1.model_dump(mode="json"))
            context.tool_snapshots.append(
                CommentAgentToolSnapshot(
                    round=1,
                    proposed_comments=[
                        {
                            "reference_text": "★7.投标人须提供售后服务承诺",
                            "comment_text": "建议提示：不得设置星号条款。",
                        }
                    ],
                    validation=validation_1,
                )
            )
            yield ToolMessage(content="round-1", tool_call_id="tool-1")

            final_comments = [
                {
                    "reference_text": "7.投标人须提供售后服务承诺",
                    "comment_text": "建议提示：不得设置星号条款。",
                }
            ]
            validation_2 = validate_comment_reference_candidates(
                initial_comments=context.initial_comments,
                proposed_comments=final_comments,
                polished_text=context.polished_text,
            )
            context.validation_results.append(validation_2.model_dump(mode="json"))
            context.tool_snapshots.append(
                CommentAgentToolSnapshot(
                    round=2,
                    proposed_comments=final_comments,
                    validation=validation_2,
                )
            )
            context.final_proposed_comments = final_comments
            yield ToolMessage(content="round-2", tool_call_id="tool-2")

    events = []
    result = run_comment_agent(
        initial_comments=[
            {
                "reference_text": "★7.投标人须提供售后服务承诺",
                "comment_text": "建议提示：不得设置星号条款。",
            }
        ],
        polished_text=doc.text,
        doc=doc,
        bound_start=0,
        bound_end=len(doc.text),
        task_id="task-5",
        runner=FakeRunner(),
        step_callback=events.append,
        audit_log_path=audit_path,
    )

    visible_round_events = [event for event in events if event.step_type == "tool_snapshot"]
    assert len(visible_round_events) == 2
    assert visible_round_events[0].comment_agent["rounds"][-1]["label"] == "第 1 轮锚点校验"
    assert visible_round_events[0].comment_agent["rounds"][-1]["failed"] == 1
    assert visible_round_events[1].comment_agent["rounds"][-1]["label"] == "第 2 轮修复复核"
    assert visible_round_events[1].comment_agent["rounds"][-1]["highlights"][0]["status"] == "已修复"
    assert visible_round_events[1].comment_agent["rounds"][-1]["highlights"][0]["reference_text"] == "7.投标人须提供售后服务承诺"
    assert events[-1].comment_agent["phase"] == "final"
    assert len(events[-1].comment_agent["rounds"]) == 2
    assert events[-1].comment_agent["final_validation"]["passed"] == 1
    assert result.writeback_result["added"] == 1
    assert doc.Comments.Count == 1
