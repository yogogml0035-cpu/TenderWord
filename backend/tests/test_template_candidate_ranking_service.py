from __future__ import annotations

from backend.services.template_candidate_ranking_service import (
    TemplateCandidateRankingService,
)


def _candidate(tendername: str, yxj: str) -> dict[str, object]:
    return {
        "tenderno": f"NO-{tendername}",
        "tendername": tendername,
        "tname": "上海市中医医院",
        "bm": "采购处",
        "hytype": "医疗行业",
        "tendertype": "询价采购",
        "hwlx": "货物",
        "yxj": yxj,
        "zbr": "张三",
        "xbr": "李四",
        "year": 2026,
        "fsg": None,
        "shener": None,
        "selectable": True,
        "blocked_reason": None,
    }


def _run_async(coro):
    try:
        coro.send(None)
    except StopIteration as exc:
        return exc.value
    raise AssertionError("Coroutine yielded unexpectedly during test execution")


def test_rank_candidates_sorts_priority_ascending_and_invalid_last():
    service = TemplateCandidateRankingService()

    result = _run_async(service.rank_candidates(
        candidates=[
            _candidate("优先级2-A", "2"),
            _candidate("优先级1-A", "1"),
            _candidate("无优先级", ""),
            _candidate("优先级1-B", "1"),
        ],
        project_name=None,
    ))

    assert [item["tendername"] for item in result.candidates] == [
        "优先级1-A",
        "优先级1-B",
        "优先级2-A",
        "无优先级",
    ]
    assert result.ranking.mode == "priority_only"
    assert result.ranking.reason == "project_name_missing"


def test_rank_candidates_skips_ai_when_no_tied_priority():
    service = TemplateCandidateRankingService()

    result = _run_async(service.rank_candidates(
        candidates=[
            _candidate("优先级3", "3"),
            _candidate("优先级1", "1"),
            _candidate("优先级2", "2"),
        ],
        project_name="细胞电转仪",
    ))

    assert [item["tendername"] for item in result.candidates] == [
        "优先级1",
        "优先级2",
        "优先级3",
    ]
    assert result.ranking.applied is False
    assert result.ranking.reason == "no_tied_priority"


def test_rank_candidates_applies_ai_within_same_priority_group(monkeypatch):
    service = TemplateCandidateRankingService()

    async def _fake_llm(*_args, **_kwargs):
        return "[1, 0]"

    monkeypatch.setattr(
        "backend.services.template_candidate_ranking_service.stream_llm_completion",
        _fake_llm,
    )

    result = _run_async(service.rank_candidates(
        candidates=[
            _candidate("胸骨锯套装", "1"),
            _candidate("细胞电转仪", "1"),
            _candidate("高速冷冻离心机", "2"),
        ],
        project_name="细胞电转仪",
    ))

    assert [item["tendername"] for item in result.candidates] == [
        "细胞电转仪",
        "胸骨锯套装",
        "高速冷冻离心机",
    ]
    assert result.ranking.applied is True
    assert result.ranking.reason == "ai_ranked"


def test_rank_candidates_falls_back_when_ai_output_invalid(monkeypatch):
    service = TemplateCandidateRankingService()

    async def _fake_llm(*_args, **_kwargs):
        return "[0, 0]"

    monkeypatch.setattr(
        "backend.services.template_candidate_ranking_service.stream_llm_completion",
        _fake_llm,
    )

    result = _run_async(service.rank_candidates(
        candidates=[
            _candidate("胸骨锯套装", "1"),
            _candidate("细胞电转仪", "1"),
        ],
        project_name="细胞电转仪",
    ))

    assert [item["tendername"] for item in result.candidates] == [
        "胸骨锯套装",
        "细胞电转仪",
    ]
    assert result.ranking.applied is False
    assert result.ranking.reason == "ai_failed"


def test_rank_candidates_keeps_other_groups_when_one_ai_group_fails(monkeypatch):
    service = TemplateCandidateRankingService()
    responses = iter(("[1, 0]", "[0, 0]"))

    async def _fake_llm(*_args, **_kwargs):
        return next(responses)

    monkeypatch.setattr(
        "backend.services.template_candidate_ranking_service.stream_llm_completion",
        _fake_llm,
    )

    result = _run_async(service.rank_candidates(
        candidates=[
            _candidate("胸骨锯套装", "1"),
            _candidate("细胞电转仪", "1"),
            _candidate("多功能酶标仪", "2"),
            _candidate("细胞自动计数仪", "2"),
        ],
        project_name="细胞电转仪",
    ))

    assert [item["tendername"] for item in result.candidates] == [
        "细胞电转仪",
        "胸骨锯套装",
        "多功能酶标仪",
        "细胞自动计数仪",
    ]
    assert result.ranking.applied is True
    assert result.ranking.reason == "ai_partial_fallback"
