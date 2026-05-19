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
    assert response.type is not None
    assert response.type.fund_lx == 1
