"""
LLM 生成正文清洗器（content_sanitizer）

统一的“AI 输出 → 进入 draft/revision/final/polished_text 前的确定性清洗层”。
本模块只做纯文本清洗，不依赖 LLM；目的是把“抽取出来是什么，AI 就生成什么”
固化为可复用的硬约束，而不是依赖模型自觉。

清洗范围：
1. 删除 AI 自述/包装语（“好的，已收到您的指令”“以下是重构后的招标文件”等）。
2. 删除最终说明、内部自检、问候语、致谢、解释段落。
3. 删除 Markdown 装饰外壳（代码块包裹、多余的 `**`/`#`/`---`）。
4. 删除无信息占位句（“须提供详细技术参数要求/须提供详细配置清单”等兜底句）。

清洗后若仍残留明显不像采购需求正文的内容，调用方可结合现有协议报错或进入审核，
本模块只负责清洗，不静默写 Word。

设计约束：
- 结构化表占位符 `[[TABLE:id]]` 是内部写回入口，不在此层删除；它的可见性由
  convert_lines_to_items / table_placeholder_utils 在写回阶段统一处理。
- 技术符号（≥/±/×/Ω/SpO₂）、重要性标识（★/▲/Δ/△/*/#/※/●）是正文语义，
  不得被清洗；清洗器只命中明确的 AI 包装/无信息兜底句。
- 正常采购需求正文（条款、参数、表格行）不被误删。
"""

from __future__ import annotations

import re
from typing import Any

from backend.agents.generation.table_placeholder_utils import (
    TABLE_PLACEHOLDER_EXTRACT_RE,
)

# ---------------------------------------------------------------------------
# 常量：需要被清洗的 AI 包装 / 无信息兜底模式
# ---------------------------------------------------------------------------

# 整段被 ```markdown ... ``` / ``` ... ``` 包裹时，去掉代码块外壳，保留内部文本。
_CODE_FENCE_RE = re.compile(
    r"^\s*```[a-zA-Z]*\s*\n(?P<body>.*?)\n?\s*```\s*$",
    re.DOTALL,
)

# AI 自述/包装/解释类整行（独占一行时才清洗，避免误伤正文里的短语）。
# 命中后整行删除；这里只覆盖明确的“对话式”或“总结式”开头，允许其后跟对话续写。
_AI_PREAMBLE_LINE_RE = re.compile(
    r"^\s*(?:"
    # “好的/收到”开头，整行是对话式开场，后续不论写什么都删除。
    r"(?:好的|好[，,]?|收到|你好|您好)[，,。!！\s]*[^\n]*"
    # “以下是/这是 + 重构/生成/... 的招标文件/采购需求/正文/内容/结果”整行。
    r"|(?:以下|这)(?:是|就是)?(?:重构|生成|修改|修订|最终|完整)[^\n]{0,30}(?:招标(?:文件|正文)?|采购需求|正文|结果|内容)?[^\n]*"
    r"|根据(?:您?的|您的)(?:指令|要求|指示|需求)[^\n]{0,40}"
    r"|我(?:已经?|已|将|会|现在)?(?:为您?)?(?:完成|生成|重构|修订|整理|输出|列出)[^\n]{0,40}"
    r"|请?(?:参考|查看|核对|确认)(?:以下|上述)?(?:重构|生成|修改|修订|最终|完整)[^\n]{0,40}"
    r"|以上(?:为|是|内容|就是)[^\n]{0,30}(?:重构|生成|修改|修订|最终|结果|内容)[^\n]*"
    r"|希望(?:对您|这|以上)[^\n]{0,40}"
    r"|如有[^\n]{0,20}(?:需要|问题|疑问|修改|调整)[^\n]{0,40}"
    r"|作为(?:一个|一台)?AI[^\n]{0,40}"
    r"|(?:注|说明|备注)[：:][^\n]{0,10}(?:以上|上述|本)?(?:内容|正文|结果)?(?:为|是)?(?:按|根据|基于)[^\n]{0,40}"
    r")\s*$",
    re.IGNORECASE,
)

# 末尾的总结/致谢/解释段（连续多行或单行），独占一行时清洗。
_AI_TAIL_LINE_RE = re.compile(
    r"^\s*(?:"
    r"(?:以上|上述|本次)(?:为|是|就是)?(?:最终|完整)?(?:重构|生成|修改|修订)?(?:后)?(?:的)?(?:招标(?:文件|正文)?|采购需求|正文|内容|结果)[^\n]{0,20}"
    r"|(?:请|欢迎)?(?:您|你)?(?:核对|确认|查阅|查看|参考)[^\n]{0,20}"
    r"|如有[^\n]{0,30}(?:需要|问题|疑问|修改|调整)[^\n]{0,30}(?:请|欢迎|可)[^\n]{0,30}"
    r"|谢谢[^\n]{0,10}"
    r")\s*$",
    re.IGNORECASE,
)

# 无信息占位句兜底（计划中点名要求删除）：
# “须提供详细技术参数要求”“须提供详细配置清单”等“看起来正式但无信息量”的兜底句。
# 这些是 B 类熔断的占位输出，不应进入最终 Word；真实缺失应按现有协议报错/审核。
_FILLER_PLACEHOLDER_LINE_RE = re.compile(
    r"^\s*(?:"
    # 编号前缀可选：`3、` / `（3）` / `3.1、` / `一、` 等
    r"(?:\d+(?:\.\d+)*[、.．)]?|（\d+）|\(\d+\)|[一二三四五六七八九十]+[、.．)])?\s*"
    r")?"
    r"须(?:提供|填写|明确)[^\n]{0,15}"
    r"(?:详细|完整|具体)?"
    r"(?:技术参数(?:要求)?|配置清单|技术要求|参数清单|配置要求|清单|参数|要求)"
    r"[^\n]{0,15}\s*$",
    re.IGNORECASE,
)

# 行内残留的 **加粗** / ### 标题装饰，清洗为纯文本（保留内部文字）。
_INLINE_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_INLINE_HEADING_RE = re.compile(r"^\s*(#{1,6})\s+(.+?)\s*$")

# Markdown 分隔线（独立一行的 --- / *** / ___）整行删除。
_HORIZONTAL_RULE_RE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")


# ---------------------------------------------------------------------------
# 清洗主函数
# ---------------------------------------------------------------------------


def _is_protected_placeholder_line(line: str) -> bool:
    """结构化表占位符行 [[TABLE:id]] 是内部写回入口，清洗时整行保留。"""
    stripped = line.strip()
    if not stripped:
        return False
    return bool(TABLE_PLACEHOLDER_EXTRACT_RE.fullmatch(stripped)) or bool(
        TABLE_PLACEHOLDER_EXTRACT_RE.search(stripped) and stripped.startswith("[[TABLE:")
    )


def _strip_code_fence(text: str) -> str:
    match = _CODE_FENCE_RE.match(text)
    if match is None:
        return text
    return match.group("body")


def _clean_inline_markdown(line: str) -> str:
    # 去掉 **加粗**，保留文字
    line = _INLINE_BOLD_RE.sub(r"\1", line)
    # 去掉行首 # 标题符，保留文字
    heading = _INLINE_HEADING_RE.match(line)
    if heading is not None:
        line = heading.group(2)
    return line


def _line_is_ai_noise(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if _AI_PREAMBLE_LINE_RE.match(stripped):
        return True
    if _AI_TAIL_LINE_RE.match(stripped):
        return True
    if _FILLER_PLACEHOLDER_LINE_RE.match(stripped):
        return True
    if _HORIZONTAL_RULE_RE.match(stripped):
        return True
    return False


def sanitize_generated_content(value: Any) -> str:
    """清洗 LLM 生成的采购需求正文，返回纯采购需求文本。

    步骤：
    1. 去掉外层 Markdown 代码块包裹。
    2. 逐行处理：保留 `[[TABLE:id]]` 占位符行；删除 AI 自述/包装/总结/无信息兜底句；
       清理行内 `**`/`#` 装饰；保留正常采购需求正文、技术符号、表格行。
    3. 压缩多余空行（连续空行合并为一个，去除首尾空白行）。

    不删除：`[[TABLE:id]]` 占位符、Markdown/pipe 表格行、技术符号、重要性标识、
    正常条款与参数正文。
    """
    text = str(value or "")
    if not text.strip():
        return ""

    text = _strip_code_fence(text)
    # 统一换行
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    raw_lines = text.split("\n")
    cleaned_lines: list[str] = []
    for line in raw_lines:
        if _is_protected_placeholder_line(line):
            # 占位符行原样保留（写回层决定恢复或丢弃），不被清洗。
            cleaned_lines.append(line.rstrip())
            continue
        if _line_is_ai_noise(line):
            continue
        cleaned = _clean_inline_markdown(line)
        cleaned_lines.append(cleaned.rstrip())

    # 压缩连续空行为单个，并去除首尾空白行。
    compressed: list[str] = []
    prev_blank = False
    for line in cleaned_lines:
        if line.strip() == "":
            if prev_blank:
                continue
            prev_blank = True
            compressed.append("")
            continue
        prev_blank = False
        compressed.append(line)

    while compressed and compressed[0].strip() == "":
        compressed.pop(0)
    while compressed and compressed[-1].strip() == "":
        compressed.pop()

    return "\n".join(compressed)


def looks_like_procurement_content(value: Any) -> bool:
    """粗判清洗后的文本是否仍像采购需求正文。

    供调用方在清洗后做二次把关：若清洗后为空或完全不像采购需求（例如只剩问候语
    或无信息占位句被全部清掉后空了），调用方可按现有协议报错或进入审核，
    而不是静默写 Word。这里只做轻量启发式判断，不做语义审核。
    """
    cleaned = sanitize_generated_content(value)
    if not cleaned.strip():
        return False
    # 至少存在一个“编号 + 条款”或“字段：值”或表格行或占位符的迹象。
    has_numbered_clause = bool(
        re.search(
            r"(?:^|\n)\s*(?:\d+(?:\.\d+)*[、.．)]|（\d+）|\(\d+\)|[一二三四五六七八九十]+[、.．)])\s*\S",
            cleaned,
        )
    )
    has_field_value = bool(re.search(r"[：:]\s*\S", cleaned))
    has_table_row = "|" in cleaned or "/" in cleaned
    has_placeholder = "[[TABLE:" in cleaned
    return has_numbered_clause or has_field_value or has_table_row or has_placeholder


__all__ = [
    "sanitize_generated_content",
    "looks_like_procurement_content",
]
