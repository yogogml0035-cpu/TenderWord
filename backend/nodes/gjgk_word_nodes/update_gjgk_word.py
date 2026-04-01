"""
国际公开（gjgk）专用的同页 Word 回填节点。

该节点用于手工调试和同页直插回归，不接入当前 graph。
逻辑目标：
1. 使用 gjgk 的双锚点双字号定位正文范围；
2. 直接删除前后锚点之间的原正文；
3. 将硬编码/传入文本按“文本 + Markdown 表格”的顺序回填到前置锚点后的同页正文起点；
4. 避免额外空白段落、表格顺序错乱和插入漂移到下一页。
"""

from __future__ import annotations

import pathlib
import re
import shutil
import sys
import time
from typing import Any, Callable, Dict, List, Optional

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config.tender_config import (  # noqa: E402
    get_anchor_target_sizes,
    get_default_anchor_texts,
)
from backend.states import GjgkTenderGraphState  # noqa: E402
from backend.util.log_util.progress_log import progress_log  # noqa: E402
from backend.util.word_util import (  # noqa: E402
    close_word_application,
    create_word_application,
    open_document_with_retry,
    save_document_with_retry,
    unprotect_document,
    wdCollapseEnd,
    wdCollapseStart,
    wdLineSpace1pt5,
    wdOutlineLevelBodyText,
    wdWithInTable,
)
from backend.util.word_util.anchor_utils import (  # noqa: E402
    find_anchor_range,
    resolve_anchor_content_range,
)

NODE_NAME = "update_gjgk_word"
INSERT_FONT_NAME = "宋体"
INSERT_FONT_SIZE = 12
CONTROL_CHARS = {"\r", "\n", "\v", "\f", "\a"}
DEFAULT_TEST_SOURCE_DOC = (
    BACKEND_ROOT / "test_doc" / "254DSITC2512-招标文件-发售稿-财政模板.doc"
)
DEFAULT_TEST_SUFFIX = "-gjgk-update-test"
MANUAL_TEST_INSERT_TEXT = """第1包：细胞电转仪
一、项目概述
1、设备名称及数量：
| 序号 | 设备名称 | 数量 | 是否按照医疗器械管理 |
| --- | --- | --- | --- |
| 1 | 细胞电转仪 | 壹套 | 是 |
2、交付日期：合同签订后30天内
3、交付地点：采购人指定地点
4、付款方式：货到验收合格（出具合同验收单或验收报告）且采购人收到其发票后三个月内，支付全部货款（100%）。
二、技术需求
须提供详细技术需求。
三、售后要求
1、★质保期：验收合格后整机免费质保≥3年。
2、★售后服务：提供报价设备均需提供原厂（制造商）售后，并出具相关证明文件。
3、医疗设备必须符合 IHE 医疗信息系统集成规范，并免费提供信息系统接口，医学影像设备须提供 DICOM软硬件接口，数字化医疗设备须提供HL7软硬件接口，并由供应商承担相应信息系统联机费用。
四、每套配置要求
| 序号 | 内容 | 数量 |
| --- | --- | --- |
| 1 | 主机 | 1台 |
| 2 | 腔室数 | ≥6个 |
| 3 | 温度控制 | 1个 |
| 4 | 软件 | 1套 |
| 5 | 校正 | 1套 |
注：供应商按上述配置要求自行提供响应设备的配置清单。
"""


def _visible_log(message: str) -> None:
    progress_log.info(f"[{NODE_NAME}] {message}")


def _is_table_separator_line(line: str) -> bool:
    return bool(re.match(r"^\s*\|\s*:?-{3,}.*\|\s*$", line))


def _parse_table_row(line: str) -> List[str]:
    cells = [cell.strip() for cell in line.split("|")]
    if cells and cells[0] == "":
        cells = cells[1:]
    if cells and cells[-1] == "":
        cells = cells[:-1]
    return cells


def _looks_like_table_row(line: str) -> bool:
    stripped = (line or "").strip()
    if not stripped.startswith("|"):
        return False
    return len(_parse_table_row(stripped)) >= 2


def _parse_table_block(lines: List[str], start_idx: int) -> tuple[Optional[List[List[str]]], int]:
    table_lines: List[str] = []
    idx = start_idx
    while idx < len(lines) and lines[idx].strip().startswith("|"):
        table_lines.append(lines[idx].strip())
        idx += 1

    if len(table_lines) >= 2 and _is_table_separator_line(table_lines[1]):
        header = table_lines[0]
        data_lines = table_lines[2:] if len(table_lines) > 2 else []
        all_lines = [header] + data_lines
        return [_parse_table_row(line) for line in all_lines], idx

    fallback_lines: List[str] = []
    idx = start_idx
    while idx < len(lines) and _looks_like_table_row(lines[idx]):
        fallback_lines.append(lines[idx].strip())
        idx += 1
    if len(fallback_lines) >= 2:
        return [_parse_table_row(line) for line in fallback_lines], idx

    return None, start_idx


def _build_insert_items(polished_text: str) -> List[Dict[str, Any]]:
    normalized_text = polished_text.replace("\r\n", "\n").replace("\r", "\n")
    raw_lines = [line.rstrip() for line in normalized_text.split("\n")]

    items: List[Dict[str, Any]] = []
    idx = 0
    while idx < len(raw_lines):
        if not raw_lines[idx].strip():
            idx += 1
            continue

        maybe_table, next_idx = _parse_table_block(raw_lines, idx)
        if maybe_table:
            items.append({"type": "table", "rows": maybe_table})
            idx = next_idx
            continue

        items.append({"type": "text", "line": raw_lines[idx].strip()})
        idx += 1

    return items


def _apply_standard_insert_format(
    inserted_rng,
    *,
    font_name: str = INSERT_FONT_NAME,
    font_size: int = INSERT_FONT_SIZE,
) -> None:
    inserted_rng.Font.Name = font_name
    inserted_rng.Font.Size = font_size
    inserted_rng.Font.Bold = False

    paragraph_format = inserted_rng.ParagraphFormat
    paragraph_format.LineSpacingRule = wdLineSpace1pt5
    paragraph_format.LeftIndent = 0
    paragraph_format.FirstLineIndent = 0
    paragraph_format.OutlineLevel = wdOutlineLevelBodyText

    for attr, value in (
        ("SpaceBeforeAuto", False),
        ("SpaceAfterAuto", False),
        ("SpaceBefore", 0),
        ("SpaceAfter", 0),
    ):
        try:
            setattr(paragraph_format, attr, value)
        except Exception:
            continue


def _resolve_gjgk_content_range(doc, word_app, before_hit, after_hit) -> Dict[str, int]:
    return resolve_anchor_content_range(
        doc=doc,
        word_app=word_app,
        before_hit=before_hit,
        after_hit=after_hit,
        tender_type="gjgk",
        allow_empty=True,
    )


def _set_collapsed_range(insert_range, position: int) -> None:
    insert_range.SetRange(int(position), int(position))
    insert_range.Collapse(wdCollapseStart)


def _ensure_insert_range(
    insert_range,
    *,
    bound_start: int,
    get_bound_end: Callable[[], int],
) -> None:
    try:
        insert_range.Collapse(wdCollapseStart)
    except Exception:
        pass

    try:
        pos = int(insert_range.Start)
    except Exception:
        pos = int(bound_start)

    current_end = int(get_bound_end())
    if pos < bound_start:
        pos = bound_start
    if pos > current_end:
        pos = current_end
    _set_collapsed_range(insert_range, pos)

    try:
        if insert_range.Information(wdWithInTable):
            parent_tables = insert_range.Tables
            if parent_tables.Count > 0:
                host_table = parent_tables(1)
                next_pos = int(host_table.Range.End)
                latest_end = int(get_bound_end())
                if next_pos > latest_end:
                    next_pos = latest_end
                if next_pos < bound_start:
                    next_pos = bound_start
                _set_collapsed_range(insert_range, next_pos)
    except Exception:
        pass


def _trim_leading_layout_controls(
    doc,
    *,
    range_start: int,
    get_bound_end: Callable[[], int],
    log_parts: List[str],
    max_scan: int = 16,
) -> int:
    cursor = max(0, int(range_start))
    removed = 0

    for _ in range(max_scan):
        current_end = int(get_bound_end())
        if cursor >= current_end or cursor >= int(doc.Content.End):
            break
        probe = doc.Range(cursor, min(cursor + 1, int(doc.Content.End)))
        probe_text = str(getattr(probe, "Text", "") or "")
        if probe_text not in CONTROL_CHARS:
            break
        probe.Delete()
        removed += 1

    if removed > 0:
        log_parts.append(f"局部清理起点控制符 {removed} 个")

    return cursor


def _insert_text_line(
    doc,
    insert_range,
    line: str,
    *,
    bound_start: int,
    get_bound_end: Callable[[], int],
):
    _ensure_insert_range(
        insert_range,
        bound_start=bound_start,
        get_bound_end=get_bound_end,
    )
    start_pos = int(insert_range.End)
    insert_range.InsertAfter(line + "\r")
    end_pos = int(insert_range.End)
    inserted_rng = doc.Range(start_pos, max(start_pos, end_pos - 1))
    _apply_standard_insert_format(inserted_rng)
    insert_range.Collapse(wdCollapseEnd)
    _ensure_insert_range(
        insert_range,
        bound_start=bound_start,
        get_bound_end=get_bound_end,
    )
    return inserted_rng


def _insert_table(
    doc,
    insert_range,
    rows: List[List[str]],
    *,
    bound_start: int,
    get_bound_end: Callable[[], int],
):
    if not rows:
        return None

    _ensure_insert_range(
        insert_range,
        bound_start=bound_start,
        get_bound_end=get_bound_end,
    )
    cols = max(len(row) for row in rows)
    start_pos = int(insert_range.End)
    table_range = doc.Range(start_pos, start_pos)
    table = doc.Tables.Add(table_range, len(rows), cols)

    try:
        table.Borders.Enable = True
    except Exception:
        pass

    for row_idx, row in enumerate(rows):
        for col_idx in range(cols):
            cell_value = row[col_idx] if col_idx < len(row) else ""
            try:
                cell = table.Cell(row_idx + 1, col_idx + 1)
                cell_range = cell.Range
                if cell_range.End > cell_range.Start + 1:
                    doc.Range(cell_range.Start, cell_range.End - 1).Delete()

                cell_range = cell.Range
                cell_text = re.sub(r"(?i)<br\s*/?>", "\r", str(cell_value or ""))
                cell_range.InsertBefore(cell_text)

                cell_range = cell.Range
                _apply_standard_insert_format(cell_range)
                cell_range.ParagraphFormat.Alignment = 0
                cell.VerticalAlignment = 1
            except Exception:
                continue

    latest_end = int(get_bound_end())
    next_pos = int(table.Range.End)
    if next_pos > latest_end:
        next_pos = latest_end
    if next_pos < bound_start:
        next_pos = bound_start
    _set_collapsed_range(insert_range, next_pos)
    _ensure_insert_range(
        insert_range,
        bound_start=bound_start,
        get_bound_end=get_bound_end,
    )
    return table


def _cleanup_blank_paragraphs(
    doc,
    *,
    range_start: int,
    range_end: int,
    log_parts: List[str],
) -> None:
    if int(range_end) <= int(range_start):
        return

    try:
        paragraphs = list(doc.Range(int(range_start), int(range_end)).Paragraphs)
    except Exception:
        return

    deleted = 0
    for para in reversed(paragraphs):
        try:
            if para.Range.Information(wdWithInTable):
                continue
            para_text = (
                str(getattr(para.Range, "Text", "") or "")
                .replace("\r", "")
                .replace("\n", "")
                .replace("\a", "")
                .strip()
            )
            if para_text:
                continue
            para.Range.Delete()
            deleted += 1
        except Exception:
            continue

    if deleted > 0:
        log_parts.append(f"清理空白段落 {deleted} 个")


def _build_manual_test_output_path(source_doc_path: pathlib.Path) -> pathlib.Path:
    return source_doc_path.with_name(
        f"{source_doc_path.stem}{DEFAULT_TEST_SUFFIX}{source_doc_path.suffix}"
    )


def _build_manual_test_state(prepared_doc_path: str) -> GjgkTenderGraphState:
    before_text, after_text = get_default_anchor_texts("gjgk")
    return GjgkTenderGraphState(
        tender_type="gjgk",
        prepared_doc_path=str(prepared_doc_path),
        polished_text=MANUAL_TEST_INSERT_TEXT,
        insertion_before_text=before_text,
        insertion_after_text=after_text,
    )


def update_gjgk_word(state: GjgkTenderGraphState, config) -> GjgkTenderGraphState:
    start_time = time.perf_counter()

    prepared_doc_path = state.get("prepared_doc_path")
    polished_text = state.get("polished_text")
    insertion_before_text = state.get("insertion_before_text")
    insertion_after_text = state.get("insertion_after_text")

    if not prepared_doc_path:
        raise ValueError("需要 prepared_doc_path 来插入 gjgk 内容")
    if not polished_text:
        raise ValueError("需要 polished_text 来插入 gjgk 内容")
    if not insertion_before_text or not insertion_after_text:
        raise ValueError("gjgk 插入必须提供 insertion_before_text 和 insertion_after_text")

    before_size, after_size = get_anchor_target_sizes("gjgk")
    items = _build_insert_items(polished_text)
    if not items:
        raise ValueError("gjgk 插入内容为空，无法执行更新")

    log_parts = [f"共解析插入项 {len(items)} 条"]
    word = None
    doc = None
    com_initialized = False

    try:
        _visible_log("开始执行 gjgk 同页回填")
        word, com_initialized = create_word_application(
            initial_delay=0.0,
            post_init_delay=1.0,
            use_existing=False,
            verify=False,
            node_name=NODE_NAME,
        )
        doc = open_document_with_retry(
            word_app=word,
            file_path=prepared_doc_path,
            read_only=False,
            node_name=NODE_NAME,
        )
        log_parts.append(f"已打开文档: {prepared_doc_path}")

        if unprotect_document(doc, node_name=NODE_NAME):
            log_parts.append("已取消文档保护")

        before_hit, after_hit = find_anchor_range(
            doc,
            insertion_before_text,
            insertion_after_text,
            before_size=before_size,
            after_size=after_size,
            prefer_before="last",
            prefer_after="first",
        )
        if not before_hit:
            raise ValueError(f"未找到前置锚点段落: {insertion_before_text}")
        if not after_hit:
            raise ValueError(f"未找到后置锚点段落: {insertion_after_text}")

        content_range = _resolve_gjgk_content_range(
            doc=doc,
            word_app=word,
            before_hit=before_hit,
            after_hit=after_hit,
        )
        range_start = int(content_range["range_start"])
        range_end = int(content_range["range_end"])
        start_page = int(content_range["start_page"])
        end_page = int(content_range["end_page"])

        log_parts.append(
            f"锚点范围 {range_start}-{range_end}，页码 {start_page}-{end_page}"
        )

        after_anchor_marker = doc.Range(int(after_hit["start"]), int(after_hit["start"]))

        def get_insertion_bound_end() -> int:
            try:
                return int(after_anchor_marker.Start)
            except Exception:
                return int(range_end)

        if range_end > range_start:
            doc.Range(range_start, range_end).Delete()
            log_parts.append(f"已删除原正文区间 {range_start}-{range_end}")
        else:
            log_parts.append("锚点区间为空，直接执行同页插入")

        insert_start = _trim_leading_layout_controls(
            doc,
            range_start=range_start,
            get_bound_end=get_insertion_bound_end,
            log_parts=log_parts,
        )
        insert_range = doc.Range(insert_start, insert_start)
        _set_collapsed_range(insert_range, insert_start)

        inserted_count = 0
        for item in items:
            if item["type"] == "text":
                _insert_text_line(
                    doc,
                    insert_range,
                    item["line"],
                    bound_start=insert_start,
                    get_bound_end=get_insertion_bound_end,
                )
                inserted_count += 1
                log_parts.append(
                    f"[{inserted_count}/{len(items)}] 已插入文本: {item['line'][:40]}"
                )
                continue

            _insert_table(
                doc,
                insert_range,
                item["rows"],
                bound_start=insert_start,
                get_bound_end=get_insertion_bound_end,
            )
            inserted_count += 1
            log_parts.append(
                f"[{inserted_count}/{len(items)}] 已插入表格，行数 {len(item['rows'])}"
            )

        inserted_end = int(insert_range.Start)
        _cleanup_blank_paragraphs(
            doc,
            range_start=insert_start,
            range_end=inserted_end,
            log_parts=log_parts,
        )

        save_document_with_retry(doc, node_name=NODE_NAME)
        log_parts.append("文档已保存")
        _visible_log("gjgk 同页回填完成")
    except Exception as exc:
        error_message = f"gjgk Word 更新失败: {exc}"
        log_parts.append(error_message)
        _visible_log(error_message)
        raise RuntimeError(error_message) from exc
    finally:
        close_word_application(
            word_app=word,
            doc=doc,
            com_initialized=com_initialized,
            wait_time=1.0,
            node_name=NODE_NAME,
        )

    duration_ms = (time.perf_counter() - start_time) * 1000
    log_parts.append(f"节点执行耗时 {duration_ms:.0f} 毫秒")

    new_state = dict(state)
    new_state["insertion_log"] = "; ".join(log_parts)
    return GjgkTenderGraphState(**new_state)


def main() -> None:
    print("=" * 80)
    print("开始测试 update_gjgk_word 节点")
    print("=" * 80)

    source_doc_path = DEFAULT_TEST_SOURCE_DOC
    if not source_doc_path.exists():
        print(f"错误: 测试文件不存在: {source_doc_path}")
        sys.exit(1)

    test_doc_path = _build_manual_test_output_path(source_doc_path)
    shutil.copy2(source_doc_path, test_doc_path)
    test_state = _build_manual_test_state(str(test_doc_path))

    print(f"源文件: {source_doc_path}")
    print(f"测试副本: {test_doc_path}")
    print("插入模式: 先删除锚点区间原内容，再执行同页顺序回填")
    print("测试状态:")
    for key, value in test_state.items():
        if key == "polished_text":
            print(f"  {key}: {value[:80]}...")
        else:
            print(f"  {key}: {value}")
    print("-" * 80)

    try:
        result_state = update_gjgk_word(test_state, config=None)
        print("✅ update_gjgk_word 执行完成")
        print(f"结果文件: {test_doc_path}")
        print("插入日志:")
        for part in str(result_state.get("insertion_log", "")).split("; "):
            print(f"  - {part}")
    except Exception as exc:
        print("❌ update_gjgk_word 执行失败")
        print(f"错误信息: {exc}")
        raise

    print("=" * 80)
    print("测试完成")
    print("=" * 80)


if __name__ == "__main__":
    main()
