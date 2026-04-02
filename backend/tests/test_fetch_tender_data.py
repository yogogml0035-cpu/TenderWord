from dataclasses import dataclass

import backend.util.common_util.fetch_tender_data as fetch_tender_data_util


@dataclass
class DummyResponse:
    json_payload: object

    def json(self):
        return self.json_payload

    def raise_for_status(self):
        return None


def test_fetch_tender_data_uses_settings_url_and_timeout(monkeypatch):
    monkeypatch.setattr(
        fetch_tender_data_util.settings,
        "TENDER_DATA_API_URL",
        "http://example.com/tender",
    )
    monkeypatch.setattr(
        fetch_tender_data_util.settings,
        "EXTERNAL_REQUEST_TIMEOUT_SECONDS",
        23,
    )

    def mock_get(url, params=None, timeout=None):
        assert url == "http://example.com/tender"
        assert params == {"tenderno": "ZBGG-2026-001"}
        assert timeout == 23.0
        return DummyResponse(
            json_payload={
                "data": {
                    "project_name": "示例项目",
                    "project_number": "NO-001",
                    "project_content": "采购内容",
                    "bzj_rule": "规则",
                    "buyer_name": "采购人",
                    "project_zbr_xbr": "联系人",
                    "zbr_xbr_tel": "123456",
                    "zbr_pinyin": "zbr",
                    "shell_start_date": "2026-03-01",
                    "shell_end_date": "2026-03-08",
                    "submit_date": "2026-03-09",
                    "platform": "平台A",
                    "fund_lx": 1,
                },
                "type": {
                    "tender_lx": 0,
                    "purchase_method": 0,
                    "fund_lx": 2,
                },
            }
        )

    monkeypatch.setattr(fetch_tender_data_util.requests, "get", mock_get)

    result = fetch_tender_data_util.fetch_tender_data("ZBGG-2026-001")

    assert result["data"]["project_name"] == "示例项目"
    assert result["data"]["shell_start_date"] == "2026-03-01起"
    assert result["data"]["shell_end_date"] == "2026-03-08止"
    assert result["data"]["fund_source_lx"] == 1
    assert result["type"] is None
