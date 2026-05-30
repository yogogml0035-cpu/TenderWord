"""Template candidate API models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class TemplateCandidate(BaseModel):
    tenderno: str = Field(default="", description="招标编号")
    tendername: str = Field(default="", description="项目名称")
    tname: str = Field(default="", description="采购人")
    bm: str = Field(default="", description="部门")
    hytype: str = Field(default="", description="行业类型")
    tendertype: str = Field(default="", description="招标类型")
    hwlx: str = Field(default="", description="采购方式")
    yxj: str = Field(default="", description="优先级")
    zbr: str = Field(default="", description="主办人")
    xbr: str = Field(default="", description="协办人")
    year: Optional[int] = Field(default=None, description="模板年份")
    fsg: Optional[str] = Field(default=None, description="发售稿链接")
    shener: Optional[str] = Field(default=None, description="送审稿链接")
    selectable: bool = Field(default=False, description="是否允许直接选择")
    blocked_reason: Optional[str] = Field(default=None, description="不可选原因")


class TemplateCandidateRanking(BaseModel):
    applied: bool = Field(default=False, description="本次是否实际应用了 AI 重排")
    mode: Literal["ai", "priority_only"] = Field(
        default="priority_only",
        description="排序模式",
    )
    reason: str = Field(default="", description="排序结果原因")
    message: str = Field(default="", description="排序结果提示")


class TemplateCandidateListData(BaseModel):
    candidates: List[TemplateCandidate] = Field(
        default_factory=list,
        description="模板候选列表",
    )
    ranking: TemplateCandidateRanking = Field(
        default_factory=TemplateCandidateRanking,
        description="模板候选排序元信息",
    )


class TemplateCandidateListResponse(BaseModel):
    success: bool = Field(default=True, description="请求是否成功")
    data: TemplateCandidateListData = Field(
        default_factory=TemplateCandidateListData,
        description="模板候选数据",
    )
    message: str = Field(default="模板候选获取成功", description="响应消息")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="响应时间戳",
    )


class TemplateCandidateSelectPayload(BaseModel):
    tendername: str = Field(..., min_length=1, description="模板项目名称")
    year: Optional[int] = Field(default=None, description="模板年份")
    fsg: Optional[str] = Field(default=None, description="发售稿链接")
    shener: Optional[str] = Field(default=None, description="送审稿链接")


class TemplateCandidateSelectRequest(BaseModel):
    candidate: TemplateCandidateSelectPayload = Field(..., description="所选模板")


class TemplateSelectedFile(BaseModel):
    file_path: str = Field(..., description="文件保存路径")
    file_name: str = Field(..., description="保存文件名")
    original_name: str = Field(..., description="上传区展示文件名")
    size: int = Field(..., description="文件大小")
    upload_time: str = Field(..., description="保存时间")


class TemplateSelectData(BaseModel):
    selected_file: TemplateSelectedFile = Field(..., description="成功回填的模板文件")


class TemplateSelectResponse(BaseModel):
    success: bool = Field(default=True, description="请求是否成功")
    data: TemplateSelectData = Field(..., description="选择结果")
    message: str = Field(default="模板文件选择成功", description="响应消息")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="响应时间戳",
    )
