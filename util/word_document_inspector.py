"""
Word 文档内容检测工具

提供文档内容检测功能，包括：
- 批注检测（内容和位置）
- 删除线段落检测
- 非黑色字体文字检测
- 文档保护状态检测
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CommentInfo:
    """批注信息"""
    author: str
    date: str
    content: str
    scope_text: str
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

    def _get_log_prefix(self) -> str:
        return f"[{self.node_name}] " if self.node_name else ""

    def _get_page_number(self, range_obj: any) -> int:
        """获取_range所在的页码"""
        try:
            if hasattr(range_obj, 'Information'):
                return range_obj.Information(2)
        except Exception:
            pass
        return 0

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
            logger.debug(f"{log_prefix}文档保护类型: {protection_type} (-1 表示无保护)")

            if protection_type == -1:
                return False, protection_type
            return True, protection_type
        except Exception as e:
            logger.warning(f"{log_prefix}检查文档保护时出错: {e}")
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

    def inspect_comments(self) -> list[CommentInfo]:
        """
        检测文档中所有的批注

        返回:
            list[CommentInfo]: 批注信息列表
        """
        log_prefix = self._get_log_prefix()
        comments = []

        try:
            comments_collection = self.doc.Comments
            comment_count = comments_collection.Count
            logger.debug(f"{log_prefix}检测到 {comment_count} 个批注")

            for i in range(1, comment_count + 1):
                try:
                    comment = comments_collection.Item(i)
                    range_obj = comment.Range

                    scope_obj = comment.Scope
                    scope_text = scope_obj.Text if scope_obj else ""

                    comment_info = CommentInfo(
                        author=comment.Author or "",
                        date=str(comment.Date) if comment.Date else "",
                        content=range_obj.Text or "",
                        scope_text=scope_text or "",
                        range_text=range_obj.Text or "",
                        page_number=self._get_page_number(range_obj)
                    )
                    comments.append(comment_info)

                    logger.debug(f"{log_prefix}批注 {i}: 作者='{comment_info.author}', "
                               f"日期='{comment_info.date}', 批注内容='{comment_info.content}', "
                               f"批注范围='{comment_info.scope_text}'")

                except Exception as e:
                    logger.warning(f"{log_prefix}读取批注 {i} 时出错: {e}")
                    continue

        except Exception as e:
            logger.warning(f"{log_prefix}获取批注集合时出错: {e}")

        return comments

    def inspect_strikethroughs(self) -> list[StrikethroughInfo]:
        """
        检测文档中带有删除线的段落

        返回:
            list[StrikethroughInfo]: 删除线段落信息列表
        """
        log_prefix = self._get_log_prefix()
        strikethroughs = []

        try:
            paragraphs = self.doc.Paragraphs
            total_paragraphs = paragraphs.Count
            logger.debug(f"{log_prefix}开始检测 {total_paragraphs} 个段落")

            for i in range(1, total_paragraphs + 1):
                try:
                    paragraph = paragraphs.Item(i)
                    range_obj = paragraph.Range
                    paragraph_text = range_obj.Text or ""

                    if hasattr(range_obj.Font, 'StrikeThrough') and range_obj.Font.StrikeThrough:
                        strikethrough_segments = []
                        current_segment = []

                        for j in range(1, range_obj.Characters.Count + 1):
                            try:
                                char = range_obj.Characters.Item(j)
                                if hasattr(char.Font, 'StrikeThrough') and char.Font.StrikeThrough:
                                    current_segment.append(char.Text)
                                else:
                                    if current_segment:
                                        segment_text = ''.join(current_segment).strip()
                                        if segment_text:
                                            strikethrough_segments.append(segment_text)
                                        current_segment = []
                            except Exception:
                                continue

                        if current_segment:
                            segment_text = ''.join(current_segment).strip()
                            if segment_text:
                                strikethrough_segments.append(segment_text)

                        strikethrough_text = '、'.join(strikethrough_segments)

                        if paragraph_text.strip() and strikethrough_text:
                            strikethrough_info = StrikethroughInfo(
                                paragraph_text=paragraph_text.strip(),
                                strikethrough_text=strikethrough_text,
                                range_text=paragraph_text,
                                page_number=self._get_page_number(range_obj)
                            )
                            strikethroughs.append(strikethrough_info)
                            logger.debug(f"{log_prefix}删除线段落 {len(strikethroughs)}: '{paragraph_text}', 删除线内容: '{strikethrough_text}'")

                except Exception as e:
                    logger.warning(f"{log_prefix}检测段落 {i} 的删除线时出错: {e}")
                    continue

        except Exception as e:
            logger.warning(f"{log_prefix}获取段落集合时出错: {e}")

        return strikethroughs

    def inspect_non_black_fonts(self) -> list[NonBlackFontInfo]:
        """
        检测文档中字体颜色不是黑色的文字

        返回:
            list[NonBlackFontInfo]: 非黑色字体文字信息列表
        """
        log_prefix = self._get_log_prefix()
        non_black_fonts = []

        try:
            paragraphs = self.doc.Paragraphs
            total_paragraphs = paragraphs.Count
            logger.debug(f"{log_prefix}开始检测 {total_paragraphs} 个段落的字体颜色")

            for i in range(1, total_paragraphs + 1):
                try:
                    paragraph = paragraphs.Item(i)
                    range_obj = paragraph.Range
                    paragraph_text = range_obj.Text or ""

                    if "申报人名称" in paragraph_text and "填写单位全称" in paragraph_text:
                        continue

                    if hasattr(range_obj.Font, 'Color'):
                        color_value = range_obj.Font.Color

                        if (color_value != self.BLACK_COLOR and 
                            color_value != self.AUTOMATIC_COLOR and
                            color_value != self.WINDOWS_AUTO_COLOR):
                            font_segments = []
                            current_segment = []
                            font_name = ""
                            font_size = 0.0

                            for j in range(1, range_obj.Characters.Count + 1):
                                try:
                                    char = range_obj.Characters.Item(j)
                                    if hasattr(char.Font, 'Color'):
                                        char_color = char.Font.Color
                                        if (char_color != self.BLACK_COLOR and 
                                            char_color != self.AUTOMATIC_COLOR and
                                            char_color != self.WINDOWS_AUTO_COLOR):
                                            current_segment.append(char.Text)
                                            if not font_name and hasattr(char.Font, 'Name'):
                                                font_name = char.Font.Name or ""
                                            if font_size == 0.0 and hasattr(char.Font, 'Size'):
                                                font_size = char.Font.Size or 0.0
                                        else:
                                            if current_segment:
                                                segment_text = ''.join(current_segment).strip()
                                                if segment_text:
                                                    font_segments.append(segment_text)
                                                current_segment = []
                                except Exception:
                                    continue

                            if current_segment:
                                segment_text = ''.join(current_segment).strip()
                                if segment_text:
                                    font_segments.append(segment_text)

                            font_text = '、'.join(font_segments)

                            if paragraph_text.strip() and font_text:
                                font_info = NonBlackFontInfo(
                                    paragraph_text=paragraph_text.strip(),
                                    font_text=font_text,
                                    color=color_value,
                                    color_name=self.get_color_name(color_value),
                                    range_text=paragraph_text,
                                    font_name=font_name,
                                    font_size=font_size,
                                    page_number=self._get_page_number(range_obj)
                                )
                                non_black_fonts.append(font_info)
                                logger.debug(f"{log_prefix}非黑色字体段落 {len(non_black_fonts)}: "
                                           f"颜色='{font_info.color_name}', 文字='{font_text}'")

                except Exception as e:
                    logger.warning(f"{log_prefix}检测段落 {i} 的字体颜色时出错: {e}")
                    continue

        except Exception as e:
            logger.warning(f"{log_prefix}获取段落集合时出错: {e}")

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

                            if hasattr(sentence.Font, 'Color'):
                                color_value = sentence.Font.Color

                                if color_value != self.BLACK_COLOR and color_value != self.AUTOMATIC_COLOR:
                                    text = sentence.Text or ""
                                    if text.strip():
                                        font_info = NonBlackFontInfo(
                                            text=text.strip(),
                                            color=color_value,
                                            color_name=self.get_color_name(color_value),
                                            range_text=text,
                                            font_name=sentence.Font.Name or "",
                                            font_size=sentence.Font.Size if hasattr(sentence.Font, 'Size') else 0.0,
                                            page_number=self._get_page_number(sentence)
                                        )
                                        non_black_fonts.append(font_info)

                        except Exception as e:
                            logger.debug(f"{log_prefix}检测 {story_name} 句子 {j} 时出错: {e}")
                            continue

                except Exception as e:
                    logger.debug(f"{log_prefix}获取 {story_name} 句子集合时出错: {e}")

        except Exception as e:
            logger.warning(f"{log_prefix}检测非黑色字体时出错: {e}")

        return non_black_fonts

    def analyze_document(self) -> DocumentAnalysisResult:
        """
        综合分析文档

        返回:
            DocumentAnalysisResult: 文档分析结果
        """
        log_prefix = self._get_log_prefix()
        logger.info(f"{log_prefix}开始综合分析文档...")

        result = DocumentAnalysisResult()

        is_protected, protection_type = self.check_protection()
        result.is_protected = is_protected
        result.protection_type = protection_type

        logger.info(f"{log_prefix}文档保护状态: {'受保护' if is_protected else '无保护'}")

        comments = self.inspect_comments()
        result.comments = comments
        result.total_comments = len(comments)
        logger.info(f"{log_prefix}批注数量: {result.total_comments}")

        strikethroughs = self.inspect_strikethroughs()
        result.strikethroughs = strikethroughs
        result.total_strikethroughs = len(strikethroughs)
        logger.info(f"{log_prefix}删除线段落数量: {result.total_strikethroughs}")

        non_black_fonts = self.inspect_non_black_fonts()
        result.non_black_fonts = non_black_fonts
        result.total_non_black_fonts = len(non_black_fonts)
        logger.info(f"{log_prefix}非黑色字体段落数量: {result.total_non_black_fonts}")

        logger.info(f"{log_prefix}文档分析完成")
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
            lines.append(f"    位置页码: {comment.page_number if comment.page_number else '未知'}")
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
            lines.append(f"    位置页码: {strikethrough.page_number if strikethrough.page_number else '未知'}")
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
            lines.append(f"    位置页码: {font_info.page_number if font_info.page_number else '未知'}")
            lines.append("")
        lines.append("")

        lines.append("=" * 70)
        lines.append("分析完成")
        lines.append("=" * 70)

        return "\n".join(lines)
