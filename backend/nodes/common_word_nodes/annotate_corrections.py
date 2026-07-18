"""共享后生成节点：条款标识规范化 + 更正批注候选。

位于 workflow/agent 最终正文确定之后、普通批注与 Word 写回之前。
只产出 state 字段，不操作 Word。
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Optional

from backend.helper.word_helper.clause_marker_normalize import (
    build_marker_correction_comments,
    normalize_clause_markers,
    normalize_table_models_markers,
)
from backend.states.base_state import CommentInstruction, TenderGraphStateBase
from backend.util.common_util import StreamCallbacks, stream_llm_completion
from backend.util.log_util.context_log import (
    get_generate_context_log_dir,
    write_agent_context_log_artifact,
)
from backend.util.log_util.progress_log import progress_log

NODE_NAME = "annotate_corrections"

_CORRECTION_SYSTEM = """你是招标文件技术参数差异批注生成器。输入同时提供【原始技术参数】与【最终正文】；只对同一参数的事实值变化生成批注。

严格按以下顺序执行：
1. 先对齐同一包、同一设备/服务对象、同一字段或同一条款；不确定对应关系时跳过。
2. 再判断变化是否只属于展示壳；不要因为两个字符串不同就直接输出批注。以下一律不生成批注：章节/条款编号的新增、删除、重排、层级变化或标点变化；项目符号（如 `.`、`-`、`•`）变化；空格、换行、末尾句号；模板字段名称变化和无损拆格。
3. 只有名称、型号、数量、单位、数值、范围、期限、地点、条件、否定词或正文事实文字真实变化时才生成批注。条款重要性标识 `*`/`※→★`、`△`/`Δ→▲` 是例外：即使其余文字相同，也必须生成更正批注。
4. 项目名称不能替代设备名称、维保设备、服务名称或采购标的名称；项目基础信息只可用于明确同槽位值。

必须跳过的示例（全部输出 `[]`）：
- `.动态心电血压仪（1套）` → `动态心电血压仪（1套）`
- `-无线连接技术` → `1、无线连接技术`
- `-1、2、3 通道或向量导联记录` → `9.2、1、2、3 通道或向量导联记录`
- `-2GB 内存` → `10.2、2GB 内存`
- `6. 速度：0~25km/h，取最大值。` → `6、速度：0~25km/h，取最大值`
- `1动态心电血压测试仪1套` → `1、动态心电血压测试仪1套`

必须保留的示例：`数量：13个` → `数量：14个`，输出 `原技术参数为“13个”，现改为“14个”`；`1. * 医用跑台` → `1、★医用跑台`，输出整条原值与整条现值的更正批注。

输出前检查：候选若只是字面不同但属于第 2 步展示壳，删除它。只输出 JSON 数组；每项仅含 `reference_text` 与 `comment_text`。`reference_text` 必须逐字出自【最终正文】；`comment_text` 必须严格为 `原技术参数为“aaa”，现改为“bbb”`。"""

_CORRECTION_REVIEW_SYSTEM = """你是更正批注的最终审核器。候选批注已经由另一模型根据原始技术参数和最终正文生成；你只决定哪些候选可以保留，不得创建、改写或解释批注。

保留条件：候选中的原值与现值是同一参数的真实事实值变化。
必须删除：仅编号/层级/编号标点、项目符号、空格或换行、末尾句号、模板字段壳或无损拆格引起的候选。`*`/`※→★`、`△`/`Δ→▲` 是重要性标识更正，必须保留。

尤其删除：`.动态心电血压仪（1套）`→`动态心电血压仪（1套）`、`-1、2、3 通道或向量导联记录`→`9.2、1、2、3 通道或向量导联记录`、`-2GB 内存`→`10.2、2GB 内存`。
保留：`13个`→`14个` 等事实值变化，以及 `1. * 医用跑台`→`1、★医用跑台` 等重要性标识更正。

只输出需要保留候选的 1 起始序号 JSON 数组，例如 `[2, 5]`；不确定时不要保留。"""


def _strip_code_fence(text: str) -> str:
    stripped = str(text or "").strip()
    if not (stripped.startswith("```") and stripped.endswith("```")):
        return stripped
    first_newline = stripped.find("\n")
    if first_newline < 0:
        return stripped
    return stripped[first_newline + 1 : -3].strip()


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


def _split_correction_comment_text(comment: str) -> tuple[str, str] | None:
    prefix = "原技术参数为“"
    separator = "”，现改为“"
    suffix = "”"
    if not comment.startswith(prefix) or not comment.endswith(suffix):
        return None
    original, found, current = comment[len(prefix) : -len(suffix)].partition(separator)
    if not found or not original or not current:
        return None
    return original, current


def _write_correction_log_artifact(*, task_id: str, phase: str, content: str) -> None:
    """将差异标注输入、模型原文和最终候选落到 context_log。"""
    try:
        write_agent_context_log_artifact(
            get_generate_context_log_dir(__file__),
            prefix="correction",
            task_id=task_id,
            phase=phase,
            content=content,
        )
    except Exception as exc:
        progress_log.warning(f"[{NODE_NAME}] 保存 {phase} 日志失败: {exc}")


def _parse_correction_comments(
    raw: str,
    *,
    tender_params: str | None = None,
    polished_text: str | None = None,
) -> list[CommentInstruction]:
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
        # LLM 只负责候选抽取；来源、现值、锚点和固定句式由代码做最后门禁，
        # 避免非思考模型把不确定差异或解释文字写进 Word 批注。
        if polished_text is not None and reference not in polished_text:
            continue
        values = _split_correction_comment_text(comment)
        if values is None:
            continue
        original, current = values
        if not original or not current or original == current:
            continue
        if tender_params is not None and original not in tender_params:
            continue
        if polished_text is not None and (
            current not in polished_text or current not in reference
        ):
            continue
        comments.append({"reference_text": reference, "comment_text": comment})
    return comments


def _build_correction_review_prompt(comments: list[CommentInstruction]) -> str:
    numbered_comments = [
        {
            "index": index,
            "reference_text": item["reference_text"],
            "comment_text": item["comment_text"],
        }
        for index, item in enumerate(comments, start=1)
    ]
    return "【待审核更正批注】\n" + json.dumps(
        numbered_comments,
        ensure_ascii=False,
        indent=2,
    )


def _parse_correction_review_indexes(raw: str, *, candidate_count: int) -> set[int]:
    payload = _extract_json_array(raw)
    if not payload:
        return set()
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return set()
    if not isinstance(data, list):
        return set()
    return {
        index
        for item in data
        if isinstance(item, int)
        and not isinstance(item, bool)
        and 1 <= (index := int(item)) <= candidate_count
    }


def _review_correction_comments(
    *,
    comments: list[CommentInstruction],
    model_provider: str,
    task_id: str,
) -> list[CommentInstruction]:
    if not comments:
        return []
    review_prompt = _build_correction_review_prompt(comments)
    _write_correction_log_artifact(
        task_id=task_id,
        phase="review_prompt",
        content=f"{_CORRECTION_REVIEW_SYSTEM}\n\n{review_prompt}",
    )
    try:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            raw_review = loop.run_until_complete(
                stream_llm_completion(
                    model_provider=model_provider,
                    system_prompt=_CORRECTION_REVIEW_SYSTEM,
                    user_prompt=review_prompt,
                    callbacks=StreamCallbacks(),
                    extra_params_override={"temperature": 0.0},
                )
            )
        finally:
            loop.close()
            asyncio.set_event_loop(None)
    except Exception as exc:
        progress_log.warning(f"[{NODE_NAME}] 批注复核 LLM 失败，跳过 LLM 更正批注: {exc}")
        return []
    _write_correction_log_artifact(
        task_id=task_id,
        phase="review_raw_output",
        content=str(raw_review or ""),
    )
    keep_indexes = _parse_correction_review_indexes(
        str(raw_review or ""),
        candidate_count=len(comments),
    )
    return [item for index, item in enumerate(comments, start=1) if index in keep_indexes]


def _build_user_prompt(
    *,
    tender_params: str,
    polished_text: str,
    marker_already_applied: bool,
    marker_correction_comments: list[CommentInstruction] | None = None,
    project_info: str = "",
    project_name: str = "",
) -> str:
    note = ""
    if marker_correction_comments:
        note = (
            "以下条款标识更正已由代码生成；不要重复输出这些同一位置的批注，"
            "其余未列出的重要性标识更正仍必须生成：\n"
            f"{json.dumps(marker_correction_comments, ensure_ascii=False)}"
        )
    elif marker_already_applied:
        note = "最终正文中的条款标识已规范为 ▲/★；若原始技术参数是对应的 `*`、`※`、`△` 或 `Δ`，必须生成该标识更正批注。"
    return (
        f"{note}\n\n"
        "按 system prompt 的 1 至 4 步执行。先排除展示壳变化，再比较同一参数的事实值；"
        "不要因为两个字符串不同就直接输出批注。\n\n"
        f"【项目名称（只授权项目名称槽位）】\n{project_name or ''}\n\n"
        "【其它项目基础信息】\n"
        "只有带明确字段标签的同槽位值才能按优先级覆盖原始技术参数；无字段标签的稳定分隔片段只能在原始技术参数没有该槽位值时补充项目级字段；"
        "不得把无标签片段或项目名称用于补全设备/维保设备/服务/采购标的名称。\n"
        f"{project_info or ''}\n\n"
        f"【原始技术参数】\n{tender_params or ''}\n\n"
        f"【最终正文】\n{polished_text or ''}\n"
    )


def _run_annotation_llm(
    *,
    tender_params: str,
    polished_text: str,
    model_provider: str,
    project_info: str = "",
    project_name: str = "",
    task_id: str = NODE_NAME,
    marker_correction_comments: list[CommentInstruction] | None = None,
) -> list[CommentInstruction]:
    user_prompt = _build_user_prompt(
        tender_params=tender_params,
        polished_text=polished_text,
        marker_already_applied=True,
        marker_correction_comments=marker_correction_comments,
        project_info=project_info,
        project_name=project_name,
    )
    _write_correction_log_artifact(
        task_id=task_id,
        phase="prompt",
        content=f"{_CORRECTION_SYSTEM}\n\n{user_prompt}",
    )
    # 标注失败不阻断生成：捕获异常并返回空列表。
    # 同步节点内新建 loop 调用异步 LLM（与 generate_polished_text 同类节点一致）。
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
                    extra_params_override={"temperature": 0.1},
                )
            )
        finally:
            loop.close()
            asyncio.set_event_loop(None)
    except Exception as exc:
        progress_log.warning(f"[{NODE_NAME}] 标注 LLM 失败，仅保留代码标识更正批注: {exc}")
        return []
    _write_correction_log_artifact(
        task_id=task_id,
        phase="raw_output",
        content=str(content or ""),
    )
    generated_comments = _parse_correction_comments(
        str(content or ""),
        tender_params=tender_params,
        polished_text=polished_text,
    )
    return _review_correction_comments(
        comments=generated_comments,
        model_provider=model_provider,
        task_id=task_id,
    )


def annotate_corrections(
    state: TenderGraphStateBase,
    config=None,
) -> TenderGraphStateBase:
    """规范化 polished_text / 表格单元格，并产出 correction_comments。"""
    start = time.perf_counter()
    polished_text = str(state.get("polished_text") or "")
    tender_params = str(state.get("tender_params") or "")
    project_info = str(state.get("project_content") or "")
    project_name = str(state.get("project_name") or "")
    table_models = state.get("tender_param_table_models") or []

    normalized_text, text_changes = normalize_clause_markers(polished_text)
    normalized_tables, table_changes = normalize_table_models_markers(table_models)
    marker_comments = build_marker_correction_comments(
        list(text_changes) + list(table_changes)
    )

    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    model_provider = str(configurable.get("model_provider") or "deepseek")
    task_id = str(configurable.get("task_id") or state.get("task_id") or NODE_NAME)
    llm_comments: list[CommentInstruction] = []
    if tender_params.strip() and normalized_text.strip():
        llm_comments = _run_annotation_llm(
            tender_params=tender_params,
            polished_text=normalized_text,
            model_provider=model_provider,
            project_info=project_info,
            project_name=project_name,
            task_id=task_id,
            marker_correction_comments=marker_comments,
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
    _write_correction_log_artifact(
        task_id=task_id,
        phase="accepted_comments",
        content=json.dumps(correction_comments, ensure_ascii=False, indent=2),
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
