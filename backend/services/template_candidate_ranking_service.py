from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from backend.config.settings import settings
from backend.models.template_candidates import TemplateCandidateRanking
from backend.prompts import (
    TemplateCandidateRankingItem,
    TemplateCandidateRankingPromptInput,
    parse_template_candidate_ranking_output,
    render_template_candidate_ranking_prompt,
)
from backend.util.common_util import stream_llm_completion


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TemplateCandidateRankingResult:
    candidates: list[dict[str, Any]]
    ranking: TemplateCandidateRanking


@dataclass(frozen=True)
class _PriorityGroup:
    priority: Optional[int]
    candidates: tuple[dict[str, Any], ...]


def _normalize_project_name(value: str | None) -> str:
    return str(value or "").strip()


def _parse_priority(value: Any) -> Optional[int]:
    normalized = str(value or "").strip()
    if not normalized or not re.fullmatch(r"\d+", normalized):
        return None
    return int(normalized)


class TemplateCandidateRankingService:
    async def rank_candidates(
        self,
        *,
        candidates: Sequence[Mapping[str, Any]],
        project_name: str | None,
    ) -> TemplateCandidateRankingResult:
        normalized_candidates = [dict(candidate) for candidate in candidates]
        project_name_text = _normalize_project_name(project_name)
        ordered_groups = self._build_priority_groups(normalized_candidates)
        eligible_groups = [
            group for group in ordered_groups if group.priority is not None and len(group.candidates) > 1
        ]

        success_count = 0
        failed_count = 0
        final_candidates: list[dict[str, Any]] = []

        for group in ordered_groups:
            ordered_group = list(group.candidates)
            if group.priority is not None and len(group.candidates) > 1 and project_name_text:
                try:
                    ordered_group = await self._rank_group_by_ai(
                        group_candidates=group.candidates,
                        project_name=project_name_text,
                    )
                    success_count += 1
                except Exception as exc:
                    failed_count += 1
                    logger.warning(
                        "模板候选 AI 重排失败: priority=%s group_size=%s error=%s",
                        group.priority,
                        len(group.candidates),
                        exc,
                    )
            final_candidates.extend(ordered_group)

        ranking = self._build_ranking_meta(
            project_name=project_name_text,
            eligible_group_count=len(eligible_groups),
            success_count=success_count,
            failed_count=failed_count,
        )
        return TemplateCandidateRankingResult(
            candidates=final_candidates,
            ranking=ranking,
        )

    def _build_priority_groups(
        self,
        candidates: Sequence[dict[str, Any]],
    ) -> tuple[_PriorityGroup, ...]:
        numeric_groups: dict[int, list[dict[str, Any]]] = {}
        invalid_candidates: list[dict[str, Any]] = []

        for candidate in candidates:
            priority = _parse_priority(candidate.get("yxj"))
            if priority is None:
                invalid_candidates.append(candidate)
                continue
            numeric_groups.setdefault(priority, []).append(candidate)

        ordered_groups: list[_PriorityGroup] = [
            _PriorityGroup(priority=priority, candidates=tuple(numeric_groups[priority]))
            for priority in sorted(numeric_groups)
        ]
        if invalid_candidates:
            ordered_groups.append(
                _PriorityGroup(priority=None, candidates=tuple(invalid_candidates))
            )
        return tuple(ordered_groups)

    async def _rank_group_by_ai(
        self,
        *,
        group_candidates: Sequence[dict[str, Any]],
        project_name: str,
    ) -> list[dict[str, Any]]:
        prompt_candidates = tuple(
            TemplateCandidateRankingItem(
                row_index=index,
                tendername=str(candidate.get("tendername") or "").strip(),
            )
            for index, candidate in enumerate(group_candidates)
        )
        rendered_prompt = render_template_candidate_ranking_prompt(
            TemplateCandidateRankingPromptInput(
                project_name=project_name,
                candidates=prompt_candidates,
            )
        )
        raw_output = await stream_llm_completion(
            model_provider=settings.TEMPLATE_CANDIDATE_RANKING_LLM_PROVIDER,
            system_prompt=rendered_prompt.system_prompt,
            user_prompt=rendered_prompt.user_prompt,
            check_interval=2.0,
        )
        ordered_indexes = parse_template_candidate_ranking_output(
            raw_output,
            [candidate.row_index for candidate in prompt_candidates],
        )
        return [dict(group_candidates[index]) for index in ordered_indexes]

    def _build_ranking_meta(
        self,
        *,
        project_name: str,
        eligible_group_count: int,
        success_count: int,
        failed_count: int,
    ) -> TemplateCandidateRanking:
        if eligible_group_count == 0:
            return TemplateCandidateRanking(
                applied=False,
                mode="priority_only",
                reason="no_tied_priority",
                message="当前没有需要同级重排的模板。",
            )

        if not project_name:
            return TemplateCandidateRanking(
                applied=False,
                mode="priority_only",
                reason="project_name_missing",
                message="当前项目名称缺失，未启用同优先级 AI 重排。",
            )

        if success_count > 0 and failed_count == 0:
            return TemplateCandidateRanking(
                applied=True,
                mode="ai",
                reason="ai_ranked",
                message="AI已按项目名称相关性和优先级排序。",
            )

        if success_count > 0:
            return TemplateCandidateRanking(
                applied=True,
                mode="ai",
                reason="ai_partial_fallback",
                message="AI已按项目名称相关性和优先级排序。",
            )

        return TemplateCandidateRanking(
            applied=False,
            mode="priority_only",
            reason="ai_failed",
            message="已按优先级排序。",
        )

_template_candidate_ranking_service: Optional[TemplateCandidateRankingService] = None


def get_template_candidate_ranking_service() -> TemplateCandidateRankingService:
    global _template_candidate_ranking_service
    if _template_candidate_ranking_service is None:
        _template_candidate_ranking_service = TemplateCandidateRankingService()
    return _template_candidate_ranking_service
