"""
Word 文档提取工具函数
提供统一的 Word 文档内容提取功能，包括上标/下标识别、表格提取、自动编号保留等
"""

import re
import logging
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)
import pathlib
import time
from typing import Any, Optional

from backend.util.word_util.word_application_util import (
    create_word_application,
    close_word_application,
    open_document_with_retry,
)
from backend.util.word_util.table_models import (
    StructuredTableModel,
    render_structured_table_markdown,
)


# Unicode 上标和下标字符映射表
SUPERSCRIPT_MAP = {
    "0": "⁰",
    "1": "¹",
    "2": "²",
    "3": "³",
    "4": "⁴",
    "5": "⁵",
    "6": "⁶",
    "7": "⁷",
    "8": "⁸",
    "9": "⁹",
    "+": "⁺",
    "-": "⁻",
    "=": "⁼",
    "(": "⁽",
    ")": "⁾",
    "n": "ⁿ",
    "i": "ⁱ",
}

SUBSCRIPT_MAP = {
    "0": "₀",
    "1": "₁",
    "2": "₂",
    "3": "₃",
    "4": "₄",
    "5": "₅",
    "6": "₆",
    "7": "₇",
    "8": "₈",
    "9": "₉",
    "+": "₊",
    "-": "₋",
    "=": "₌",
    "(": "₍",
    ")": "₎",
    "a": "ₐ",
    "e": "ₑ",
    "o": "ₒ",
    "x": "ₓ",
}

WORD_XML_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

# Symbol 字体（w:font="Symbol"）通过 <w:sym w:char="xxxx"/> 表示特殊字符，
# char 是十六进制私有区码位（Symbol 字体内部编码），需要在抽取阶段映射回可见字符，
# 否则下游会看到乱码或空。这里覆盖常见的标书/技术参数符号。
# char 属性值大小写不敏感，统一按大写匹配。
SYMBOL_FONT_NAME = "symbol"
# 关键：Word 把 Delta（Δ）画成 <w:sym w:font="Symbol" w:char="F044"/>。
# 抽取层必须把它转成可见 Δ，否则重要性标识会丢失，导致生成/审核/写回链路整体失真。
SYMBOL_FONT_CHAR_MAP = {
    "F044": "Δ",  # 增量符号 Delta，标书中常用作紧邻编号的重要性标识
    "F0D7": "Δ",  # 部分模板用 D7 表示 Delta
    "F0E5": "D",  # Symbol 'D'
    "F0B1": "±",  # 加减号
    "F0B4": "×",  # 乘号
    "F0B0": "°",  # 度
    "F051": "Ö",  # 欧姆符号 Ö/Ω 在不同字体中映射
    "F0B3": "³",  # 上标 3
    "F0B2": "²",  # 上标 2
    "F0B0": "°",
    "F0A8": "·",  # 中点
    "F0A9": "√",  # 对号
    "F0BF": "￮",
}


def _resolve_sym_element(run_content: str) -> str:
    """从 <w:r> 内容中解析 <w:sym w:font="..." w:char="..."/>，返回可见字符或空串。

    Symbol 字体的 sym 元素不产生可见文本，必须显式映射；只有 font 为 Symbol
    且 char 命中映射表时才替换，其它情况返回空串（保持原有跳过行为）。
    """
    sym_match = re.search(
        r'<w:sym\s+[^>]*?w:font=["\']([^"\']+)["\'][^>]*?w:char=["\']([0-9A-Fa-f]+)["\']',
        run_content,
    )
    if sym_match is None:
        # 兼容属性顺序相反的写法：char 在前，font 在后
        sym_match = re.search(
            r'<w:sym\s+[^>]*?w:char=["\']([0-9A-Fa-f]+)["\'][^>]*?w:font=["\']([^"\']+)["\']',
            run_content,
        )
        if sym_match is None:
            return ""
        char_code = sym_match.group(1)
        font_name = sym_match.group(2)
    else:
        font_name = sym_match.group(1)
        char_code = sym_match.group(2)
    if str(font_name or "").strip().lower() != SYMBOL_FONT_NAME:
        return ""
    return SYMBOL_FONT_CHAR_MAP.get(str(char_code or "").strip().upper(), "")


def _xml_unescape(text):
    return (
        text.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&apos;", "'")
    )


def _strip_xml_comments(xml_content: str) -> str:
    try:
        xml_content = re.sub(
            r"<w:comments\b[^\u003e]*>.*?</w:comments>",
            "",
            xml_content,
            flags=re.DOTALL,
        )
        xml_content = re.sub(
            r"<w:comment\b[^\u003e]*>.*?</w:comment>",
            "",
            xml_content,
            flags=re.DOTALL,
        )
        xml_content = re.sub(
            r"<w:annotation\b[^\u003e]*>.*?</w:annotation>",
            "",
            xml_content,
            flags=re.DOTALL,
        )
    except Exception as e:
        logger.debug(f"[_strip_xml_comments] 清理注释标签失败（可忽略）: {e}")
    return xml_content


def _build_xml_run_patterns():
    run_pattern = re.compile(r"<w:r\b[^\u003e]*>(.*?)</w:r>", re.DOTALL)
    align_pattern = re.compile(
        r'<w:vertAlign\s+w:val=["\'](superscript|subscript)["\']\s*/>'
    )
    position_pattern = re.compile(r'<w:position\s+w:val=["\'](-?\d+)["\']\s*/>')
    text_pattern = re.compile(r"<w:t\b[^\u003e]*>(.*?)</w:t>", re.DOTALL)
    return run_pattern, align_pattern, position_pattern, text_pattern


def _process_run_text(run_content, align_pattern, position_pattern, text_pattern):
    if (
        "<w:commentReference" in run_content
        or "<w:commentRangeStart" in run_content
        or "<w:commentRangeEnd" in run_content
        or "<w:annotationRef" in run_content
    ):
        return ""

    is_superscript = False
    is_subscript = False

    align_match = align_pattern.search(run_content)
    if align_match:
        val = align_match.group(1)
        if val == "superscript":
            is_superscript = True
        elif val == "subscript":
            is_subscript = True

    if not is_superscript and not is_subscript:
        pos_match = position_pattern.search(run_content)
        if pos_match:
            try:
                val = int(pos_match.group(1))
                if val >= 4:
                    is_superscript = True
                elif val <= -4:
                    is_subscript = True
            except Exception as e:
                logger.debug(f"[_process_run_text] 解析position偏移失败（可忽略）: {e}")

    run_texts = []
    # Symbol 字体（如 <w:sym w:font="Symbol" w:char="F044"/>）不产生 <w:t>，
    # 必须先把映射后的可见字符（如 Δ）拼到 run 文本前部，保证段落/cell/prompt context 一致。
    sym_char = ""
    if "<w:sym" in run_content:
        try:
            sym_char = _resolve_sym_element(run_content)
        except Exception as e:
            logger.debug(f"[_process_run_text] 解析 w:sym 失败（可忽略）: {e}")
            sym_char = ""
    if sym_char:
        run_texts.append(sym_char)

    text_matches = text_pattern.finditer(run_content)
    for tm in text_matches:
        raw_text = tm.group(1)
        text = _xml_unescape(raw_text)

        if is_superscript:
            run_texts.append("".join(SUPERSCRIPT_MAP.get(char, char) for char in text))
        elif is_subscript:
            run_texts.append("".join(SUBSCRIPT_MAP.get(char, char) for char in text))
        else:
            run_texts.append(text)

    return "".join(run_texts)


def _iter_paragraph_texts_from_xml(
    parent,
) -> list[str]:
    para_texts: list[str] = []
    for para in parent.findall(".//w:p", WORD_XML_NS):
        run_texts = []
        for run in para.findall(".//w:r", WORD_XML_NS):
            if (
                run.find(".//w:commentReference", WORD_XML_NS) is not None
                or run.find(".//w:commentRangeStart", WORD_XML_NS) is not None
                or run.find(".//w:commentRangeEnd", WORD_XML_NS) is not None
                or run.find(".//w:annotationRef", WORD_XML_NS) is not None
            ):
                continue

            is_superscript = False
            is_subscript = False
            vert_align = run.find(".//w:vertAlign", WORD_XML_NS)
            if vert_align is not None:
                val = (
                    vert_align.attrib.get(f"{{{WORD_XML_NS['w']}}}val", "").strip().lower()
                )
                if val == "superscript":
                    is_superscript = True
                elif val == "subscript":
                    is_subscript = True

            if not is_superscript and not is_subscript:
                position = run.find(".//w:position", WORD_XML_NS)
                if position is not None:
                    try:
                        pos_val = int(position.attrib.get(f"{{{WORD_XML_NS['w']}}}val", "0") or 0)
                        if pos_val >= 4:
                            is_superscript = True
                        elif pos_val <= -4:
                            is_subscript = True
                    except Exception as e:
                        logger.debug(f"[_iter_paragraph_texts_from_xml] 解析position失败（可忽略）: {e}")

            texts = []
            # Symbol 字体 sym 元素（如 <w:sym w:font="Symbol" w:char="F044"/> -> Δ）
            # 不产生 <w:t>，必须先把映射后的可见字符拼到 run 文本前，保证 cell/prompt
            # context 与段落抽取一致。
            sym_char = ""
            for sym_node in run.findall(".//w:sym", WORD_XML_NS):
                font_name = str(
                    sym_node.attrib.get(f"{{{WORD_XML_NS['w']}}}font", "") or ""
                ).strip().lower()
                char_code = str(
                    sym_node.attrib.get(f"{{{WORD_XML_NS['w']}}}char", "") or ""
                ).strip().upper()
                if font_name != SYMBOL_FONT_NAME or not char_code:
                    continue
                mapped = SYMBOL_FONT_CHAR_MAP.get(char_code, "")
                if mapped:
                    sym_char = mapped
                    break
            if sym_char:
                texts.append(sym_char)
            for text_node in run.findall(".//w:t", WORD_XML_NS):
                text_value = _xml_unescape(text_node.text or "")
                if is_superscript:
                    texts.append("".join(SUPERSCRIPT_MAP.get(char, char) for char in text_value))
                elif is_subscript:
                    texts.append("".join(SUBSCRIPT_MAP.get(char, char) for char in text_value))
                else:
                    texts.append(text_value)
            if texts:
                run_texts.append("".join(texts))
        if run_texts:
            para_texts.append("".join(run_texts))
    return para_texts


def _parse_table_model_from_table_xml(
    table_xml: str,
    *,
    table_id: str,
) -> Optional[StructuredTableModel]:
    try:
        table_root = ET.fromstring(table_xml)
    except ET.ParseError as exc:
        logger.debug(f"[_parse_table_model_from_table_xml] 解析表格 XML 失败（可忽略）: {exc}")
        return None

    rows = table_root.findall("./w:tr", WORD_XML_NS)
    if not rows:
        return None

    cells: list[dict[str, Any]] = []
    max_cols = 0

    for row_index, row in enumerate(rows, start=1):
        col_cursor = 1
        tc_elements = row.findall("./w:tc", WORD_XML_NS)
        if not tc_elements:
            continue

        for cell_elem in tc_elements:
            tc_pr = cell_elem.find("./w:tcPr", WORD_XML_NS)
            col_span = 1
            row_span = 1
            vmerge_kind: str | None = None

            if tc_pr is not None:
                grid_span = tc_pr.find("./w:gridSpan", WORD_XML_NS)
                if grid_span is not None:
                    raw_val = grid_span.attrib.get(f"{{{WORD_XML_NS['w']}}}val")
                    try:
                        col_span = max(1, int(raw_val or 1))
                    except Exception:
                        col_span = 1

                vmerge = tc_pr.find("./w:vMerge", WORD_XML_NS)
                if vmerge is not None:
                    raw_vmerge = vmerge.attrib.get(f"{{{WORD_XML_NS['w']}}}val")
                    vmerge_kind = str(raw_vmerge or "continue").strip().lower() or "continue"

            if vmerge_kind == "continue":
                col_cursor += col_span
                max_cols = max(max_cols, col_cursor - 1)
                continue

            cell_texts = _iter_paragraph_texts_from_xml(
                cell_elem,
            )
            cell_text = " ".join(text.strip() for text in cell_texts if text.strip()).strip()

            if vmerge_kind in {"restart", None}:
                lookahead_span = 1
                if vmerge_kind == "restart":
                    next_rows = rows[row_index:]
                    for next_row in next_rows:
                        next_col_cursor = 1
                        continued = False
                        for next_cell in next_row.findall("./w:tc", WORD_XML_NS):
                            next_tc_pr = next_cell.find("./w:tcPr", WORD_XML_NS)
                            next_col_span = 1
                            next_vmerge_kind: str | None = None
                            if next_tc_pr is not None:
                                next_grid_span = next_tc_pr.find("./w:gridSpan", WORD_XML_NS)
                                if next_grid_span is not None:
                                    raw_next_span = next_grid_span.attrib.get(
                                        f"{{{WORD_XML_NS['w']}}}val"
                                    )
                                    try:
                                        next_col_span = max(1, int(raw_next_span or 1))
                                    except Exception:
                                        next_col_span = 1
                                next_vmerge = next_tc_pr.find("./w:vMerge", WORD_XML_NS)
                                if next_vmerge is not None:
                                    raw_next_vmerge = next_vmerge.attrib.get(
                                        f"{{{WORD_XML_NS['w']}}}val"
                                    )
                                    next_vmerge_kind = (
                                        str(raw_next_vmerge or "continue").strip().lower()
                                        or "continue"
                                    )

                            if next_col_cursor == col_cursor:
                                if (
                                    next_col_span == col_span
                                    and next_vmerge_kind == "continue"
                                ):
                                    lookahead_span += 1
                                    continued = True
                                break
                            next_col_cursor += next_col_span
                        if not continued:
                            break
                row_span = lookahead_span

            cells.append(
                {
                    "row": row_index,
                    "col": col_cursor,
                    "row_span": row_span,
                    "col_span": col_span,
                    "text": cell_text,
                }
            )
            col_cursor += col_span
            max_cols = max(max_cols, col_cursor - 1)

    return StructuredTableModel(
        table_id=table_id,
        rows=len(rows),
        cols=max(1, max_cols),
        cells=cells,
    )


def extract_text_from_xml(xml_content, preserve_structure=False):
    """
    从 WordOpenXML 解析文本，识别上标/下标（支持 vertAlign 和 position）

    Args:
        xml_content: Word XML 内容字符串
        preserve_structure: 是否保留文档结构（段落换行、表格等）
                          True: 保留段落边界的换行符，适用于提取整个文档
                          False: 不保留换行，适用于提取单个单元格或段落内的文本

    Returns:
        str: 提取的文本，上标/下标字符已转换为Unicode上标/下标字符
    """
    try:
        xml_content = _strip_xml_comments(xml_content)

        run_pattern, align_pattern, position_pattern, text_pattern = (
            _build_xml_run_patterns()
        )

        if not preserve_structure:
            # 原始逻辑：不保留结构，适用于单个段落或单元格
            result = []
            pos = 0
            while True:
                match = run_pattern.search(xml_content, pos)
                if not match:
                    break

                run_content = match.group(1)
                pos = match.end()

                run_text = _process_run_text(
                    run_content, align_pattern, position_pattern, text_pattern
                )
                if run_text:
                    result.append(run_text)

            return "".join(result)

        else:
            # 保留结构模式：识别段落边界，保留换行和表格
            # 段落模式 <w:p>...</w:p>
            para_pattern = re.compile(r"<w:p\b[^\u003e]*>(.*?)</w:p>", re.DOTALL)
            # 表格模式 <w:tbl>...</w:tbl>
            table_pattern = re.compile(r"<w:tbl\b[^\u003e]*>(.*?)</w:tbl>", re.DOTALL)
            # 表格行 <w:tr>...</w:tr>
            row_pattern = re.compile(r"<w:tr\b[^\u003e]*>(.*?)</w:tr>", re.DOTALL)
            # 表格单元格 <w:tc>...</w:tc>
            cell_pattern = re.compile(r"<w:tc\b[^\u003e]*>(.*?)</w:tc>", re.DOTALL)

            result_parts = []

            # 按顺序处理内容：找到所有段落和表格，按位置排序处理
            # 先找出所有段落和表格的位置
            elements = []

            for match in para_pattern.finditer(xml_content):
                # 检查这个段落是否在表格内（如果在 <w:tbl> 和 </w:tbl> 之间则跳过）
                para_start = match.start()
                # 简单检查：往前找最近的 <w:tbl 和 </w:tbl>
                before_content = xml_content[:para_start]
                last_tbl_open = before_content.rfind("<w:tbl")
                last_tbl_close = before_content.rfind("</w:tbl>")
                # 如果最近的 <w:tbl 比 </w:tbl> 更靠后，说明在表格内
                if last_tbl_open > last_tbl_close:
                    continue  # 跳过表格内的段落，由表格处理
                elements.append(("para", match.start(), match.group(1)))

            for match in table_pattern.finditer(xml_content):
                elements.append(("table", match.start(), match.group(1)))

            # 按位置排序
            elements.sort(key=lambda x: x[1])

            for elem_type, _, content in elements:
                if elem_type == "para":
                    # 处理段落：提取所有 run 中的文本
                    para_texts = []
                    for run_match in run_pattern.finditer(content):
                        run_content = run_match.group(1)
                        run_text = _process_run_text(
                            run_content, align_pattern, position_pattern, text_pattern
                        )
                        if run_text:
                            para_texts.append(run_text)

                    para_text = "".join(para_texts)
                    if para_text.strip():  # 只添加非空段落
                        result_parts.append(para_text)

                elif elem_type == "table":
                    table_model = _parse_table_model_from_table_xml(
                        f"<w:tbl xmlns:w=\"{WORD_XML_NS['w']}\">{content}</w:tbl>",
                        table_id="XML_TABLE",
                    )
                    if table_model is not None:
                        table_markdown = render_structured_table_markdown(table_model)
                        if table_markdown:
                            result_parts.append(table_markdown)

            # 用换行符连接所有部分
            return "\n".join(result_parts)

    except Exception as e:
        logger.error(f"[extract_text_from_xml] XML解析失败: {e}", exc_info=True)
        return None


def extract_text_with_superscript_subscript(range_obj, use_xml=True):
    """
    提取WPS/Word范围中的文本，保留上标和下标格式

    优先使用 WordOpenXML 提取（支持 vertAlign 和 position 偏移），
    如果 XML 提取失败则回退到逐字符遍历方式。

    Args:
        range_obj: WPS/Word Range对象

    Returns:
        str: 提取的文本，上标/下标字符已转换为Unicode上标/下标字符
    """
    if use_xml:
        try:
            xml_content = None
            try:
                xml_content = range_obj.WordOpenXML
            except Exception as e:
                logger.debug(f"[extract_text_with_superscript_subscript] 获取WordOpenXML失败（可忽略）: {e}")
            if xml_content and isinstance(xml_content, str) and len(xml_content) > 0:
                xml_text = extract_text_from_xml(xml_content)
                if xml_text is not None:
                    return xml_text
        except Exception as e:
            logger.warning(f"[extract_text_with_superscript_subscript] WordOpenXML提取异常，回退到逐字符遍历: {e}")

    # 策略2: 回退到逐字符遍历 (增强版，支持位置偏移检测)
    try:
        result = []
        characters = range_obj.Characters
        char_count = characters.Count

        # 遍历每个字符
        for i in range(1, char_count + 1):
            try:
                char = characters(i)
                char_text = char.Text
                font = char.Font

                try:
                    if char_text and len(char_text) == 1:
                        code = ord(char_text)
                        if code < 32 and char_text not in ("\r", "\n", "\t"):
                            continue
                except Exception as e:
                    logger.debug(f"[extract_text_with_superscript_subscript] 字符代码检查失败（可忽略）: {e}")

                # 检查是否是上标
                is_superscript = False
                is_subscript = False

                # 检查上标 (包括标准上标属性和位置偏移)
                try:
                    sup_val = font.Superscript
                    # Word COM 返回 -1 或 True 表示上标，0 或 False 表示否
                    # 9999999 (wdUndefined) 表示混合状态，不应视为上标
                    if sup_val == -1 or sup_val == True:
                        is_superscript = True
                    else:
                        # 检查位置偏移 (单位：磅)
                        # 如果没有开启 Superscript，但位置提升了 > 1.5 磅，也视为上标
                        try:
                            pos_val = font.Position
                            if pos_val > 1.5:
                                is_superscript = True
                        except Exception as e:
                            logger.debug(f"[extract_text_with_superscript_subscript] 获取font.Position失败（上标检测，可忽略）: {e}")
                except Exception as e:
                    logger.debug(f"[extract_text_with_superscript_subscript] 上标检测失败（可忽略）: {e}")

                # 检查下标
                try:
                    sub_val = font.Subscript
                    if sub_val == -1 or sub_val == True:
                        is_subscript = True
                    elif not is_superscript:
                        # 检查位置偏移 (负值表示下移)
                        try:
                            pos_val = font.Position
                            if pos_val < -1.5:
                                is_subscript = True
                        except Exception as e:
                            logger.debug(f"[extract_text_with_superscript_subscript] 获取font.Position失败（下标检测，可忽略）: {e}")
                except Exception as e:
                    logger.debug(f"[extract_text_with_superscript_subscript] 下标检测失败（可忽略）: {e}")

                # 根据上标/下标状态转换字符
                if is_superscript and char_text in SUPERSCRIPT_MAP:
                    result.append(SUPERSCRIPT_MAP[char_text])
                elif is_subscript and char_text in SUBSCRIPT_MAP:
                    result.append(SUBSCRIPT_MAP[char_text])
                else:
                    result.append(char_text)

            except Exception as char_e:
                # 如果处理某个字符失败，尝试获取原始文本
                try:
                    result.append(characters(i).Text)
                except Exception as e:
                    logger.debug(f"[extract_text_with_superscript_subscript] 获取字符原始文本失败（可忽略）: {e}")

        return "".join(result)

    except Exception as e:
        # 最终回退
        logger.error(f"[extract_text_with_superscript_subscript] 提取带上标/下标文本时出错: {e}")
        try:
            return range_obj.Text
        except Exception as fallback_e:
            logger.warning(f"[extract_text_with_superscript_subscript] 获取range_obj.Text失败: {fallback_e}")
            return ""


def extract_table_as_text(table):
    """
    提取WPS/Word表格，转换为Markdown表格格式，便于大模型理解表格结构

    Args:
        table: WPS/Word表格对象

    Returns:
        str: Markdown格式的表格文本
    """
    try:
        rows_count = table.Rows.Count
        cols_count = table.Columns.Count

        if rows_count == 0 or cols_count == 0:
            return table.Range.Text

        table_data = []
        for row_idx in range(1, rows_count + 1):
            row_data = []
            for col_idx in range(1, cols_count + 1):
                try:
                    cell = table.Cell(row_idx, col_idx)
                    cell_text = extract_text_with_superscript_subscript(
                        cell.Range, use_xml=False
                    )
                    cell_text = cell_text.rstrip("\r\x07\n")
                    cell_text = cell_text.replace("\r\n", "\n").replace("\r", "\n")
                    cell_text = cell_text.replace("\x07", "")
                    cell_text = cell_text.strip()
                    cell_text = cell_text.replace("\n", "\\n")
                    cell_text = cell_text.replace("|", "\\|")
                    row_data.append(cell_text)
                except Exception as cell_e:
                    # 某些合并单元格可能无法访问，填充空字符串
                    logger.debug(f"[extract_table_as_text] 访问表格单元格失败（合并单元格，可忽略）: {cell_e}")
                    row_data.append("")
            table_data.append(row_data)

        if not table_data:
            return extract_text_with_superscript_subscript(table.Range, use_xml=False)

        # 构建Markdown表格
        markdown_lines = []

        # 表头行
        header_row = table_data[0]
        markdown_lines.append("| " + " | ".join(header_row) + " |")

        # 分隔行
        separator = "| " + " | ".join(["---"] * len(header_row)) + " |"
        markdown_lines.append(separator)

        # 数据行
        for row_data in table_data[1:]:
            # 确保每行列数与表头一致
            while len(row_data) < len(header_row):
                row_data.append("")
            row_data = row_data[: len(header_row)]  # 截断多余的列
            markdown_lines.append("| " + " | ".join(row_data) + " |")

        return "\n".join(markdown_lines)

    except Exception as e:
        logger.error(f"[extract_table_as_text] 提取表格时出错: {e}", exc_info=True)
        # 如果出错，回退到原始文本提取
        try:
            return extract_text_with_superscript_subscript(table.Range)
        except Exception as fallback_e:
            logger.warning(f"[extract_table_as_text] 回退提取也失败: {fallback_e}")
            return ""


def extract_text_with_list_numbers(range_obj):
    """
    提取WPS/Word范围中的文本，保留自动编号

    Args:
        range_obj: WPS/Word Range对象

    Returns:
        str: 提取的文本，包含自动编号
    """
    try:
        result_lines = []
        paragraphs = []

        # 尝试多种方法获取段落列表（增强的错误处理）
        try:
            # 方法1: 直接转换为列表（适用于某些 Range 对象）
            paragraphs = list(range_obj.Paragraphs)
        except Exception as e1:
            # 方法2: 使用索引访问（适用于不支持枚举的 Range 对象）
            try:
                para_count = range_obj.Paragraphs.Count
                for i in range(1, para_count + 1):
                    try:
                        para = range_obj.Paragraphs(i)
                        paragraphs.append(para)
                    except Exception as e:
                        logger.debug(f"[extract_text_with_list_numbers] 获取段落对象失败（可忽略）: {e}")
            except Exception as e2:
                # 方法3: 尝试直接迭代（某些情况下可能有效）
                try:
                    for para in range_obj.Paragraphs:
                        paragraphs.append(para)
                except Exception as e3:
                    # 所有方法都失败，使用直接文本提取
                    # 检查是否是对象删除错误
                    error_msgs = [str(e1), str(e2), str(e3)]
                    has_deleted_error = any(
                        "对象已被删除" in str(e)
                        or "无效指针" in str(e)
                        or "-2147467261" in str(e)
                        or "-2147352567" in str(e)
                        for e in error_msgs
                    )

                    if has_deleted_error:
                        logger.warning(f"[extract_text_with_list_numbers] 检测到对象失效，使用直接文本提取")
                    else:
                        logger.warning(
                            f"[extract_text_with_list_numbers] 无法获取段落列表，使用直接文本提取: {e1}, {e2}, {e3}"
                        )

                    try:
                        # 尝试使用上标/下标提取
                        text = extract_text_with_superscript_subscript(range_obj)
                        if text:
                            return text
                    except Exception as text_e:
                        logger.error(f"[extract_text_with_list_numbers] 直接文本提取也失败: {text_e}")
                        return ""
                    return ""

        for para in paragraphs:
            try:
                # 检查段落对象是否有效
                try:
                    para_range = para.Range
                except Exception as para_check:
                    # 如果段落对象已失效，跳过
                    if "对象已被删除" in str(para_check) or "无效指针" in str(
                        para_check
                    ):
                        continue
                    raise

                # 检查是否有自动编号
                list_format = para_range.ListFormat
                has_list = False
                list_string = ""

                try:
                    # 尝试获取列表类型（如果ListType > 0，说明有自动编号）
                    list_type = list_format.ListType
                    if list_type > 0:
                        has_list = True
                        # 获取编号文本（如"1."、"1.1"等）
                        try:
                            list_string = list_format.ListString
                        except Exception as e:
                            logger.debug(f"[extract_text_with_list_numbers] 获取ListString失败（可忽略）: {e}")
                            # 如果获取ListString失败，尝试其他方法
                            try:
                                # 某些版本可能使用ListValue
                                list_string = str(list_format.ListValue) + "."
                            except Exception as e:
                                logger.debug(f"[extract_text_with_list_numbers] 获取ListValue也失败（可忽略）: {e}")
                                list_string = ""
                except Exception as e:
                    # 如果无法获取ListType，尝试直接获取ListString
                    logger.debug(f"[extract_text_with_list_numbers] 获取ListType失败（可忽略）: {e}")
                    try:
                        list_string = list_format.ListString
                        if list_string:
                            has_list = True
                    except Exception as e2:
                        logger.debug(f"[extract_text_with_list_numbers] 获取ListString也失败（可忽略）: {e2}")

                # 获取段落文本，保留原始内容和上标/下标格式
                para_text = extract_text_with_superscript_subscript(para_range)

                if para_text:
                    # 获取原文档中段落的实际文本，以保留换行格式
                    try:
                        original_para_text = para_range.Text
                        # 检查原文档段落末尾是否有换行符（通常是 \r）
                        has_trailing_newline = original_para_text.endswith(
                            "\r"
                        ) or original_para_text.endswith("\n")
                        # 清理特殊控制字符
                        para_text_clean = para_text.replace("\x07", "")
                        # 如果原文档有换行符，但提取的文本没有，则添加
                        if has_trailing_newline and not (
                            para_text_clean.endswith("\r")
                            or para_text_clean.endswith("\n")
                        ):
                            # 使用原文档的换行符格式
                            if original_para_text.endswith("\r\n"):
                                para_text_clean += "\r\n"
                            elif original_para_text.endswith("\r"):
                                para_text_clean += "\r"
                            elif original_para_text.endswith("\n"):
                                para_text_clean += "\n"
                    except Exception as e:
                        # 如果无法获取原文档文本，只清理特殊字符
                        logger.debug(f"[extract_text_with_list_numbers] 获取原文档段落文本失败（可忽略）: {e}")
                        para_text_clean = para_text.replace("\x07", "")

                    if has_list and list_string:
                        # 如果有自动编号，将编号添加到文本前
                        # 检查文本开头是否已经包含编号（避免重复）
                        # 去除编号字符串两端的空格（编号本身不应该有前后空格）
                        list_string_clean = list_string.strip()
                        # 检查去除前导空白后的文本是否以编号开头
                        para_text_stripped = para_text_clean.lstrip()
                        if para_text_stripped and para_text_stripped.startswith(
                            list_string_clean
                        ):
                            # 文本已经包含编号，直接使用原始文本（保留所有格式包括换行）
                            result_lines.append(para_text_clean)
                        else:
                            # 文本不包含编号，添加编号
                            result_lines.append(
                                list_string_clean + " " + para_text_clean
                            )
                    else:
                        # 没有自动编号，直接添加原始文本（保留所有格式包括换行）
                        result_lines.append(para_text_clean)

            except Exception as para_e:
                # 如果处理某个段落失败，回退到直接提取文本（带上标/下标）
                # 检查是否是对象删除错误
                if "对象已被删除" in str(para_e) or "无效指针" in str(para_e):
                    # 对象已失效，跳过这个段落
                    continue
                try:
                    para_text = extract_text_with_superscript_subscript(para.Range)
                    if para_text:
                        result_lines.append(para_text)
                except Exception as e:
                    # 如果连文本都无法获取，跳过这个段落
                    logger.debug(f"[extract_text_with_list_numbers] 回退提取段落文本失败（可忽略）: {e}")

        # 如果没有提取到任何内容，回退到直接提取文本（带上标/下标）
        if not result_lines:
            return extract_text_with_superscript_subscript(range_obj)

        # 直接连接所有段落文本，保留原文档的实际格式（包括换行符）
        # 不统一添加换行，让原文档的格式自然保留
        return "".join(result_lines)

    except Exception as e:
        logger.error(f"[extract_text_with_list_numbers] 提取带编号文本时出错: {e}", exc_info=True)
        # 如果出错，回退到带上标/下标的文本提取
        try:
            return extract_text_with_superscript_subscript(range_obj)
        except Exception as fallback_e:
            # 如果连文本都无法获取，返回空字符串
            logger.warning(f"[extract_text_with_list_numbers] 无法提取任何文本内容: {fallback_e}")
            return ""


def extract_content_with_tables(range_obj):
    """
    提取WPS/Word范围中的内容，包括表格，保留表格格式和自动编号

    Args:
        range_obj: WPS/Word Range对象

    Returns:
        str: 提取的内容，表格已格式化，自动编号已保留
    """
    try:
        # 获取范围内的所有表格（增强的错误处理）
        tables = []
        try:
            # 方法1: 直接转换为列表
            tables = list(range_obj.Tables)
        except Exception as e1:
            # 方法2: 使用索引访问
            try:
                table_count = range_obj.Tables.Count
                for i in range(1, table_count + 1):
                    try:
                        table = range_obj.Tables(i)
                        tables.append(table)
                    except Exception as e:
                        logger.debug(f"[extract_content_with_tables] 获取表格对象失败（可忽略）: {e}")
            except Exception as e2:
                # 方法3: 尝试直接迭代
                try:
                    for table in range_obj.Tables:
                        tables.append(table)
                except Exception as e3:
                    # 所有方法都失败，回退到文本提取
                    logger.warning(f"[extract_content_with_tables] 无法获取表格列表，使用文本提取: {e1}, {e2}, {e3}")
                    try:
                        return extract_text_with_list_numbers(range_obj)
                    except Exception as fallback_e1:
                        logger.debug(f"[extract_content_with_tables] 带编号文本提取失败: {fallback_e1}")
                        try:
                            return range_obj.Text
                        except Exception as fallback_e2:
                            logger.warning(f"[extract_content_with_tables] 直接获取range_obj.Text也失败: {fallback_e2}")
                            return ""

        if not tables:
            # 没有表格，使用带自动编号的文本提取
            return extract_text_with_list_numbers(range_obj)

        # 获取范围的起始和结束位置
        start_pos = range_obj.Start
        end_pos = range_obj.End

        # 按位置排序表格
        sorted_tables = sorted(tables, key=lambda t: t.Range.Start)

        result_parts = []
        current_pos = start_pos

        # 遍历所有表格和文本内容
        for table in sorted_tables:
            table_start = table.Range.Start
            table_end = table.Range.End

            # 检查表格是否与范围有交集（表格可能部分在范围内）
            if table_end > start_pos and table_start < end_pos:
                # 提取表格前的文本（只提取在当前范围内且表格之前的部分）
                text_start = max(current_pos, start_pos)
                text_end = min(table_start, end_pos)

                if text_end > text_start:
                    text_before = range_obj.Document.Range(text_start, text_end)
                    # 使用带自动编号的文本提取函数
                    text_content = extract_text_with_list_numbers(text_before)
                    if text_content:
                        result_parts.append(text_content)

                # 提取表格（只提取在范围内的部分）
                if table_start >= start_pos and table_end <= end_pos:
                    # 表格完全在范围内
                    table_text = extract_table_as_text(table)
                    if table_text:
                        result_parts.append(table_text)
                else:
                    # 表格部分在范围内，提取表格的格式化文本
                    table_text = extract_table_as_text(table)
                    if table_text:
                        result_parts.append(table_text)

                current_pos = max(current_pos, table_end)

        # 提取最后一个表格后的文本
        text_start = max(current_pos, start_pos)
        text_end = end_pos
        if text_end > text_start:
            text_after = range_obj.Document.Range(text_start, text_end)
            # 使用带自动编号的文本提取函数
            text_content = extract_text_with_list_numbers(text_after)
            if text_content:
                result_parts.append(text_content)

        # 如果没有提取到任何内容，回退到带编号的文本提取
        if not result_parts:
            return extract_text_with_list_numbers(range_obj)

        # 直接连接各部分，保留原文档的实际格式
        # 不添加额外的换行符，让原文档的格式自然保留
        return "".join(result_parts)

    except Exception as e:
        logger.error(f"[extract_content_with_tables] 提取内容（含表格）时出错: {e}", exc_info=True)
        # 如果出错，回退到带编号的文本提取
        try:
            return extract_text_with_list_numbers(range_obj)
        except Exception as fallback_e1:
            # 如果带编号提取也失败，使用带上标/下标的文本作为最后回退
            logger.debug(f"[extract_content_with_tables] 带编号文本提取失败: {fallback_e1}")
            try:
                return extract_text_with_superscript_subscript(range_obj)
            except Exception as fallback_e2:
                # 如果连文本都无法获取，返回空字符串
                logger.warning(f"[extract_content_with_tables] 无法提取任何内容: {fallback_e2}")
                return ""


def extract_content_with_table_models(
    range_obj,
    *,
    table_id_prefix: str = "TP",
) -> tuple[str, list[StructuredTableModel]]:
    """
    提取范围中的文本与结构化表格模型。

    返回:
        (content_text, table_models)
    """
    try:
        try:
            xml_content = range_obj.WordOpenXML
        except Exception as exc:
            logger.debug(
                f"[extract_content_with_table_models] 获取WordOpenXML失败，回退纯文本提取: {exc}"
            )
            return extract_content_with_tables(range_obj), []

        if not xml_content or not isinstance(xml_content, str):
            return extract_content_with_tables(range_obj), []

        xml_content = _strip_xml_comments(xml_content)
        run_pattern, align_pattern, position_pattern, text_pattern = (
            _build_xml_run_patterns()
        )
        para_pattern = re.compile(r"<w:p\b[^\u003e]*>(.*?)</w:p>", re.DOTALL)
        table_pattern = re.compile(r"<w:tbl\b[^\u003e]*>(.*?)</w:tbl>", re.DOTALL)

        result_parts: list[str] = []
        table_models: list[StructuredTableModel] = []
        elements: list[tuple[str, int, str]] = []

        for match in para_pattern.finditer(xml_content):
            para_start = match.start()
            before_content = xml_content[:para_start]
            last_tbl_open = before_content.rfind("<w:tbl")
            last_tbl_close = before_content.rfind("</w:tbl>")
            if last_tbl_open > last_tbl_close:
                continue
            elements.append(("para", match.start(), match.group(1)))

        for match in table_pattern.finditer(xml_content):
            elements.append(("table", match.start(), match.group(1)))

        elements.sort(key=lambda value: value[1])
        table_index = 0
        for elem_type, _, content in elements:
            if elem_type == "para":
                para_texts = []
                for run_match in run_pattern.finditer(content):
                    run_content = run_match.group(1)
                    run_text = _process_run_text(
                        run_content,
                        align_pattern,
                        position_pattern,
                        text_pattern,
                    )
                    if run_text:
                        para_texts.append(run_text)
                para_text = "".join(para_texts)
                if para_text.strip():
                    result_parts.append(para_text)
                continue

            table_index += 1
            table_model = _parse_table_model_from_table_xml(
                f"<w:tbl xmlns:w=\"{WORD_XML_NS['w']}\">{content}</w:tbl>",
                table_id=f"{table_id_prefix}{table_index}",
            )
            if table_model is None:
                continue
            table_models.append(table_model)
            table_markdown = render_structured_table_markdown(table_model)
            placeholder = f"[[TABLE:{table_model['table_id']}]]"
            if table_markdown:
                result_parts.append(table_markdown)
            result_parts.append(placeholder)

        rendered = "\n".join(part for part in result_parts if part is not None)
        return rendered, table_models
    except Exception as exc:
        logger.warning(
            f"[extract_content_with_table_models] 结构化表格提取失败，回退纯文本提取: {exc}"
        )
        return extract_content_with_tables(range_obj), []


def extract_text_from_word_file(file_path: str) -> str:
    """从 Word 文件中提取所有文本内容，包括表格和自动编号"""
    file_path_obj = pathlib.Path(file_path)

    # 检查文件是否存在
    if not file_path_obj.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    # 根据文件扩展名选择不同的读取方式
    # 注意：.docx 和 .doc 都使用 win32com 读取，以便正确提取自动编号
    if file_path_obj.suffix.lower() in (".docx", ".doc"):
        # 对于 .docx 和 .doc 文件，使用 win32com（需要 Windows 环境）
        # 使用 extract_content_with_tables 来提取内容，保留表格格式和自动编号
        word = None
        doc = None
        com_initialized = False

        try:
            # 使用统一的工具函数创建 Word 应用程序
            word, com_initialized = create_word_application(
                initial_delay=2.0,  # 首次尝试前等待，确保上一个节点完全关闭
                post_init_delay=0.5,  # 给 Word 时间初始化
                use_existing=False,  # 并发环境下必须使用独立实例
                verify=False,
                node_name="word_extraction",
            )

            # 使用统一的工具函数打开文档（带重试机制）
            doc = open_document_with_retry(
                word_app=word,
                file_path=str(file_path_obj.resolve()),
                read_only=True,
                node_name="word_extraction",
            )

            # 使用 extract_content_with_tables 提取内容，保留表格格式和自动编号
            content_range = doc.Content
            document_text = extract_content_with_tables(content_range)
            return document_text

        except ImportError:
            raise ValueError(
                "读取 Word 文件需要 pywin32 库，且只能在 Windows 环境下运行"
            )
        except Exception as e:
            raise ValueError(f"读取 Word 文件失败: {e}")
        finally:
            # 使用统一的工具函数关闭 Word 应用程序
            close_word_application(
                word_app=word,
                doc=doc,
                com_initialized=com_initialized,
                wait_time=0.0,
                node_name="word_extraction",
            )
    else:
        raise ValueError(f"不支持的文件格式: {file_path_obj.suffix}")
