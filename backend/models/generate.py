"""
生成请求/响应模型

定义文档生成相关的 Pydantic 模型，用于 API 请求和响应。
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from .tender import TenderData

from .tender import TenderData
from .task import TaskProgress, TaskStatus


class LLMModel(str, Enum):
    """
    支持的 LLM 模型枚举
    """

    DEEPSEEK = "deepseek"
    QWEN = "qwen"
    DOUBAO = "doubao"


class FormType(str, Enum):
    """
    表单类型枚举

    对应 config/form_config.py 中的 form_id
    """

    XJCG_TENDER = "xjcg_tender"  # 询价采购
    GNGK_TENDER = "gngk_tender"  # 国内公开招标


class GenerateRequest(BaseModel):
    """
    文档生成请求模型

    Attributes:
        form_type: 表单类型（xjcg_tender | gngk_tender）
        tender_data: 招标数据
        file_paths: 文件路径字典
            - template: 模板文件路径
            - params: 技术参数文件路径列表
        model: 使用的 LLM 模型
    """

    form_type: FormType = Field(
        ..., description="表单类型", examples=["xjcg_tender", "gngk_tender"]
    )
    tender_data: TenderData = Field(..., description="招标数据")
    file_paths: Dict[str, str | List[str]] = Field(..., description="文件路径字典")
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
                },
                "file_paths": {
                    "template": "D:/UploadFiles/template.docx",
                    "params": [
                        "D:/UploadFiles/params1.docx",
                        "D:/UploadFiles/params2.docx",
                    ],
                },
                "model": "deepseek",
            }
        }
    }


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
