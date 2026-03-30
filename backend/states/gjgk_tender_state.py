"""国际公开文档生成 State 定义。"""

from __future__ import annotations

from .base_state import TenderGraphStateBase


class GjgkTenderGraphState(TenderGraphStateBase, total=False):
    """国际公开 Graph 的主状态类。"""

    fund_source_lx: str
    tender_invitation: str
    delivery_location: str
