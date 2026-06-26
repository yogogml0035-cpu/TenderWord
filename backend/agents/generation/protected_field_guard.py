"""受保护基础字段确定性护栏.

`content_verify_agent` 的提示词已经声明“受保护基础字段不得删除”，但 LLM 在
param/template 生成风格下偶尔会把模板继承的 `付款方式`、`交付日期` 等受保护字段
误判为“无新材料支撑的旧事实”，产出删除 finding；下游 `content_revise_agent`
照做删除后，`update_word` 因 `xjcg`/`gngk_fw_zc` 缺少 `付款方式：` 失败。

本模块在 LLM 审核 JSON 解析之后、写入 `/audits/round-N.json` 之前执行两层确定性
净化，保证修订 agent 读到的 JSON 已经满足“字段存在性高于旧事实清理”：

1. 过滤任何要求删除受保护字段的 finding（evidence/fix_hint 命中
   `删除/移除/去掉/删去 + 受保护字段名`）。
2. 对当前正文缺失的受保护字段追加确定性 finding：要求按参考模板同包字段行
   补回；找不到同包则用参考中第一个可用字段行。

direct_replace 类型（如 `gngk_hw_cz`、`gjgk`）不使用受保护字段 profile，
guard 直接返回原 findings，不介入。
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from backend.agents.generation.types import AuditFinding
from backend.config.tender_config import (
    CONTENT_UPDATE_MODE_PROTECTED_FIELDS,
    ProtectedFieldProfile,
    get_content_update_mode,
    get_protected_field_profile,
)
from backend.helper.word_helper.protected_fields import (
    extract_protected_field_name,
    match_protected_field_line,
)


# 命中即视为“要求删除字段”的动词；与受保护字段名同现时该项 finding 被丢弃。
_PROTECTED_FIELD_DELETE_VERBS = ("删除", "移除", "去掉", "删去", "删除掉", "清除")
# 限定受保护字段的“基础信息”字段名（不包含值/具体说明），用于判断 finding 是否
# 在讨论受保护字段；只取字段名（不含冒号）即可。
_BASIC_INFO_FIELD_NAMES = (
    "设备名称及数量",
    "交付日期",
    "交付地点",
    "付款方式",
    "服务地点",
    "服务期限",
    "预算",
    "最高限价",
    "包号",
    "标段号",
)


def resolve_protected_field_profile(
    tender_type: Any,
) -> ProtectedFieldProfile | None:
    """返回该招标类型的受保护字段 profile；direct_replace 类型返回 None。"""
    normalized_type = str(tender_type or "").strip()
    if not normalized_type:
        return None
    try:
        content_update_mode = get_content_update_mode(normalized_type)
    except Exception:
        return None
    if content_update_mode != CONTENT_UPDATE_MODE_PROTECTED_FIELDS:
        return None
    try:
        return get_protected_field_profile(normalized_type)
    except Exception:
        return None


def _marker_field_names(profile: ProtectedFieldProfile) -> tuple[str, ...]:
    names: list[str] = []
    for marker in profile.ordered_markers:
        try:
            names.append(extract_protected_field_name(marker))
        except Exception:
            stripped = str(marker or "").rstrip(":：").strip()
            if stripped:
                names.append(stripped)
    return tuple(names)


def _finding_requests_protected_field_deletion(
    finding: AuditFinding,
    field_names: tuple[str, ...],
) -> bool:
    """判断 finding 是否在要求删除受保护字段行。

    只有同时命中“删除类动词”和“受保护字段名”才视为越界删除建议；只提及字段名
    但 fix_hint 是“补回/保留/恢复”的不视为删除建议。
    """
    combined = f"{finding.evidence}\n{finding.fix_hint}"
    has_delete_verb = any(verb in combined for verb in _PROTECTED_FIELD_DELETE_VERBS)
    if not has_delete_verb:
        return False
    return any(field_name in combined for field_name in field_names)


def _current_text_has_field(current_text: str, field_names: tuple[str, ...]) -> set[str]:
    """返回当前正文里已经出现的受保护字段名集合（按字段名统计）。"""
    lines = str(current_text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    present: set[str] = set()
    for field_name in field_names:
        marker = f"{field_name}："
        for line in lines:
            if match_protected_field_line(line, marker) is not None:
                present.add(field_name)
                break
    return present


def _resolve_template_field_line(
    template_reference_text: str,
    field_name: str,
    *,
    package_index: int | None,
) -> str | None:
    """从参考模板里找到指定字段的字段行原句。

    多包场景按包序号优先匹配：先把参考模板按“第N包/包N/包件N”切分成段，
    package_index 指向同序号的包；找不到同包时回退到全局第一个可用字段行。
    package_index 为 None 或非正数时直接走全局第一个。
    """
    normalized = str(template_reference_text or "")
    if not normalized:
        return None

    candidate_lines = _lines_for_package(normalized, package_index)
    for line in candidate_lines:
        if match_protected_field_line(line, f"{field_name}：") is not None:
            return line.strip()

    # 找不到同包字段行时，回退到参考中第一个可用字段行（不限包）。
    for line in normalized.split("\n"):
        if match_protected_field_line(line, f"{field_name}：") is not None:
            return line.strip()
    return None


def _lines_for_package(text: str, package_index: int | None) -> list[str]:
    """按“第N包/包N/包件N”切分参考文本，返回目标包对应行。

    package_index 为 None 或 <=0 时返回全部行（不做包过滤）。
    无法识别包段时也返回全部行，保证不误删字段。
    """
    if package_index is None or package_index <= 0:
        return text.split("\n")
    target = package_index
    segments = _split_by_package_markers(text)
    if not segments:
        return text.split("\n")
    for index, segment in enumerate(segments, start=1):
        if index == target:
            return segment
    # 参考模板包数不足时退回第一个包；最坏退回全文。
    return segments[0] if segments else text.split("\n")


def _split_by_package_markers(text: str) -> list[list[str]]:
    """把参考文本按包/标段标题切分成段；识别不到任何包标题时返回空列表。"""
    lines = str(text or "").split("\n")

    package_pattern = re.compile(
        r"^\s*(?:第\s*[一二三四五六七八九十0-9]+\s*包"
        r"|包\s*件?\s*[一二三四五六七八九十0-9]+"
        r"|标\s*段\s*[一二三四五六七八九十0-9]+).*$",
    )
    segments: list[list[str]] = []
    current: list[str] | None = None
    saw_package = False
    for line in lines:
        if package_pattern.match(line):
            saw_package = True
            current = []
            segments.append(current)
        if current is None:
            current = []
            segments.append(current)
        current.append(line)
    return segments if saw_package else []


def _backfill_findings(
    *,
    missing_field_names: Iterable[str],
    template_reference_text: str,
    package_index: int | None,
) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    for field_name in missing_field_names:
        template_line = _resolve_template_field_line(
            template_reference_text,
            field_name,
            package_index=package_index,
        )
        if template_line:
            evidence = (
                f"待审核正文缺少受保护基础信息字段 `{field_name}：`，"
                f"该字段来自参考模板 `{template_line}`，受保护字段不得删除。"
            )
            fix_hint = (
                f"按参考模板同包字段行恢复 `{template_line}` 这类字段行，"
                "保留模板字段名、冒号和相对顺序；当前项目材料未提供新值时"
                "保留模板原值或占位表达，保持其它内容不变。"
            )
        else:
            evidence = (
                f"待审核正文缺少受保护基础信息字段 `{field_name}：`，"
                "该字段属于受保护字段，不得删除。"
            )
            fix_hint = (
                f"恢复 `{field_name}：` 字段行，保留字段名和冒号；"
                "当前项目材料未提供新值时保留模板占位/固定表达，保持其它内容不变。"
            )
        findings.append(AuditFinding(evidence=evidence, fix_hint=fix_hint))
    return findings


def sanitize_protected_field_findings(
    *,
    findings: list[AuditFinding],
    tender_type: Any,
    current_text: str,
    template_reference_text: Any,
    package_index: int | None = None,
    backfill_missing: bool = True,
) -> list[AuditFinding]:
    """对 LLM 审核 JSON 做受保护字段确定性净化。

    Args:
        findings: LLM 审核产出的 finding 列表（已通过 noop/coerce 净化）。
        tender_type: 招标类型；direct_replace 类型直接原样返回。
        current_text: 当前待审核正文。
        template_reference_text: 参考模板文本，用于补回字段行。
        package_index: 当前包序号（多包场景按包继承模板字段）；None/<=0 表示
            不做包过滤。
        backfill_missing: 是否对当前正文缺失的受保护字段追加“补回字段行”
            的 finding。verify 阶段应 True（字段存在性属于审核范围）；
            revise 阶段应 False（只做删除过滤，不引入新 finding，避免与
            “空审核跳过修订”契约冲突）。

    Returns:
        净化后的 finding 列表：先丢弃要求删除受保护字段的 finding；当
        backfill_missing=True 时再对当前正文缺失的受保护字段追加“补回字段行”
        的确定性 finding。
    """
    profile = resolve_protected_field_profile(tender_type)
    if profile is None:
        return list(findings)

    field_names = _marker_field_names(profile)
    if not field_names:
        return list(findings)

    sanitized = [
        finding
        for finding in findings
        if not _finding_requests_protected_field_deletion(finding, field_names)
    ]

    if not backfill_missing:
        return sanitized

    normalized_reference = str(template_reference_text or "")
    reference_lines = normalized_reference.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    present_fields = _current_text_has_field(current_text, field_names)
    # 回填启发式：只在参考模板里存在对应字段行时才要求补回该字段。
    # 这样避免对抽象测试文本或不含字段的旧正文误报；真实流水线里参考模板
    # 始终含受保护字段（字段壳来自模板），不会漏报。
    missing_field_names: list[str] = []
    for field_name in field_names:
        if field_name in present_fields:
            continue
        if not any(
            match_protected_field_line(line, f"{field_name}：") is not None
            for line in reference_lines
        ):
            continue
        missing_field_names.append(field_name)
    if missing_field_names:
        sanitized.extend(
            _backfill_findings(
                missing_field_names=missing_field_names,
                template_reference_text=normalized_reference,
                package_index=package_index,
            )
        )
    return sanitized


__all__ = [
    "resolve_protected_field_profile",
    "sanitize_protected_field_findings",
]
