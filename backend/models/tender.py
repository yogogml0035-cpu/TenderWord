"""
招标数据模型

定义招标相关的 Pydantic 模型，用于 API 请求和响应。
基于 states/base_state.py 中的 TenderGraphStateBase 定义。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TenderType(BaseModel):
    """
    招标类型信息

    对应 config/form_config.py 中的 URL 参数映射
    """

    tender_lx: int = Field(
        ..., description="招标类型（0=询价, 1=国内公开, 2=邀请招标）", ge=0, le=2
    )
    purchase_method: int = Field(
        ..., description="采购方式（5=询价采购, 1=国内公开, 2=邀请招标）", ge=0, le=5
    )
    fund_lx: int = Field(..., description="资金类型（0=国内, 1=国际）", ge=0, le=1)


class TenderData(BaseModel):
    """
    招标数据模型

    基于 states/base_state.py 中的 TenderGraphStateBase 定义。
    包含招标项目的基本信息字段。

    Attributes:
        project_name: 项目名称
        project_number: 项目编号
        project_content: 项目内容/采购需求
        buyer_name: 采购人名称
        bzj_rule: 保证金规则说明
        project_zbr_xbr: 项目负责人姓名（主标人或协标人）
        zbr_xbr_tel: 负责人联系电话
        zbr_pinyin: 负责人姓名拼音（用于文件命名）
        shell_start_date: 投标开始日期
        shell_end_date: 投标截止日期
        submit_date: 提交/开标日期
        platform: 招标平台名称
        service_fee: 服务费金额
    """

    # 项目基本信息
    project_name: str = Field(
        ..., description="项目名称", min_length=1, examples=["某某系统采购项目"]
    )
    project_number: str = Field(
        ...,
        description="项目编号（招标编号）",
        min_length=1,
        examples=["ZBGG-2024-001"],
    )
    project_content: str = Field(..., description="项目内容/采购需求描述", min_length=1)
    buyer_name: str = Field(
        ..., description="采购人名称", min_length=1, examples=["某某单位"]
    )

    # 规则和联系人信息
    bzj_rule: str = Field(default="", description="保证金规则说明")
    project_zbr_xbr: str = Field(
        default="", description="项目负责人姓名（主标人或协标人）"
    )
    zbr_xbr_tel: str = Field(default="", description="负责人联系电话")
    zbr_pinyin: str = Field(default="", description="负责人姓名拼音（用于文件命名）")

    # 日期信息
    shell_start_date: str = Field(
        default="",
        description="投标开始日期（格式：YYYY-MM-DD）",
        examples=["2024-03-01"],
    )
    shell_end_date: str = Field(
        default="",
        description="投标截止日期（格式：YYYY-MM-DD）",
        examples=["2024-03-15"],
    )
    submit_date: str = Field(
        default="",
        description="提交/开标日期（格式：YYYY-MM-DD）",
        examples=["2024-03-20"],
    )

    # 平台和服务信息
    platform: str = Field(
        default="", description="招标平台名称", examples=["中国政府采购网"]
    )
    service_fee: str = Field(default="", description="服务费金额", examples=["5000元"])

    model_config = {
        "json_schema_extra": {
            "example": {
                "project_name": "某某信息化系统采购项目",
                "project_number": "ZBGG-2024-001",
                "project_content": "采购信息化系统一套，包含硬件和软件...",
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
            }
        }
    }


class TenderFormConfig(BaseModel):
    """
    表单配置模型

    对应 config/form_config.py 中的 FormConfig dataclass
    """

    form_id: str = Field(..., description="表单唯一标识符", examples=["xjcg_tender"])
    tab_name: str = Field(
        ..., description="显示的标签名称", examples=["生成询价采购文件"]
    )
    graph_name: str = Field(
        ..., description="关联的 graph 名称", examples=["xjcg_tender_graph"]
    )
    state_name: str = Field(
        ..., description="关联的 state 名称", examples=["XjcgTenderGraphState"]
    )
    url_params: TenderType = Field(..., description="URL 参数映射")
    description: str = Field(default="", description="表单描述")
