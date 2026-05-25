import pytest

from backend.api import tender as tender_api


@pytest.mark.asyncio
async def test_get_tender_data_preserves_ifzgcg(monkeypatch):
    monkeypatch.setattr(
        tender_api,
        "fetch_tender_data",
        lambda tender_no: {
            "data": {
                "project_name": "68Ge/68Ga发生器",
                "project_number": "261004",
                "project_content": "68Ge/68Ga发生器 壹台",
                "buyer_name": "上海市东方医院",
                "investment": "140.0",
                "ifzgcg": 2,
            },
            "type": {
                "tender_lx": 0,
                "purchase_method": 2,
                "fund_lx": 1,
            },
        },
    )

    response = await tender_api.get_tender_data("0811-DSITC261004")

    assert response.data is not None
    assert response.data.ifzgcg == 2
    assert response.data.investment == "140.0"
    assert response.type is not None
    assert response.type.fund_lx == 1


@pytest.mark.asyncio
async def test_get_tender_data_coerces_numeric_investment(monkeypatch):
    monkeypatch.setattr(
        tender_api,
        "fetch_tender_data",
        lambda tender_no: {
            "data": {
                "project_name": "物业管理服务",
                "project_number": "251498",
                "project_content": "物业管理服务 一项",
                "buyer_name": "上海市某单位",
                "investment": 30.0,
            },
            "type": {
                "tender_lx": 2,
                "purchase_method": 2,
                "fund_lx": 0,
            },
        },
    )

    response = await tender_api.get_tender_data("0811-DSITC251498")

    assert response.data is not None
    assert response.data.investment == "30.0"
    assert response.type is not None
    assert response.type.purchase_method == 2
