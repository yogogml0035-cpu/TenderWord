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

_CORRECTION_COMMENT_PATTERN = re.compile(
    r"\A原技术参数为“(?P<original>.+?)”，现改为“(?P<current>.+?)”\Z",
    re.DOTALL,
)

# 编号是生成阶段允许重排/补全的结构壳，不属于事实值。
# ponytail: 仅剥离常见行首编号壳；若抽取层保留 Word list metadata，应升级为 token-aware diff。
_LEADING_CLAUSE_NUMBER_RE = re.compile(
    r"^\s*(?:"
    r"(?:\(\s*(?:\d+(?:\.\d+)*|[一二三四五六七八九十百千万]+)\s*\)|"
    r"（\s*(?:\d+(?:\.\d+)*|[一二三四五六七八九十百千万]+)\s*）)|"
    r"(?:\d+(?:[.-]\d+)*|[一二三四五六七八九十百千万]+)"
    r"[、.．:：)）]"
    r")\s*"
)

_CORRECTION_SYSTEM = """你是招标文件技术参数差异标注器。唯一任务是比较事实值：找出【原始技术参数】在【最终正文】中被增字、减字、替换、改写或错误拼接的内容，并生成 Word 更正批注候选。不要做合规审查，不要提出修改建议。

执行顺序（必须从第 1 步做到第 7 步，不要跳步）：
1. 建立事实账本：按“包/设备或服务对象/来源字段标签/目标语义槽位/原始字段值”拆分【原始技术参数】。一行中若同时出现维保设备、数量、品牌、型号、服务期限等多个字段，必须拆成多个事实原子，不能把整行当成一个值。
2. 对齐目标槽位：
   - 先锁定同一包、同一设备或服务对象和物理顺序，再优先匹配完全同名字段。
   - 只有最终正文明显是在给同一事实换模板字段壳时，才允许对齐不同标签。例如原字段`维保设备`可对齐设备清单的`设备名称`列，`型号`可对齐`规格型号`列，`数量：1套`可对齐`数量=1`与`单位=套`。若拆分字符按原顺序拼回仍为`1套`，这是无损结构变化，不是参数改动。
   - `项目名称`描述整个项目，默认绝不是`设备名称/维保设备/服务名称/采购标的名称`的值。项目名称、文件名、模板旧名称或相邻字段即使包含相似词，也不能授权给标的名称增字或补全。只有输入明确声明两个槽位取值相同，才可按原值逐字复制。
3. 确定比较真值：
   - 项目概述受保护字段按“【项目基础信息】明确标注或可无歧义定位的同槽位值 > 【原始技术参数】项目概述同槽位值”确定真值；项目名称只能授权项目名称槽位。
   - 若【项目基础信息】只是用制表符、空格或斜杠拼接的无标签文本，只有目标项目级字段壳已明确语义、完整分隔片段与现值逐字一致、且原始技术参数没有该槽位值时，才视为合法来源；不得靠猜测拆分并覆盖原始技术参数的明确值。
   - 技术/服务/商务条款和设备清单单元格以【原始技术参数】同槽位值为真值。
   - 模板只有在前两个来源都没有该槽位值时才是合法兜底；若原始技术参数已经有同槽位值，模板旧值不能覆盖它。
4. 逐字比较：将原值与现值逐字符比较。除第 5 步白名单外，只要现值发生增字、减字、替换或拼接，就生成批注；即使语义相同也要标注。
5. 结构变化白名单：纯章节/条款编号重排、模板字段标签壳、字段从句子无损拆到表格单元格、换行、缩进、字体、段落、表格布局、系统来源标记删除、评分/评审污染删除不标注。`△/Δ→▲`、`*/※→★` 已由代码生成更正批注，本步骤不要重复输出。无损拆格必须满足“目标单元格字符按原顺序拼回等于原字段值”；否则仍要标注。
   - **编号隔离硬规则：** 先从原值和现值每个原子条款行首剥离纯结构编号（例如 `1、`、`2.1、`、`（1）`、`一、`），再比较事实文字。仅新增、删除、替换、重排或恢复可见编号时，必须输出 `[]`，不得生成“原技术参数为……现改为……”批注；编号后的 `★/▲` 与条款正文仍需继续比较。
6. 必查变化：
   - 名称、品牌、型号、专有名词增加或删除限定词；
   - 同义改写、简称展开、术语规范化、语序润色；
   - 数字与中文数字互换，数值、单位、范围、比例、频次、期限、地点、条件、否定词或比较符号变化；
   - 项目名称、文件名、模板旧值或相邻字段被拼入另一槽位；
   - 原条款被部分删除、合并后丢字，或拆分后改变文字/含义。
7. 输出前逐条校验：
   - 只保留能与原始技术参数明确对齐、且原值和现值确实不同的项目；不确定就不输出。
   - reference_text 必须是【最终正文】中连续、逐字、可搜索到的最小可靠片段；优先用现字段值，过短或重复时用包含它的完整现字段/现条款。不得用原值作锚点，不得跨行拼接。
   - comment_text 固定为`原技术参数为“aaa”，现改为“bbb”`。单字段变化时，aaa 与 bbb 只写原字段值和现字段值，不重复字段标签；只有无法分离的整条条款变化才写完整原条款和现条款。不得概括、解释或加入“建议确认”。每个事实原子单独一条。
   - 最终只输出 JSON 数组，元素只能包含 reference_text 和 comment_text；无可确定变化时输出 []。不要输出 Markdown、解释、审核结论或修复建议。

正例 1（名称被项目名错误补全）：
项目基础信息：`项目名称：医用核磁共振系统维保`
原始技术参数：`维保设备：磁共振系统；数量：1套`
最终正文设备清单：`设备名称：医用核磁共振系统；数量：1；单位：套`
输出：[{"reference_text":"医用核磁共振系统","comment_text":"原技术参数为“磁共振系统”，现改为“医用核磁共振系统”"}]

正例 2（数字写法被改写）：
原始技术参数：`服务期限：3年`；最终正文：`服务期限：三年`
输出：[{"reference_text":"服务期限：三年","comment_text":"原技术参数为“3年”，现改为“三年”"}]

反例 1（无损换字段壳/拆格）：
原始技术参数：`维保设备：磁共振系统；数量：1套；型号：Ingenia 3.0T`
最终正文设备清单：`设备名称=磁共振系统；数量=1；单位=套；规格型号=Ingenia 3.0T`
输出：[]

反例 2（只有编号变化）：原条款仅从`2.1`重排为`1.1`，其它文字未变。
输出：[]

反例 3（自动补号）：原始技术参数为`通道反转分析`，最终正文为`4、通道反转分析`。
输出：[]

反例 4（补号同时规范标识）：原始技术参数为`*独立婴幼儿分析模式`，最终正文为`2、★独立婴幼儿分析模式`。
输出：[]"""


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


def _normalize_for_correction_comparison(value: str) -> str:
    """去除编号壳并规范条款标识，用于过滤结构变化误报。"""
    lines: list[str] = []
    for line in str(value or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        lines.append(_LEADING_CLAUSE_NUMBER_RE.sub("", line.strip(), count=1))
    normalized, _ = normalize_clause_markers("\n".join(lines))
    return normalized.strip()


def _is_structure_only_correction(original: str, current: str) -> bool:
    """编号/标识规范化后无事实差异时，拒绝 LLM 的更正批注候选。"""
    return (
        bool(str(original or "").strip())
        and bool(str(current or "").strip())
        and _normalize_for_correction_comparison(original)
        == _normalize_for_correction_comparison(current)
    )


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
        match = _CORRECTION_COMMENT_PATTERN.fullmatch(comment)
        if match is None:
            continue
        original = match.group("original")
        current = match.group("current")
        if not original or not current or original == current:
            continue
        if _is_structure_only_correction(original, current):
            continue
        if tender_params is not None and original not in tender_params:
            continue
        if polished_text is not None and (
            current not in polished_text or current not in reference
        ):
            continue
        comments.append({"reference_text": reference, "comment_text": comment})
    return comments


def _build_user_prompt(
    *,
    tender_params: str,
    polished_text: str,
    marker_already_applied: bool,
    project_info: str = "",
    project_name: str = "",
) -> str:
    note = (
        "最终正文与表格单元格中的条款标识已由代码规范为 ▲/★；"
        "请勿把这些已规范标识再改回 △/Δ/*/※。"
        if marker_already_applied
        else ""
    )
    return (
        f"{note}\n\n"
        "请先按包、对象、来源字段标签和目标语义槽位拆分原始技术参数，再逐字段对齐最终正文并逐字比较。"
        "优先检查名称限定词、同义改写、数字写法、单位/范围、否定词、型号和专有名词；"
        "允许`维保设备`对齐设备清单`设备名称`，允许`数量：1套`无损拆为`数量=1、单位=套`；"
        "只标注事实值字符变化，不标注纯结构变化。先剥离行首的`1、`、`2.1、`、`（1）`、`一、`等编号再比较；"
        "例如`通道反转分析`与`4、通道反转分析`、`无线连接技术……`与`1、无线连接技术……`都不生成更正批注。\n\n"
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
) -> list[CommentInstruction]:
    user_prompt = _build_user_prompt(
        tender_params=tender_params,
        polished_text=polished_text,
        marker_already_applied=True,
        project_info=project_info,
        project_name=project_name,
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
    return _parse_correction_comments(
        str(content or ""),
        tender_params=tender_params,
        polished_text=polished_text,
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
    llm_comments: list[CommentInstruction] = []
    if tender_params.strip() and normalized_text.strip():
        llm_comments = _run_annotation_llm(
            tender_params=tender_params,
            polished_text=normalized_text,
            model_provider=model_provider,
            project_info=project_info,
            project_name=project_name,
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
