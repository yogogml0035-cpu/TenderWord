"""共享后生成节点：条款标识规范化 + 更正批注候选。

位于 workflow/agent 最终正文确定之后、普通批注与 Word 写回之前。
只产出 state 字段，不操作 Word。
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, Optional

from backend.helper.word_helper.clause_marker_normalize import (
    build_marker_correction_comments,
    normalize_clause_markers,
    normalize_table_models_markers,
)
from backend.states.base_state import CommentInstruction, TenderGraphStateBase
from backend.util.common_util import StreamCallbacks, stream_llm_completion
from backend.util.log_util.progress_log import progress_log

NODE_NAME = "annotate_corrections"

_CORRECTION_SYSTEM = """你是招标文件更正标注器。比较【原始技术参数】与【最终正文】，只输出明确的文本更正批注 JSON 数组。

规则：
1. 只标注可判定的错别字、标点、全半角、规范写法、授权标识（如 △/Δ→▲、*/※→★）差异。
2. 不得要求改回数值、单位、范围、否定词、型号、专有名词、条款归属。
3. 纯章节编号、换行、缩进、字体、段落或表格布局变化不批注。
4. 能精确定位时，reference_text 取最终正文中最小可靠锚点；无法可靠拆分局部变更时，以完整原条款和完整现条款各写一条，不猜测局部映射。
5. comment_text 固定格式：原技术参数为“aaa”，现改为“bbbb”
6. 只输出 JSON 数组，元素形如 {"reference_text":"...","comment_text":"..."}；无更正则输出 []。
7. 不要编造差异；不要输出 Markdown 代码块或解释。"""


def _strip_code_fence(text: str) -> str:
    stripped = str(text or "").strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, re.IGNORECASE | re.DOTALL)
    if not match:
        return stripped
    return match.group(1).strip()


def _extract_json_array(text: str) -> Optional[str]:
    raw = _strip_code_fence(text)
    start = raw.find("[")
    if start < 0:
        return None
    in_string = False
    escape = False
    depth = 0
    array_start = -1
    for index in range(start, len(raw)):
        char = raw[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "[":
            if depth == 0:
                array_start = index
            depth += 1
            continue
        if char == "]" and depth > 0:
            depth -= 1
            if depth == 0 and array_start >= 0:
                return raw[array_start : index + 1]
    return None


def _parse_correction_comments(raw: str) -> list[CommentInstruction]:
    payload = _extract_json_array(raw)
    if not payload:
        return []
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    comments: list[CommentInstruction] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        reference = str(item.get("reference_text") or "").strip()
        comment = str(item.get("comment_text") or "").strip()
        if not reference or not comment:
            continue
        comments.append({"reference_text": reference, "comment_text": comment})
    return comments


def _build_user_prompt(
    *,
    tender_params: str,
    polished_text: str,
    marker_already_applied: bool,
) -> str:
    note = (
        "最终正文与表格单元格中的条款标识已由代码规范为 ▲/★；"
        "请勿把这些已规范标识再改回 △/Δ/*/※。"
        if marker_already_applied
        else ""
    )
    return (
        f"{note}\n\n"
        f"【原始技术参数】\n{tender_params or ''}\n\n"
        f"【最终正文】\n{polished_text or ''}\n"
    )


def _run_annotation_llm(
    *,
    tender_params: str,
    polished_text: str,
    model_provider: str,
) -> list[CommentInstruction]:
    user_prompt = _build_user_prompt(
        tender_params=tender_params,
        polished_text=polished_text,
        marker_already_applied=True,
    )
    # 标注失败不阻断生成：捕获异常并返回空列表。
    try:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            content = loop.run_until_complete(
                stream_llm_completion(
                    model_provider=model_provider,
                    system_prompt=_CORRECTION_SYSTEM,
                    user_prompt=user_prompt,
                    callbacks=StreamCallbacks(),
                    temperature=0.1,
                )
            )
        finally:
            loop.close()
            asyncio.set_event_loop(None)
    except Exception as exc:
        progress_log.warning(f"[{NODE_NAME}] 标注 LLM 失败，仅保留代码标识更正批注: {exc}")
        return []
    return _parse_correction_comments(str(content or ""))


def annotate_corrections(
    state: TenderGraphStateBase,
    config=None,
) -> TenderGraphStateBase:
    """规范化 polished_text / 表格单元格，并产出 correction_comments。"""
    start = time.perf_counter()
    polished_text = str(state.get("polished_text") or "")
    tender_params = str(state.get("tender_params") or "")
    table_models = state.get("tender_param_table_models") or []

    normalized_text, text_changes = normalize_clause_markers(polished_text)
    normalized_tables, table_changes = normalize_table_models_markers(table_models)
    marker_comments = build_marker_correction_comments(
        list(text_changes) + list(table_changes)
    )

    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    model_provider = str(configurable.get("model_provider") or "deepseek")
    llm_comments: list[CommentInstruction] = []
    if tender_params.strip() and normalized_text.strip():
        llm_comments = _run_annotation_llm(
            tender_params=tender_params,
            polished_text=normalized_text,
            model_provider=model_provider,
        )

    # 代码标识更正优先，再追加 LLM 更正；按 (reference, comment) 去重。
    seen: set[tuple[str, str]] = set()
    correction_comments: list[CommentInstruction] = []
    for item in list(marker_comments) + list(llm_comments):
        key = (
            str(item.get("reference_text") or "").strip(),
            str(item.get("comment_text") or "").strip(),
        )
        if not key[0] or not key[1] or key in seen:
            continue
        seen.add(key)
        correction_comments.append(
            {"reference_text": key[0], "comment_text": key[1]}
        )

    duration = time.perf_counter() - start
    progress_log.info(
        f"[{NODE_NAME}] 标识替换={len(text_changes)+len(table_changes)}，"
        f"更正批注={len(correction_comments)}，耗时 {duration:.2f}s"
    )

    result: dict[str, Any] = {
        "polished_text": normalized_text,
        "correction_comments": correction_comments,
    }
    if table_models:
        result["tender_param_table_models"] = normalized_tables
    return TenderGraphStateBase(**result)


__all__ = ["annotate_corrections", "NODE_NAME"]
