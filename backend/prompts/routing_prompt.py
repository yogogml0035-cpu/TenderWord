from __future__ import annotations

import re

from backend.prompts.types import (
    RenderedPrompt,
    RewriteAssistantCandidate,
    RewriteHistoryMessage,
    RewriteTargetSelectionBundle,
    RewriteTargetSelectionPromptInput,
    RouteOrReplyPromptInput,
)


REWRITE_ROUTE_LITERAL = "rewrite"
REPLY_ROUTE_LITERAL = "reply"

ROUTE_OR_REPLY_SYSTEM_PROMPT = """
你是东松招标文件智能生成助手。
如果用户输入和修改、改写、重写已生成的招标文本有关，只输出 rewrite。
如果用户输入无关，就直接正常回答问题，并在合适时自然提醒用户：当前支持在生成招标文件后继续修改或重写，不满意时可以直接下达修改重写指令。
如果用户的问题依赖“当前文档”“这份文档”“第几章”等正文内容，但消息本身不是要求修改重写，不要假装看过文档；要直接说明当前不会自动携带文档正文，建议用户粘贴相关段落或直接下达修改重写指令。
如果用户是在打招呼、询问你是谁、你能做什么，请简短自我介绍，并明确自称“东松招标文件智能生成助手”。

规则：
1. 只有确定是修改、改写、重写当前招标文本时，才能输出 rewrite。
2. 输出 rewrite 时只能输出这一个单词，小写，不得带任何额外字符。
3. 其他情况直接输出给用户的中文回复，不要输出 JSON、标签、解释、分析过程。
4. 如果不确定是否属于修改重写，按普通回复处理。
5. 对“支持生成后继续修改或重写”的提醒最多说一次，不要重复改写同一提醒。
""".strip()

JUDGE_TARGET_SYSTEM_PROMPT = """
你是文档修改版本选择助手。
你的任务是根据会话历史和用户最新修改指令，从候选 assistant 版本中选出最应该被修改的一版。

规则：
1. 只能返回候选 assistant 版本的零基索引。
2. 只能输出一个纯数字，不要输出解释、标点、JSON 或额外文本。
3. 若用户没有明确指定历史版本，默认选择最符合语义的候选版本。
4. 若多版都可行，优先选择最新且最相关的一版。
""".strip()


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def _truncate(text: str, limit: int) -> str:
    normalized = _normalize_whitespace(text)
    if len(normalized) > limit:
        return normalized[:limit] + "..."
    return normalized


def render_route_or_reply_prompt(data: RouteOrReplyPromptInput) -> RenderedPrompt:
    history_lines: list[str] = []
    for item in data.messages[-6:]:
        role = "用户" if str(item.role or "") == "user" else "助手"
        content = _truncate(item.content, 300)
        if not content:
            continue
        history_lines.append(f"{role}: {content}")

    history_block = "\n".join(history_lines) if history_lines else "（无历史对话）"
    doc_summary = "无"
    if data.latest_rewrite_state is not None:
        doc_summary = (
            f"project_number={data.latest_rewrite_state.project_number}\n"
            f"project_name={data.latest_rewrite_state.project_name}\n"
            f"tender_type={data.latest_rewrite_state.tender_type}\n"
            f"latest_polished_preview={_truncate(data.latest_rewrite_state.polished_text, 400)}"
        )

    user_prompt = (
        "【会话状态】\n"
        f"has_rewrite_history={'yes' if data.has_rewrite_history else 'no'}\n\n"
        "【最近对话】\n"
        f"{history_block}\n\n"
        "【当前文档摘要】\n"
        f"{doc_summary}\n\n"
        "【最新用户消息】\n"
        f"{data.latest_user_message}\n"
    )

    return RenderedPrompt(
        system_prompt=ROUTE_OR_REPLY_SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )


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
