from __future__ import annotations

import re

from backend.prompts.types import (
    RenderedPrompt,
    RewriteAssistantCandidate,
    RewriteTargetSelectionBundle,
    RewriteTargetSelectionPromptInput,
)

JUDGE_TARGET_SYSTEM_PROMPT = """
你是文档修改版本选择助手。
你的任务是根据会话历史和用户最新修改指令，从候选 assistant 版本中选出最应该被修改的一版。

规则：
1. 只能返回候选 assistant 版本的零基索引。
2. 只能输出一个纯数字，不要输出解释、标点、JSON 或额外文本。
3. 若用户没有明确指定历史版本，默认选择最符合语义的候选版本。
4. 若多版都可行，优先选择最新且最相关的一版。
""".strip()


def build_rewrite_target_selection_bundle(
    data: RewriteTargetSelectionPromptInput,
) -> RewriteTargetSelectionBundle:
    assistant_candidates: list[RewriteAssistantCandidate] = []
    assistant_index = 0
    lines: list[str] = ["【会话历史】"]

    for idx, message in enumerate(data.messages):
        if message.role == "assistant" and message.rewrite_state is not None:
            candidate = RewriteAssistantCandidate(
                assistant_index=assistant_index,
                content=message.content,
                created_at=message.created_at,
                rewrite_state=message.rewrite_state,
            )
            assistant_candidates.append(candidate)
            lines.extend(
                [
                    f"{idx}. role=assistant candidate_index={assistant_index}",
                    f"content={message.content}",
                    f"tender_type={message.rewrite_state.tender_type}",
                    f"prepared_doc_path={message.rewrite_state.prepared_doc_path}",
                    "polished_text:",
                    message.rewrite_state.polished_text,
                    "---",
                ]
            )
            assistant_index += 1
            continue

        lines.extend(
            [
                f"{idx}. role={message.role}",
                f"content={message.content}",
                "---",
            ]
        )

    candidate_list = ", ".join(
        str(item.assistant_index) for item in assistant_candidates
    )
    lines.extend(
        [
            "",
            "【用户最新指令】",
            data.user_prompt,
            "",
            f"可选 assistant candidate_index: {candidate_list}",
            "请只输出一个纯数字索引。",
        ]
    )

    return RewriteTargetSelectionBundle(
        rendered_prompt=RenderedPrompt(
            system_prompt=JUDGE_TARGET_SYSTEM_PROMPT,
            user_prompt="\n".join(lines),
        ),
        assistant_candidates=tuple(assistant_candidates),
    )


def parse_rewrite_target_selection(raw_output: str, candidate_count: int) -> int:
    normalized = str(raw_output or "").strip()
    if not re.fullmatch(r"\d+", normalized):
        raise ValueError(f"rewrite 目标版本选择结果非法: {normalized!r}")

    index = int(normalized)
    if index < 0 or index >= candidate_count:
        raise ValueError(f"rewrite 目标版本索引越界: {index}")
    return index
