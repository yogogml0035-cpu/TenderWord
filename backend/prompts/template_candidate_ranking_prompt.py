from __future__ import annotations

import json
from typing import Sequence

from backend.prompts.types import (
    RenderedPrompt,
    TemplateCandidateRankingPromptInput,
)


TEMPLATE_CANDIDATE_RANKING_SYSTEM_PROMPT = """
你是模板候选排序助手。
你的任务是根据“当前项目名称”和“历史项目名称候选列表”，判断哪些历史项目名称与当前项目名称最相关，并给出从高到低的排序结果。

规则：
1. 只能输出一个 JSON 数组。
2. 数组元素只能是候选 row_index 整数。
3. 必须完整覆盖所有候选且不能重复、不能遗漏。
4. 不能输出解释、注释、Markdown、代码块或额外文本。
""".strip()


def render_template_candidate_ranking_prompt(
    data: TemplateCandidateRankingPromptInput,
) -> RenderedPrompt:
    candidate_lines = [
        f"- row_index={item.row_index}; tendername={item.tendername}"
        for item in data.candidates
    ]
    candidate_block = "\n".join(candidate_lines) if candidate_lines else "（无候选）"
    expected_indexes = ", ".join(str(item.row_index) for item in data.candidates)

    user_prompt = (
        "【当前项目名称】\n"
        f"{data.project_name}\n\n"
        "【历史项目名称候选】\n"
        f"{candidate_block}\n\n"
        "请按相关性从高到低返回 row_index 排序结果。\n"
        f"候选 row_index 必须且只能包含：{expected_indexes}\n"
        f"输出示例：{json.dumps([item.row_index for item in data.candidates], ensure_ascii=False)}"
    )

    return RenderedPrompt(
        system_prompt=TEMPLATE_CANDIDATE_RANKING_SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )


def parse_template_candidate_ranking_output(
    raw_output: str,
    expected_indexes: Sequence[int],
) -> tuple[int, ...]:
    try:
        parsed = json.loads(str(raw_output or "").strip())
    except json.JSONDecodeError as exc:
        raise ValueError("模板候选排序结果不是有效 JSON 数组") from exc

    if not isinstance(parsed, list):
        raise ValueError("模板候选排序结果必须是 JSON 数组")

    normalized_indexes: list[int] = []
    for item in parsed:
        if isinstance(item, bool) or not isinstance(item, int):
            raise ValueError("模板候选排序结果只能包含整数 row_index")
        normalized_indexes.append(item)

    if len(normalized_indexes) != len(expected_indexes):
        raise ValueError("模板候选排序结果数量不完整")

    if len(set(normalized_indexes)) != len(normalized_indexes):
        raise ValueError("模板候选排序结果存在重复 row_index")

    if set(normalized_indexes) != set(expected_indexes):
        raise ValueError("模板候选排序结果与候选 row_index 不一致")

    return tuple(normalized_indexes)
