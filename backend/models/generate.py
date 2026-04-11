"""
生成请求/响应模型

定义文档生成相关的 Pydantic 模型，用于 API 请求和响应。
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from .tender import TenderData
from .task import TaskKind, TaskProgress, TaskStatus


class LLMModel(str, Enum):
    """
    支持的 LLM 模型枚举
    """

    DEEPSEEK = "deepseek"
    QWEN = "qwen"
    DOUBAO = "doubao"


class GenerationStyle(str, Enum):
    """生成风格枚举，仅影响初次 generate 的 prompt 路由。"""

    TEMPLATE = "template"
    PARAM = "param"


class FormType(str, Enum):
    """
    表单类型枚举

    对应 config/form_config.py 中的 form_id
    """

    XJCG_TENDER = "xjcg_tender"  # 询价采购
    GNGK_HW_ZC_TENDER = "gngk_hw_zc_tender"  # 国内公开（货物 / 自筹）
    GNGK_HW_CZ_TENDER = "gngk_hw_cz_tender"  # 国内公开（货物 / 财政）
    GNGK_FW_ZC_TENDER = "gngk_fw_zc_tender"  # 国内公开（服务 / 自筹）
    GNGK_FW_CZ_TENDER = "gngk_fw_cz_tender"  # 国内公开（服务 / 财政）
    GJGK_TENDER = "gjgk_tender"  # 国际公开


class InsertionConfig(BaseModel):
    before_text: Optional[str] = Field(default=None, description="插入位置前文本（锚点）")
    after_text: Optional[str] = Field(default=None, description="插入位置后文本（锚点）")


class GenerateRequest(BaseModel):
    """
    文档生成请求模型

    Attributes:
        form_type: 表单类型
        tender_data: 招标数据
        file_paths: 文件路径字典
            - template: 模板文件路径
            - params: 技术参数文件路径列表
        model: 使用的 LLM 模型
    """

    form_type: FormType = Field(
        ...,
        description="表单类型",
        examples=[
            "xjcg_tender",
            "gngk_hw_zc_tender",
            "gngk_hw_cz_tender",
            "gngk_fw_zc_tender",
            "gngk_fw_cz_tender",
            "gjgk_tender",
        ],
    )
    tender_data: TenderData = Field(..., description="招标数据")
    file_paths: Dict[str, str | List[str]] = Field(..., description="文件路径字典")
    insertion_config: Optional[InsertionConfig] = Field(
        default=None, description="插入锚点配置（可选）"
    )
    generation_style: GenerationStyle = Field(
        default=GenerationStyle.TEMPLATE,
        description="生成风格（仅初次 generate 生效）",
    )
    conversation_id: Optional[str] = Field(
        default=None, description="会话ID，用于会话级 rewrite 历史与状态管理"
    )
    model: LLMModel = Field(default=LLMModel.DEEPSEEK, description="使用的 LLM 模型")

    model_config = {
        "json_schema_extra": {
            "example": {
                "form_type": "xjcg_tender",
                "tender_data": {
                    "project_name": "某某信息化系统采购项目",
                    "project_number": "ZBGG-2024-001",
                    "project_content": "采购信息化系统一套...",
                    "buyer_name": "某某事业单位",
                    "bzj_rule": "投标保证金为项目预算的2%",
                    "project_zbr_xbr": "张三",
                    "zbr_xbr_tel": "13800138000",
                    "zbr_pinyin": "zhangsan",
                    "shell_start_date": "2024-03-01",
                    "shell_end_date": "2024-03-15",
                    "submit_date": "2024-03-20",
                    "platform": "中国政府采购网",
                    "service_fee": "5000元",
                    "tender_lx": 0,
                    "fund_source_lx": 1,
                },
                "file_paths": {
                    "template": "D:/UploadFiles/template.docx",
                    "params": [
                        "D:/UploadFiles/params1.docx",
                        "D:/UploadFiles/params2.docx",
                    ],
                },
                "insertion_config": {
                    "before_text": "第三章 采购需求",
                    "after_text": "第四章 响应文件有关格式",
                },
                "generation_style": "template",
                "model": "deepseek",
            }
        }
    }


class EditTaskRequest(BaseModel):
    """显式 edit 文档修改请求模型。"""

    conversation_id: str = Field(..., min_length=1, description="会话ID")
    form_type: FormType = Field(..., description="表单类型")
    model: LLMModel = Field(default=LLMModel.DEEPSEEK, description="使用的 LLM 模型")
    edit_prompt: str = Field(..., min_length=1, description="用户修改指令")
    file_path: Optional[str] = Field(default=None, description="待修改 Word 文档路径")
    insertion_config: Optional[InsertionConfig] = Field(
        default=None, description="插入锚点配置（可选）"
    )
    tender_lx: int = Field(..., description="标的类型编码（0=货物, 1=服务）")
    fund_source_lx: int = Field(..., description="资金性质编码（0=自筹, 1=财政）")
    tender_data_snapshot: Optional[TenderData] = Field(
        default=None,
        description="当前页面招标数据快照（可选透传，用于保留会话上下文）",
    )

    @field_validator("conversation_id", "edit_prompt")
    @classmethod
    def _validate_non_empty_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized

    @field_validator("tender_lx", "fund_source_lx")
    @classmethod
    def _validate_binary_flag(cls, value: int) -> int:
        if value not in (0, 1):
            raise ValueError("字段必须是 0 或 1")
        return int(value)


class GenerateResponse(BaseModel):
    """
    文档生成响应模型

    Attributes:
        success: 是否成功
        task_id: 任务ID
        message: 消息说明
        output_file: 输出文件路径（仅完成时）
        download_url: 下载链接（仅完成时）
        progress: 任务进度信息
    """

    success: bool = Field(..., description="是否成功")
    task_id: str = Field(..., description="任务ID")
    message: str = Field(default="", description="消息说明")
    task_kind: TaskKind = Field(default=TaskKind.GENERATE, description="任务类别")
    status: Optional[TaskStatus] = Field(default=None, description="任务当前状态")
    queue_position: Optional[int] = Field(
        default=None,
        description="队列位置（0=正在执行, -1=不在队列中）",
    )
    waiting_count: Optional[int] = Field(default=None, description="前方等待任务数")
    output_file: Optional[str] = Field(default=None, description="输出文件路径")
    download_url: Optional[str] = Field(default=None, description="文件下载链接")
    progress: Optional[TaskProgress] = Field(default=None, description="任务进度信息")
    error: Optional[str] = Field(default=None, description="错误信息（失败时）")


class GenerateResult(BaseModel):
    """
    文档生成结果模型

    用于存储任务完成后的结果
    """

    output_file: str = Field(..., description="输出文件路径")
    output_filename: str = Field(..., description="输出文件名")
    file_size: Optional[int] = Field(default=None, description="文件大小（字节）")
    download_url: Optional[str] = Field(default=None, description="下载链接")
    processing_time: Optional[float] = Field(default=None, description="处理时间（秒）")


class FileRequirement(BaseModel):
    """
    文件要求模型

    描述生成所需文件的类型和要求
    """

    key: str = Field(..., description="文件键名")
    name: str = Field(..., description="文件显示名称")
    description: str = Field(default="", description="文件说明")
    required: bool = Field(default=True, description="是否必需")
    accept_types: List[str] = Field(
        default_factory=lambda: [".docx", ".doc"], description="接受的文件类型"
    )
    multiple: bool = Field(default=False, description="是否允许多文件")


class FormRequirementsResponse(BaseModel):
    """
    表单文件要求响应模型

    返回指定表单类型的文件上传要求
    """

    form_type: FormType = Field(..., description="表单类型")
    form_name: str = Field(..., description="表单显示名称")
    required_files: List[FileRequirement] = Field(
        default_factory=list, description="必需文件列表"
    )
    optional_files: List[FileRequirement] = Field(
        default_factory=list, description="可选文件列表"
    )
    description: str = Field(default="", description="表单描述")
