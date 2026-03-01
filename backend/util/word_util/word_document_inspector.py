"""
Word 文档内容检测工具

提供文档内容检测功能，包括：
- 批注检测（内容和位置）
- 删除线段落检测
- 非黑色字体文字检测
- 文档保护状态检测
"""

from dataclasses import dataclass, field
from typing import Optional
from backend.util.log_util.progress_util import progress_logger



@dataclass
class CommentInfo:
    """批注信息"""

    author: str
    date: str
    content: str
    scope_text: str
    reference_text: str
    range_text: str
    page_number: int = 0


@dataclass
class StrikethroughInfo:
    """删除线段落信息"""

    paragraph_text: str
    strikethrough_text: str
    range_text: str
    page_number: int = 0


@dataclass
class NonBlackFontInfo:
    """非黑色字体文字信息"""

    paragraph_text: str
    font_text: str
    color: int
    color_name: str
    range_text: str
    font_name: str = ""
    font_size: float = 0.0
    page_number: int = 0


@dataclass
class DocumentAnalysisResult:
    """文档分析结果"""

    is_protected: bool = False
    protection_type: int = -1
    comments: list = field(default_factory=list)
    strikethroughs: list = field(default_factory=list)
    non_black_fonts: list = field(default_factory=list)
    total_comments: int = 0
    total_strikethroughs: int = 0
    total_non_black_fonts: int = 0


class WordDocumentInspector:
    """Word 文档内容检测器"""

    BLACK_COLOR = 0
    AUTOMATIC_COLOR = 0
    WINDOWS_AUTO_COLOR = -16777216

    def __init__(self, word_app: any, doc: any, node_name: str = ""):
        self.word_app = word_app
        self.doc = doc
        self.node_name = node_name
        self._paragraph_index_built = False
        self._paragraph_ranges: list[tuple[int, int, int]] = []

    def _get_log_prefix(self) -> str:
        return f"[{self.node_name}] " if self.node_name else ""

    def _get_page_number(self, range_obj: any) -> int:
        """获取_range所在的页码"""
        try:
            if hasattr(range_obj, "Information"):
                return range_obj.Information(2)
        except Exception:
            pass
        return 0

    def _build_scope_with_neighbor_paragraphs(self, scope_obj: any) -> str:
        """
        根据批注 Scope 所在段落，构造包含前后各两个段落的 scope_text。

        规则：
        - 找到 Scope.Start 所在的段落索引 i
        - 取段落 [i-2, i+2]（边界裁剪为 [1, Count]）
        - 按顺序拼接这些段落的文本，作为 scope_text
        - 若任一步失败，则回退为原始 scope_obj.Text
        """
        try:
            if scope_obj is None or not hasattr(self, "doc") or self.doc is None:
                return (scope_obj.Text or "") if scope_obj is not None else ""

            paragraphs = getattr(self.doc, "Paragraphs", None)
            if paragraphs is None or not hasattr(paragraphs, "Count"):
                return scope_obj.Text or ""

            try:
                scope_start = int(getattr(scope_obj, "Start", 0))
            except Exception:
                return scope_obj.Text or ""

            self._ensure_paragraph_index()
            if not self._paragraph_ranges:
                return scope_obj.Text or ""

            target_idx = self._find_paragraph_index_for_position(scope_start)
            if target_idx is None:
                return scope_obj.Text or ""

            try:
                total = int(getattr(paragraphs, "Count", 0) or 0)
            except Exception:
                total = 0
            if total <= 0:
                return scope_obj.Text or ""

            parts: list[str] = []
            try:
                para = paragraphs.Item(target_idx)
                pr = getattr(para, "Range", None)
                if pr is not None:
                    text = getattr(pr, "Text", "") or ""
                    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
                    if text:
                        parts.append(text)
            except Exception:
                return scope_obj.Text or ""

            if not parts:
                return scope_obj.Text or ""

            return "\n".join(parts)
        except Exception:
            return scope_obj.Text or ""

    def _ensure_paragraph_index(self) -> None:
        if self._paragraph_index_built:
            return
        self._paragraph_ranges = []
        paragraphs = getattr(self.doc, "Paragraphs", None)
        if paragraphs is None or not hasattr(paragraphs, "Count"):
            self._paragraph_index_built = True
            return
        try:
            total = int(paragraphs.Count or 0)
        except Exception:
            total = 0
        if total <= 0:
            self._paragraph_index_built = True
            return
        for i in range(1, total + 1):
            try:
                para = paragraphs.Item(i)
                pr = getattr(para, "Range", None)
                if pr is None:
                    continue
                start = int(getattr(pr, "Start", 0))
                end = int(getattr(pr, "End", 0))
                self._paragraph_ranges.append((start, end, i))
            except Exception:
                continue
        self._paragraph_index_built = True

    def _find_paragraph_index_for_position(self, pos: int) -> Optional[int]:
        if not self._paragraph_ranges:
            return None
        lo = 0
        hi = len(self._paragraph_ranges) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            start, end, idx = self._paragraph_ranges[mid]
            if start <= pos < end:
                return idx
            if pos < start:
                hi = mid - 1
            else:
                lo = mid + 1
        return None

    def _build_paragraph_context_by_index(
        self, paragraphs: any, idx: int, total: int
    ) -> str:
        """
        给定段落集合与当前段落索引 idx（1-based），返回该段落前后各两个段落的组合文本。
        失败时返回空串，由调用方决定回退策略。
        """
        try:
            if paragraphs is None or total <= 0 or idx <= 0:
                return ""
            start_idx = max(1, idx - 2)
            end_idx = min(total, idx + 2)
            parts: list[str] = []
            for j in range(start_idx, end_idx + 1):
                try:
                    para = paragraphs.Item(j)
                    pr = getattr(para, "Range", None)
                    if pr is None:
                        continue
                    text = getattr(pr, "Text", "") or ""
                    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
                    if text:
                        parts.append(text)
                except Exception:
                    continue
            return "\n".join(parts)
        except Exception:
            return ""

    def _get_comment_full_content(self, range_obj: any) -> str:
        """
        获取批注气泡的完整文本（含多段落）。
        Word COM 中 comment.Range.Text 在多段落时可能只返回最后一段，故按段落拼接。
        """
        try:
            if not hasattr(range_obj, "Paragraphs"):
                return (range_obj.Text or "").replace("\r\n", "\n").replace("\r", "\n")
            parts = []
            paras = range_obj.Paragraphs
            for j in range(1, paras.Count + 1):
                try:
                    para = paras.Item(j)
                    parts.append(para.Range.Text or "")
                except Exception:
                    continue
            text = "".join(parts)
            return text.replace("\r\n", "\n").replace("\r", "\n")
        except Exception:
            return (range_obj.Text or "").replace("\r\n", "\n").replace("\r", "\n")

    def check_protection(self) -> tuple[bool, int]:
        """
        检查文档保护状态

        返回:
            tuple[is_protected, protection_type]
            - is_protected: 是否受保护
            - protection_type: 保护类型 (-1 表示无保护)
        """
        log_prefix = self._get_log_prefix()
        try:
            protection_type = self.doc.ProtectionType
            progress_logger.debug(f"{log_prefix}文档保护类型: {protection_type} (-1 表示无保护)")

            if protection_type == -1:
                return False, protection_type
            return True, protection_type
        except Exception as e:
            progress_logger.debug(f"{log_prefix}检查文档保护时出错: {e}")
            return False, -1

    def get_color_name(self, color_value: int) -> str:
        """获取颜色名称"""
        color_names = {
            0: "黑色/自动",
            1: "白色",
            2: "红色",
            3: "鲜绿",
            4: "蓝色",
            5: "青色",
            6: "品红",
            7: "黄色",
            8: "深红",
            9: "绿色",
            10: "深蓝",
            11: "深青",
            12: "深品红",
            13: "橄榄色",
            14: "紫色",
            15: "银色",
            16: "深蓝(强调文字)",
            17: "青色(强调文字)",
            18: "深绿(强调文字)",
            19: "蓝色灰(强调文字)",
            20: "深黄(强调文字)",
            21: "蓝色(强调文字)",
            22: "深青(强调文字)",
            23: "深紫(强调文字)",
            24: "深蓝(辅助颜色)",
        }

        if color_value in color_names:
            return color_names[color_value]

        return self._get_rgb_color_name(color_value)

    def _get_rgb_color_name(self, color_value: int) -> str:
        """根据RGB值获取颜色名称"""
        red = color_value & 0xFF
        green = (color_value >> 8) & 0xFF
        blue = (color_value >> 16) & 0xFF

        if red > 200 and green < 100 and blue < 100:
            return "红色"
        elif red < 100 and green > 200 and blue < 100:
            return "绿色"
        elif red < 100 and green < 100 and blue > 200:
            return "蓝色"
        elif red > 200 and green > 200 and blue < 100:
            return "黄色"
        elif red < 100 and green > 200 and blue > 200:
            return "青色"
        elif red > 200 and green < 100 and blue > 200:
            return "品红"
        elif red > 200 and green < 100 and blue < 100:
            return "深红"
        elif red < 100 and green > 200 and blue < 100:
            return "深绿"
        elif red < 100 and green < 100 and blue > 200:
            return "深蓝"
        elif red > 150 and green > 150 and blue > 150:
            return "银色/灰色"
        elif red > 200 and green > 100 and blue < 100:
            return "橙色"
        elif red > 200 and green > 200 and blue < 50:
            return "浅黄"
        elif red > 200 and green < 50 and blue > 200:
            return "紫色"
        elif red < 50 and green > 200 and blue > 200:
            return "浅青"
        elif red > 100 and green < 100 and blue > 200:
            return "紫红色"
        elif red > 100 and green > 100 and blue < 100:
            return "橄榄色"
        elif red < 100 and green > 100 and blue > 100:
            return "深青色"
        elif red > 100 and green < 100 and blue < 100:
            return "深红色"
        elif red < 100 and green > 100 and blue < 100:
            return "深绿色"
        elif red < 100 and green < 100 and blue > 100:
            return "深蓝色"
        else:
            return f"RGB({red},{green},{blue})"

    def inspect_comments(
        self,
        range_start: Optional[int] = None,
        range_end: Optional[int] = None,
    ) -> list[CommentInfo]:
        """
        检测文档中的批注；若提供 range_start/range_end，仅保留批注 Scope 与该范围有交集的批注。

        Args:
            range_start: 锚点范围起始位置（字符偏移，含）
            range_end: 锚点范围结束位置（字符偏移，不含）

        返回:
            list[CommentInfo]: 批注信息列表
        """
        log_prefix = self._get_log_prefix()
        comments = []
        use_range = (
            range_start is not None
            and range_end is not None
            and range_start < range_end
        )
        if use_range:
            progress_logger.debug(f"{log_prefix}仅抽取批注范围: [{range_start}, {range_end})")

        try:
            comments_collection = self.doc.Comments
            comment_count = comments_collection.Count
            progress_logger.debug(f"{log_prefix}检测到 {comment_count} 个批注")

            for i in range(1, comment_count + 1):
                try:
                    comment = comments_collection.Item(i)
                    range_obj = comment.Range

                    scope_obj = comment.Scope
                    # 批注范围：扩展为 Scope 所在段落前后各两个段落的文本
                    scope_text = ""
                    reference_text = ""
                    if scope_obj is not None:
                        try:
                            reference_text = (scope_obj.Text or "").strip()
                        except Exception:
                            reference_text = ""
                        scope_text = self._build_scope_with_neighbor_paragraphs(
                            scope_obj
                        )

                    if use_range and scope_obj is not None:
                        try:
                            scope_start = int(scope_obj.Start)
                            scope_end = int(scope_obj.End)
                            # 仅保留 Scope 与 [range_start, range_end) 有交集的批注
                            if scope_end <= range_start or scope_start >= range_end:
                                continue
                        except Exception:
                            pass

                    # 用按段落拼接的方式取批注气泡全文，避免多段落批注只得到最后一段
                    comment_content = self._get_comment_full_content(range_obj)

                    comment_info = CommentInfo(
                        author=comment.Author or "",
                        date=str(comment.Date) if comment.Date else "",
                        content=comment_content,
                        scope_text=scope_text or "",
                        reference_text=reference_text or "",
                        range_text=comment_content,
                        page_number=self._get_page_number(range_obj),
                    )
                    comments.append(comment_info)

                    # 分块分行打印，避免批注内容/范围中的换行导致与下一项混在一起
                    progress_logger.debug(f"{log_prefix}---------- 批注 {i} ----------")
                    progress_logger.debug(f"{log_prefix}  作者: {comment_info.author}")
                    progress_logger.debug(f"{log_prefix}  日期: {comment_info.date}")
                    progress_logger.debug(f"{log_prefix}  批注内容:\n{comment_info.content}")
                    progress_logger.debug(f"{log_prefix}  批注范围:\n{comment_info.scope_text}")

                except Exception as e:
                    progress_logger.debug(f"{log_prefix}读取批注 {i} 时出错: {e}")
                    continue

        except Exception as e:
            progress_logger.debug(f"{log_prefix}获取批注集合时出错: {e}")

        return comments

    def _check_paragraph_strikethrough(
        self, range_obj, paragraph_text: str, log_prefix: str
    ) -> Optional[StrikethroughInfo]:
        """对单个段落的 Range 检测删除线，有则返回 StrikethroughInfo，否则返回 None。"""
        try:
            if not (
                hasattr(range_obj.Font, "StrikeThrough")
                and range_obj.Font.StrikeThrough
            ):
                return None
            strikethrough_segments = []
            current_segment = []
            for j in range(1, range_obj.Characters.Count + 1):
                try:
                    char = range_obj.Characters.Item(j)
                    if hasattr(char.Font, "StrikeThrough") and char.Font.StrikeThrough:
                        current_segment.append(char.Text)
                    else:
                        if current_segment:
                            segment_text = "".join(current_segment).strip()
                            if segment_text:
                                strikethrough_segments.append(segment_text)
                            current_segment = []
                except Exception:
                    continue
            if current_segment:
                segment_text = "".join(current_segment).strip()
                if segment_text:
                    strikethrough_segments.append(segment_text)
            strikethrough_text = "、".join(strikethrough_segments)
            if not paragraph_text.strip() or not strikethrough_text:
                return None
            return StrikethroughInfo(
                paragraph_text=paragraph_text.strip(),
                strikethrough_text=strikethrough_text,
                range_text=paragraph_text,
                page_number=self._get_page_number(range_obj),
            )
        except Exception:
            return None

    def _check_paragraph_non_black_font(
        self, range_obj, paragraph_text: str, log_prefix: str
    ) -> Optional[NonBlackFontInfo]:
        """对单个段落的 Range 检测非黑色字体，有则返回 NonBlackFontInfo，否则返回 None。"""
        try:
            if "申报人名称" in paragraph_text and "填写单位全称" in paragraph_text:
                return None
            if not hasattr(range_obj.Font, "Color"):
                return None
            color_value = range_obj.Font.Color
            if (
                color_value == self.BLACK_COLOR
                or color_value == self.AUTOMATIC_COLOR
                or color_value == self.WINDOWS_AUTO_COLOR
            ):
                return None
            font_segments = []
            current_segment = []
            font_name = ""
            font_size = 0.0
            for j in range(1, range_obj.Characters.Count + 1):
                try:
                    char = range_obj.Characters.Item(j)
                    if hasattr(char.Font, "Color"):
                        char_color = char.Font.Color
                        if (
                            char_color != self.BLACK_COLOR
                            and char_color != self.AUTOMATIC_COLOR
                            and char_color != self.WINDOWS_AUTO_COLOR
                        ):
                            current_segment.append(char.Text)
                            if not font_name and hasattr(char.Font, "Name"):
                                font_name = char.Font.Name or ""
                            if font_size == 0.0 and hasattr(char.Font, "Size"):
                                font_size = char.Font.Size or 0.0
                        else:
                            if current_segment:
                                segment_text = "".join(current_segment).strip()
                                if segment_text:
                                    font_segments.append(segment_text)
                                current_segment = []
                except Exception:
                    continue
            if current_segment:
                segment_text = "".join(current_segment).strip()
                if segment_text:
                    font_segments.append(segment_text)
            font_text = "、".join(font_segments)
            if not paragraph_text.strip() or not font_text:
                return None
            return NonBlackFontInfo(
                paragraph_text=paragraph_text.strip(),
                font_text=font_text,
                color=color_value,
                color_name=self.get_color_name(color_value),
                range_text=paragraph_text,
                font_name=font_name,
                font_size=font_size,
                page_number=self._get_page_number(range_obj),
            )
        except Exception:
            return None

    def _inspect_paragraphs_strikethrough_and_non_black(
        self,
        range_start: Optional[int] = None,
        range_end: Optional[int] = None,
    ) -> tuple[list[StrikethroughInfo], list[NonBlackFontInfo]]:
        """
        一次遍历所有段落，在锚点范围内（若指定）对每个段落同时检测删除线、非黑字。
        有范围时：只遍历锚点内的段落，超出范围即 break，不再扫全文。
        """
        log_prefix = self._get_log_prefix()
        strikethroughs: list[StrikethroughInfo] = []
        non_black_fonts: list[NonBlackFontInfo] = []
        use_range = (
            range_start is not None
            and range_end is not None
            and range_start < range_end
        )

        try:
            paragraphs = self.doc.Paragraphs
            total_paragraphs = paragraphs.Count
            if use_range:
                progress_logger.debug(
                    f"{log_prefix}一次遍历段落：仅锚点范围内检测删除线+非黑字（全文共 {total_paragraphs} 段，遇范围外即结束）"
                )
            else:
                progress_logger.debug(
                    f"{log_prefix}一次遍历 {total_paragraphs} 个段落，检测删除线+非黑字"
                )

            for i in range(1, total_paragraphs + 1):
                try:
                    paragraph = paragraphs.Item(i)
                    range_obj = paragraph.Range
                    if use_range:
                        para_start = int(range_obj.Start)
                        para_end = int(range_obj.End)
                        if para_end <= range_start:
                            continue
                        if para_start >= range_end:
                            break
                    paragraph_text = range_obj.Text or ""

                    strike = self._check_paragraph_strikethrough(
                        range_obj, paragraph_text, log_prefix
                    )
                    if strike:
                        strikethroughs.append(strike)
                        progress_logger.debug(
                            f"{log_prefix}删除线段落 {len(strikethroughs)}: '{paragraph_text}...', 删除线: '{strike.strikethrough_text}'"
                        )

                    font_info = self._check_paragraph_non_black_font(
                        range_obj, paragraph_text, log_prefix
                    )
                    if font_info:
                        non_black_fonts.append(font_info)
                        progress_logger.debug(
                            f"{log_prefix}非黑色字体段落 {len(non_black_fonts)}: 颜色='{font_info.color_name}', 文字='{font_info.font_text}'"
                        )
                except Exception as e:
                    progress_logger.debug(f"{log_prefix}检测段落 {i} 时出错: {e}")
                    continue

        except Exception as e:
            progress_logger.debug(f"{log_prefix}获取段落集合时出错: {e}")

        return strikethroughs, non_black_fonts

    def inspect_strikethroughs(
        self,
        range_start: Optional[int] = None,
        range_end: Optional[int] = None,
    ) -> list[StrikethroughInfo]:
        """
        检测文档中带有删除线的段落；若提供 range_start/range_end，仅保留段落与该范围有交集的。
        内部复用一次段落遍历（与非黑字合并），对外保持接口一致。
        """
        strikethroughs, _ = self._inspect_paragraphs_strikethrough_and_non_black(
            range_start=range_start, range_end=range_end
        )
        return strikethroughs

    def inspect_non_black_fonts(
        self,
        range_start: Optional[int] = None,
        range_end: Optional[int] = None,
    ) -> list[NonBlackFontInfo]:
        """
        检测文档中字体颜色不是黑色的文字；若提供 range_start/range_end，仅保留段落与该范围有交集的。
        内部复用一次段落遍历（与删除线合并），对外保持接口一致。
        """
        _, non_black_fonts = self._inspect_paragraphs_strikethrough_and_non_black(
            range_start=range_start, range_end=range_end
        )
        return non_black_fonts

    def inspect_non_black_fonts_by_sentence(self) -> list[NonBlackFontInfo]:
        """
        按句子/句子单元检测非黑色字体文字（更细粒度）

        返回:
            list[NonBlackFontInfo]: 非黑色字体文字信息列表
        """
        log_prefix = self._get_log_prefix()
        non_black_fonts = []

        try:
            story_ranges = [
                (self.doc.Content, "正文内容"),
                (self.doc.StoryRanges(2), "脚注"),
                (self.doc.StoryRanges(3), "尾注"),
                (self.doc.StoryRanges(4), "批注"),
            ]

            for range_obj, story_name in story_ranges:
                try:
                    sentences = range_obj.Sentences
                    for j in range(1, sentences.Count + 1):
                        try:
                            sentence = sentences.Item(j)

                            if hasattr(sentence.Font, "Color"):
                                color_value = sentence.Font.Color

                                if (
                                    color_value != self.BLACK_COLOR
                                    and color_value != self.AUTOMATIC_COLOR
                                ):
                                    text = sentence.Text or ""
                                    if text.strip():
                                        font_info = NonBlackFontInfo(
                                            text=text.strip(),
                                            color=color_value,
                                            color_name=self.get_color_name(color_value),
                                            range_text=text,
                                            font_name=sentence.Font.Name or "",
                                            font_size=sentence.Font.Size
                                            if hasattr(sentence.Font, "Size")
                                            else 0.0,
                                            page_number=self._get_page_number(sentence),
                                        )
                                        non_black_fonts.append(font_info)

                        except Exception as e:
                            progress_logger.debug(f"{log_prefix}检测 {story_name} 句子 {j} 时出错: {e}")
                            continue

                except Exception as e:
                    progress_logger.debug(f"{log_prefix}获取 {story_name} 句子集合时出错: {e}")

        except Exception as e:
            progress_logger.debug(f"{log_prefix}检测非黑色字体时出错: {e}")

        return non_black_fonts

    def analyze_document(
        self,
        range_start: Optional[int] = None,
        range_end: Optional[int] = None,
    ) -> DocumentAnalysisResult:
        """
        综合分析文档；若提供 range_start/range_end，批注/删除线/非黑字均只统计该范围内。

        Args:
            range_start: 锚点范围起始位置（字符偏移，含）
            range_end: 锚点范围结束位置（字符偏移，不含）

        返回:
            DocumentAnalysisResult: 文档分析结果
        """
        log_prefix = self._get_log_prefix()
        progress_logger.debug(f"{log_prefix}开始综合分析文档...")

        result = DocumentAnalysisResult()

        is_protected, protection_type = self.check_protection()
        result.is_protected = is_protected
        result.protection_type = protection_type

        progress_logger.debug(f"{log_prefix}文档保护状态: {'受保护' if is_protected else '无保护'}")

        # 批注：单独遍历 doc.Comments，按范围过滤
        comments = self.inspect_comments(range_start=range_start, range_end=range_end)
        result.comments = comments
        result.total_comments = len(comments)
        progress_logger.debug(f"{log_prefix}批注数量: {result.total_comments}")

        # 删除线+非黑字：一次遍历段落，仅在锚点范围内逐段检测，范围内检查完即结束
        strikethroughs, non_black_fonts = (
            self._inspect_paragraphs_strikethrough_and_non_black(
                range_start=range_start, range_end=range_end
            )
        )
        result.strikethroughs = strikethroughs
        result.total_strikethroughs = len(strikethroughs)
        result.non_black_fonts = non_black_fonts
        result.total_non_black_fonts = len(non_black_fonts)
        progress_logger.debug(f"{log_prefix}删除线段落数量: {result.total_strikethroughs}")
        progress_logger.debug(f"{log_prefix}非黑色字体段落数量: {result.total_non_black_fonts}")

        progress_logger.debug(f"{log_prefix}文档分析完成")
        return result

    def format_analysis_report(self, result: DocumentAnalysisResult) -> str:
        """
        格式化分析报告

        参数:
            result: 文档分析结果

        返回:
            str: 格式化的报告字符串
        """
        lines = []
        lines.append("=" * 70)
        lines.append("Word 文档分析报告")
        lines.append("=" * 70)
        lines.append("")

        lines.append("【文档保护状态】")
        if result.is_protected:
            lines.append(f"  状态: 受保护")
            lines.append(f"  保护类型: {result.protection_type}")
        else:
            lines.append(f"  状态: 无保护")
        lines.append("")

        lines.append("【批注信息】")
        lines.append(f"  总数量: {result.total_comments}")
        lines.append("-" * 50)
        for i, comment in enumerate(result.comments, 1):
            lines.append(f"  批注 {i}:")
            lines.append(f"    作者: {comment.author}")
            lines.append(f"    日期: {comment.date}")
            lines.append(
                f"    位置页码: {comment.page_number if comment.page_number else '未知'}"
            )
            lines.append(f"    批注范围: {comment.scope_text}")
            lines.append(f"    内容: {comment.content}")
            lines.append("")
        lines.append("")

        lines.append("【删除线段落】")
        lines.append(f"  总数量: {result.total_strikethroughs}")
        lines.append("-" * 50)
        for i, strikethrough in enumerate(result.strikethroughs, 1):
            lines.append(f"  删除线段落 {i}:")
            lines.append(f"    删除线所在段落: {strikethrough.paragraph_text}")
            lines.append(f"    删除线内容: {strikethrough.strikethrough_text}")
            lines.append(
                f"    位置页码: {strikethrough.page_number if strikethrough.page_number else '未知'}"
            )
            lines.append("")
        lines.append("")

        lines.append("【非黑色字体文字】")
        lines.append(f"  总数量: {result.total_non_black_fonts}")
        lines.append("-" * 50)
        for i, font_info in enumerate(result.non_black_fonts, 1):
            lines.append(f"  非黑色字体 {i}:")
            lines.append(f"    非黑色字体所在段落: {font_info.paragraph_text}")
            lines.append(f"    非黑色字体: {font_info.font_text}")
            lines.append(f"    颜色: {font_info.color_name}")
            lines.append(
                f"    位置页码: {font_info.page_number if font_info.page_number else '未知'}"
            )
            lines.append("")
        lines.append("")

        lines.append("=" * 70)
        lines.append("分析完成")
        lines.append("=" * 70)

        return "\n".join(lines)
