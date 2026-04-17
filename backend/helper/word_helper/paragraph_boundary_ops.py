"""
paragraph_boundary_ops — 共享的段落边界修复与字段尾部造段 helper。

统一 delete/update 在“受保护字段前后补真实正文段落边界”上的 Word COM 语义，
避免不同节点继续各自维护一份 InsertBefore/InsertAfter 分叉实现。
"""

from __future__ import annotations

import re
from typing import Callable, Optional, Sequence

from backend.config.tender_config import get_tender_type_family
from backend.helper.word_helper.range_utils import (
    find_safe_insert_position,
    is_range_locked,
)


def uses_wide_scan_window(tender_type: str | None) -> bool:
    return get_tender_type_family(tender_type) in {"gngk", "gjgk"}


def find_paragraph_containing_any(
    doc,
    texts: Sequence[str],
    min_start: int = 0,
    max_start: Optional[int] = None,
):
    """在指定起点之后，查找首个包含任一文本的段落。"""
    for para in doc.Paragraphs:
        try:
            rng = para.Range
            range_start = int(rng.Start)
            range_end = int(rng.End)
            if range_end < int(min_start):
                continue
            if max_start is not None and range_start > int(max_start):
                break
            para_text = str(getattr(rng, "Text", "") or "")
            if any(text in para_text for text in texts):
                return rng
        except Exception:
            continue
    return None


def find_first_visible_insert_offset(paragraph_text: str) -> int:
    """优先将换行插到编号前，否则回退到首个可见字符前。"""
    if not paragraph_text:
        return 0

    digit_match = re.search(r"\d", paragraph_text)
    if digit_match:
        return int(digit_match.start())

    for index, char in enumerate(paragraph_text):
        if not char.isspace() and char not in ("\r", "\n", "\a"):
            return int(index)
    return 0


def insert_paragraph_break_before_paragraph(
    doc,
    paragraph_range,
    fallback_pos: Optional[int],
    *,
    tender_type: str | None = None,
    field_name: str = "字段",
    log: Optional[Callable[[str], None]] = None,
) -> bool:
    """
    在字段段落前补一个真实正文段落边界。

    优先使用字段段落自身的可见起点；失败时回退到外部提供的 fallback 位置。
    """
    paragraph_candidates: list[int] = []
    if paragraph_range is not None:
        try:
            para_text_raw = str(getattr(paragraph_range, "Text", "") or "")
            primary_offset = find_first_visible_insert_offset(para_text_raw)
            paragraph_start = int(paragraph_range.Start)
            paragraph_candidates = [
                paragraph_start + primary_offset,
                paragraph_start,
            ]

            safe_insert_pos = find_safe_insert_position(
                doc,
                paragraph_candidates,
                max_forward_scan_chars=24 if uses_wide_scan_window(tender_type) else 8,
                field_name=field_name,
                log=log,
            )
            if safe_insert_pos is not None:
                doc.Range(safe_insert_pos, safe_insert_pos).InsertBefore("\r")
                return True
        except Exception:
            pass

    if fallback_pos is None:
        return False

    fallback_insert_pos = find_safe_insert_position(
        doc,
        [fallback_pos],
        max_forward_scan_chars=24 if uses_wide_scan_window(tender_type) else 8,
        field_name=field_name,
        log=log,
    )
    if fallback_insert_pos is None:
        return False

    try:
        doc.Range(fallback_insert_pos, fallback_insert_pos).InsertParagraphAfter()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# “可写独立正文段”判定
# ---------------------------------------------------------------------------

def is_writable_body_paragraph_pos(doc, pos: int) -> bool:
    """
    判断 doc 的 pos 处是否位于一个“可写独立正文段”。

    只检查 Word 真正会阻止写入的因素：Locked 属性、Fields.Locked、
    文档 ProtectionType，以及写入探针（这些都集中在 is_range_locked 里）。

    **不再基于段落的 OutlineLevel（Heading 样式）否决**。原因：
    - 在 Word 里 Heading 样式段落本身是可写的，写入会把新段插在其之前，
      并不会污染标题段。
    - 大量模板（如 xjcg 询价采购）的“二、技术要求”标题段就是普通 Heading，
      并未加锁。若用 OutlineLevel 判不可写，会触发不必要的“段内拆段”，
      在付款方式段后多出一个可见空行。
    - 真正的“写入被拒”来自 SDT / 字段锁 / 文档保护，这些 is_range_locked
      已覆盖；gngk 国内公开模板里付款方式后不可写的是因为 SDT，而不是
      因为它是 Heading。
    """
    try:
        probe = doc.Range(int(pos), int(pos))
    except Exception:
        return False
    try:
        return not is_range_locked(doc, probe)
    except Exception:
        return False


def _try_split_current_paragraph(
    doc,
    paragraph_range,
    *,
    field_name: str,
    log: Optional[Callable[[str], None]],
) -> Optional[int]:
    """
    在字段段自身的 pilcrow 之前插入 "\\r"，把它拆成两段。

    成功返回新拆出的空正文段的可写落点；失败返回 None，并尽力回滚已插入的 \\r。

    该动作的要点：
    - 不去碰下一段（标题 / SDT 等都可能是锁定的）。
    - 拆出的新段天然继承字段段的 pPr（正文样式），所以是可写的。
    - 拆段后用 is_writable_body_paragraph_pos 做后置校验；不通过则回滚。
    """
    try:
        paragraph_start = int(getattr(paragraph_range, "Start", 0))
        paragraph_end = int(paragraph_range.End)
    except Exception:
        return None

    split_pos = paragraph_end - 1
    if split_pos <= paragraph_start:
        if log:
            log(f"{field_name}段过短，无法在段内安全拆出新正文段")
        return None
    try:
        if is_range_locked(doc, doc.Range(split_pos, split_pos)):
            if log:
                log(f"{field_name}段 pilcrow 前位置受保护，放弃拆段")
            return None
    except Exception:
        return None

    try:
        doc.Range(split_pos, split_pos).InsertBefore("\r")
    except Exception as exc:
        if log:
            log(f"{field_name}段内拆段失败：{exc}")
        return None

    writable_pos = split_pos + 1
    if is_writable_body_paragraph_pos(doc, writable_pos):
        if log:
            log(
                f"{field_name}段后已通过“段内拆段”主动造出可写正文段，"
                f"位置 {writable_pos}"
            )
        return writable_pos

    # 拆段结果仍不可写 —— 回滚 \r，避免把文档弄脏。
    try:
        doc.Range(split_pos, split_pos + 1).Delete()
    except Exception:
        pass
    if log:
        log(f"{field_name}段拆出的新正文段仍不可写，已回滚")
    return None


def ensure_paragraph_break_after_paragraph(
    doc,
    paragraph_range,
    *,
    scan_bound_end: Optional[int] = None,
    tender_type: str | None = None,
    field_name: str = "字段",
    max_scan_chars: int = 4000,
    require_writable: bool = False,
    log: Optional[Callable[[str], None]] = None,
) -> tuple[bool, Optional[int]]:
    """
    保证字段段落后存在一个段落边界，返回 (inserted_new_break, boundary_or_writable_pos)。

    两种契约强度（由 require_writable 控制）：

    - require_writable=False（默认，兼容旧行为）：
        只要字段段末存在 ``\\r`` 就视为满足，不触发任何写入；段末没有 ``\\r`` 时
        走向后扫描 + InsertBefore("\\r") 补齐。适合 **只需要“有分隔”** 的 caller：
        * update 写入前的 pre-ensure 段落边界；
        * delete 后的边界修复。
        这些 caller 本身没有内容要落在"后续可写段"上，强行拆段会造出多余空行。

    - require_writable=True：
        语义升级为“必须返回一个可写独立正文段的位置”。仅供主动造段 caller 使用
        （content_ops.create_distinct_body_paragraph_after_range）。在以下情况会
        在字段段自身 pilcrow 之前 InsertBefore("\\r") 把字段段拆成两段，新空段
        继承字段段的正文 pPr：
        * 段末已有 ``\\r`` 但紧邻段是标题/锁定/SDT（例如付款方式后是章节标题）；
        * 段末 ``\\r`` 刚刚被补上，但其后紧邻段仍不可写。

    **严格禁止**软回车（wdLineBreak / ``\\v``）作为兜底 —— 软回车会让后续多段
    内容塌成一整段。任何分支都用 is_writable_body_paragraph_pos 做后置校验，
    校验不过在 require_writable=True 时直接 (False, None) fail-fast。
    """
    if paragraph_range is None:
        return False, None

    try:
        paragraph_end = int(paragraph_range.End)
        doc_end = int(doc.Content.End)
    except Exception:
        return False, None

    upper_bound = doc_end
    if scan_bound_end is not None:
        upper_bound = min(doc_end, int(scan_bound_end))
    if upper_bound <= paragraph_end:
        # 字段段末紧贴插入边界（典型：gngk 模板里付款方式后紧跟
        # after-anchor，没有任何缓冲位置可补 \r）。
        #
        # 弱契约下调用方只是想"确认有段落边界"，直接返回失败即可。
        # 强契约（require_writable=True）下调用方要写正文到新段里，
        # 必须在字段段自身 pilcrow 之前拆段 —— 这个动作不会跨过
        # upper_bound，只是把字段段内部拆成两段，新空段的可写位置
        # 仍然在 upper_bound 之前；同时插入 \r 会让 after-anchor 的
        # Start 前移一位，bound_end 自然向后扩展。
        if not require_writable:
            return False, None

        writable_pos = _try_split_current_paragraph(
            doc, paragraph_range, field_name=field_name, log=log
        )
        if writable_pos is not None:
            return True, writable_pos
        return False, None

    # ---- 情形 A / B：字段段末已有 \r ----
    try:
        next_char = doc.Range(paragraph_end, min(paragraph_end + 1, doc_end)).Text
    except Exception:
        next_char = ""

    if next_char == "\r":
        # 弱契约：段末已有 \r，任务完成，直接返回段落边界位置。
        if not require_writable:
            return False, paragraph_end

        candidate_pos = min(paragraph_end, upper_bound)
        if candidate_pos < upper_bound and is_writable_body_paragraph_pos(
            doc, candidate_pos
        ):
            return False, candidate_pos

        if log:
            log(
                f"{field_name}段末已有段落边界，但紧邻段不是可写正文段，"
                "尝试在字段段内部拆出新正文段"
            )
        writable_pos = _try_split_current_paragraph(
            doc, paragraph_range, field_name=field_name, log=log
        )
        if writable_pos is not None:
            return True, writable_pos
        return False, None

    # ---- 情形 C：字段段末没有 \r（delete 路径常见）----
    max_pos = min(upper_bound, paragraph_end + int(max_scan_chars))
    safe_insert_pos = find_safe_insert_position(
        doc,
        range(paragraph_end, max_pos + 1),
        max_forward_scan_chars=8 if uses_wide_scan_window(tender_type) else 0,
        field_name=field_name,
        log=log,
    )
    if safe_insert_pos is not None:
        try:
            doc.Range(safe_insert_pos, safe_insert_pos).InsertBefore("\r")
        except Exception:
            safe_insert_pos = None

    if safe_insert_pos is not None:
        # 弱契约：只要补上了 \r 即算成功，不验证后续段是否可写。
        if not require_writable:
            return True, int(safe_insert_pos)

        verify_pos = int(safe_insert_pos)
        if verify_pos < doc_end and is_writable_body_paragraph_pos(doc, verify_pos):
            return True, verify_pos
        if log:
            log(
                f"{field_name}段后已补段落边界，但紧邻段仍不可写，"
                "尝试段内拆段兜底"
            )

    if not require_writable:
        # 弱契约下，scan 补 \r 都失败就认为失败；不再触发拆段。
        return False, None

    writable_pos = _try_split_current_paragraph(
        doc, paragraph_range, field_name=field_name, log=log
    )
    if writable_pos is not None:
        return True, writable_pos

    return False, None


__all__ = [
    "uses_wide_scan_window",
    "find_paragraph_containing_any",
    "find_first_visible_insert_offset",
    "insert_paragraph_break_before_paragraph",
    "ensure_paragraph_break_after_paragraph",
    "is_writable_body_paragraph_pos",
]
