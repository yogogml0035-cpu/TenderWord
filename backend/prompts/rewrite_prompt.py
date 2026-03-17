from __future__ import annotations

from backend.prompts.types import RenderedPrompt, RewritePromptInput


REWRITE_SYSTEM_PROMPT = """
你是招标文档修改助手。
请根据用户修改指令，在保持文档结构与专业风格的前提下，对现有文本进行定向改写。
要求：
1. 只输出最终可直接写回文档的正文文本，不输出解释。
2. 无指令涉及的段落尽量保持原意。
3. 避免编造事实，不新增与指令无关的内容。
""".strip()

REWRITE_USER_PROMPT = """
【当前文档内容】
{base_text}

【技术参数参考资料】
以下内容仅作为改写时的背景参考，用于补充原始技术参数上下文；如用户没有要求，不要无关扩写。
{tender_params}

【用户修改指令】
{user_prompt}

请严格按指令完成修改，输出最终文本：
""".strip()


def render_rewrite_prompt(data: RewritePromptInput) -> RenderedPrompt:
    return RenderedPrompt(
        system_prompt=REWRITE_SYSTEM_PROMPT,
        user_prompt=REWRITE_USER_PROMPT.format(
            base_text=data.base_text,
            tender_params=data.tender_params,
            user_prompt=data.user_prompt,
        ),
    )
