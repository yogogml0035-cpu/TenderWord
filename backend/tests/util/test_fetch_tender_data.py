from __future__ import annotations

from importlib import import_module

import pytest

from backend.util.common_util import fetch_tender_data as fetch_tender_data_function

fetch_tender_data_module = import_module("backend.util.common_util.fetch_tender_data")


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


@pytest.mark.parametrize("tender_lx", [1, 2])
def test_fetch_tender_data_preserves_supported_tender_lx(monkeypatch, tender_lx: int):
    payload = {
        "data": {
            "project_name": "68Ge/68Ga发生器",
            "project_number": "261004",
            "project_content": "68Ge/68Ga发生器 壹台",
            "buyer_name": "上海市东方医院",
            "bzj_rule": "项目预算的2.0%",
            "project_zbr_xbr": "周晟、王之风",
            "zbr_xbr_tel": "8609、8631",
            "zbr_pinyin": "zhousheng",
            "shell_start_date": "2026年04月30日",
            "shell_end_date": "2026年05月11日",
            "submit_date": "2026年05月21日 10:00",
            "platform": "中国招标投标公共服务平台",
            "service_fee": "按比例收取:1.5%",
            "ifdzpt2": "3",
            "ifzgcg": "2",
            "fund_lx": 0,
        },
        "type": {
            "tender_lx": tender_lx,
            "purchase_method": 2,
            "fund_lx": 0,
        },
    }

    monkeypatch.setattr(
        fetch_tender_data_module.requests,
        "get",
        lambda *args, **kwargs: _FakeResponse(payload),
    )
    monkeypatch.setattr(
        fetch_tender_data_module.settings,
        "TENDER_DATA_API_URL",
        "https://example.com/tender",
    )

    result = fetch_tender_data_function("0811-DSITC261224")

    assert result["data"]["ifdzpt2"] == 3
    assert result["data"]["ifzgcg"] == 2
    assert result["data"]["fund_source_lx"] == 0
    assert result["data"]["investment"] == ""
    assert result["type"] == {
        "tender_lx": tender_lx,
        "purchase_method": 2,
        "fund_lx": 0,
    }


def test_fetch_tender_data_preserves_investment(monkeypatch):
    payload = {
        "data": {
            "project_name": "医疗设备采购",
            "project_number": "261005",
            "project_content": "设备一批",
            "buyer_name": "上海市东方医院",
            "investment": "140.0",
            "fund_lx": 0,
        },
        "type": {
            "tender_lx": 0,
            "purchase_method": 2,
            "fund_lx": 0,
        },
    }

    monkeypatch.setattr(
        fetch_tender_data_module.requests,
        "get",
        lambda *args, **kwargs: _FakeResponse(payload),
    )
    monkeypatch.setattr(
        fetch_tender_data_module.settings,
        "TENDER_DATA_API_URL",
        "https://example.com/tender",
    )

    result = fetch_tender_data_function("0811-DSITC261005")

    assert result["data"]["investment"] == "140.0"
