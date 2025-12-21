"""
Word COM 常量定义

统一管理所有 Word COM 操作所需的常量，避免在各个节点文件中重复定义。

参考文档：
- https://docs.microsoft.com/en-us/office/vba/api/word.wdunits
- https://docs.microsoft.com/en-us/office/vba/api/word.wdcollapseirection
"""

# ============================================================================
# 查找和替换相关常量
# ============================================================================

# WdFindWrap 枚举 - 控制查找操作的换行行为
wdFindStop = 0          # 到达搜索范围末尾时停止
wdFindContinue = 1      # 继续从文档开头搜索
wdFindAsk = 2           # 询问用户是否继续

# ============================================================================
# 光标折叠相关常量
# ============================================================================

# WdCollapseDirection 枚举 - 控制 Range.Collapse 的方向
wdCollapseStart = 1     # 折叠到范围起始位置
wdCollapseEnd = 0       # 折叠到范围结束位置

# ============================================================================
# 页面导航相关常量
# ============================================================================

# WdGoToItem 枚举 - GoTo 方法的目标类型
wdGoToPage = 1          # 跳转到页面
wdGoToSection = 0       # 跳转到节
wdGoToLine = 3          # 跳转到行
wdGoToBookmark = -1     # 跳转到书签
wdGoToTable = 2         # 跳转到表格

# WdGoToDirection 枚举 - GoTo 方法的方向
wdGoToAbsolute = 1      # 绝对位置
wdGoToRelative = 2      # 相对位置
wdGoToFirst = 1         # 第一个
wdGoToLast = -1         # 最后一个
wdGoToNext = 2          # 下一个
wdGoToPrevious = 3      # 上一个

# ============================================================================
# 页面信息相关常量
# ============================================================================

# WdInformation 枚举 - Range.Information 属性的类型
wdActiveEndPageNumber = 3       # 当前范围结束位置所在的页码
wdActiveEndSectionNumber = 2    # 当前范围结束位置所在的节号
wdNumberOfPagesInDocument = 4   # 文档总页数
wdWithInTable = 12              # 范围是否在表格中

# ============================================================================
# 行间距相关常量
# ============================================================================

# WdLineSpacing 枚举 - 段落行间距规则
wdLineSpaceSingle = 0       # 单倍行距
wdLineSpace1pt5 = 1         # 1.5 倍行距
wdLineSpaceDouble = 2       # 双倍行距
wdLineSpaceAtLeast = 3      # 最小值
wdLineSpaceExactly = 4      # 固定值
wdLineSpaceMultiple = 5     # 多倍行距

# ============================================================================
# 大纲级别相关常量
# ============================================================================

# WdOutlineLevel 枚举 - 段落大纲级别
wdOutlineLevel1 = 1
wdOutlineLevel2 = 2
wdOutlineLevel3 = 3
wdOutlineLevel4 = 4
wdOutlineLevel5 = 5
wdOutlineLevel6 = 6
wdOutlineLevel7 = 7
wdOutlineLevel8 = 8
wdOutlineLevel9 = 9
wdOutlineLevelBodyText = 10  # 正文文本

# ============================================================================
# 文档保护相关常量
# ============================================================================

# WdProtectionType 枚举 - 文档保护类型
wdNoProtection = -1             # 无保护
wdAllowOnlyRevisions = 0        # 只允许修订
wdAllowOnlyComments = 1         # 只允许批注
wdAllowOnlyFormFields = 2       # 只允许填写窗体
wdAllowOnlyReading = 3          # 只读

# ============================================================================
# 段落对齐相关常量
# ============================================================================

# WdParagraphAlignment 枚举 - 段落对齐方式
wdAlignParagraphLeft = 0        # 左对齐
wdAlignParagraphCenter = 1      # 居中
wdAlignParagraphRight = 2       # 右对齐
wdAlignParagraphJustify = 3     # 两端对齐
wdAlignParagraphDistribute = 4  # 分散对齐

# ============================================================================
# 单元格垂直对齐相关常量
# ============================================================================

# WdCellVerticalAlignment 枚举 - 表格单元格垂直对齐
wdCellAlignVerticalTop = 0      # 顶部对齐
wdCellAlignVerticalCenter = 1   # 垂直居中
wdCellAlignVerticalBottom = 3   # 底部对齐

# ============================================================================
# 页眉页脚相关常量
# ============================================================================

# WdHeaderFooterIndex 枚举 - 页眉页脚索引
wdHeaderFooterPrimary = 1       # 奇数页页眉/页脚（主要）
wdHeaderFooterFirstPage = 2     # 首页页眉/页脚
wdHeaderFooterEvenPages = 3     # 偶数页页眉/页脚

# WdStoryType 枚举 - 文档故事类型（用于遍历文档各部分）
wdMainTextStory = 1             # 正文
wdFootnotesStory = 2            # 脚注
wdEndnotesStory = 3             # 尾注
wdCommentsStory = 4             # 批注
wdTextFrameStory = 5            # 文本框
wdEvenPagesHeaderStory = 6      # 偶数页页眉
wdPrimaryHeaderStory = 7        # 奇数页页眉（主要）
wdEvenPagesFooterStory = 8      # 偶数页页脚
wdPrimaryFooterStory = 9        # 奇数页页脚（主要）
wdFirstPageHeaderStory = 10     # 首页页眉
wdFirstPageFooterStory = 11     # 首页页脚

