from __future__ import annotations

from typing import Dict, List, Optional, Tuple, TypedDict


class CommentInstruction(TypedDict):
    reference_text: str
    comment_text: str


class XjcgTenderGraphState(TypedDict, total=False):
    origin_tender_path: str  # 技术需求草稿文件路径
    tender_param_paths: List[str]  # 技术参数文件路径列表
    origin_tender_params: str  # 上一次项目文档参考的技术参数内容
    tender_params: str  # 技术参数内容
    replacements: List[Tuple[str, str]]  # Word 模板替换对列表
    placeholder_mapping: Dict[str, str]  # 字段名到占位符的映射关系
    prepared_doc_path: str  # 当前加工中的文档路径
    insertion_before_text: str  # 插入位置的前置文本
    insertion_after_text: str  # 插入位置的后置文本
    polished_text: str  # 大模型润色后的文本
    insertion_log: str  # Word 写入过程的状态记录
    replacement_log: str  # 内容替换过程的状态记录
    comments_summary: str  # 批注添加结果摘要
    comment_plan: List[CommentInstruction]  # 批注指令列表
    project_name: str  # 项目名称
    project_number: str  # 项目编号
    project_content: str  # 项目名称及数量
    bzj_rule: str  # 保证金规则
    buyer_name: str  # 采购人名称
    project_zbr_xbr: str  # 项目负责人和项目协助人
    zbr_xbr_tel: str  # 负责人和协助人电话
    zbr_pinyin: str  # 负责人拼音
    shell_start_date: str
    shell_end_date: str
    submit_date: str
    platform: str
    service_fee: str
    generate_polished_done: bool  # generate_polished_text 是否完成
    replace_content_done: bool  # replace_content 是否完成


class TextFormatState(TypedDict, total=False):
    input_text: str  # 输入的原始文本
    formatted_text: str  # 格式化后的文本
    output_file_path: str  # 输出文件路径
