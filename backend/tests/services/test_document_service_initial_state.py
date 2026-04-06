from __future__ import annotations

from backend.models.generate import FormType, GenerateRequest, LLMModel
from backend.models.tender import TenderData
from backend.services.document_service import DocumentService


def build_request(*, origin_tender: str | None, template: str | None) -> GenerateRequest:
    file_paths: dict[str, object] = {"tender_params": ["D:/UploadFiles/params.docx"]}
    if origin_tender is not None:
        file_paths["origin_tender"] = origin_tender
    if template is not None:
        file_paths["template"] = template

    return GenerateRequest(
        form_type=FormType.GJGK_TENDER,
        tender_data=TenderData(
            project_name="国际公开测试项目",
            project_number="0811-254DSITC2512",
            project_content="采购内容",
            buyer_name="采购人",
            bzj_rule="规则",
            project_zbr_xbr="张三",
            zbr_xbr_tel="13800000000",
            zbr_pinyin="zhangsan",
            shell_start_date="2026-04-01",
            shell_end_date="2026-04-08",
            submit_date="2026-04-09",
            platform="平台",
            service_fee="1000",
            tender_lx=0,
            fund_source_lx=1,
        ),
        file_paths=file_paths,
        model=LLMModel.DEEPSEEK,
    )


def test_build_initial_state_prefers_explicit_origin_tender() -> None:
    service = object.__new__(DocumentService)
    request = build_request(
        origin_tender=" D:/UploadFiles/review.docx ",
        template="D:/UploadFiles/template.docx",
    )

    state = service._build_initial_state(request, task_id="task-1")

    assert state["origin_tender_path"] == " D:/UploadFiles/review.docx "
    assert state["source_origin_tender_path"] == "D:/UploadFiles/review.docx"
    assert state["template_path"] == "D:/UploadFiles/template.docx"
    assert state["project_number"] == "254DSITC2512"
    assert "254DSITC2512" in state["tender_invitation"]


def test_build_initial_state_falls_back_to_template_without_origin_tender() -> None:
    service = object.__new__(DocumentService)
    request = build_request(
        origin_tender=None,
        template="D:/UploadFiles/template.docx",
    )

    state = service._build_initial_state(request, task_id="task-2")

    assert state["origin_tender_path"] == "D:/UploadFiles/template.docx"
    assert state["source_origin_tender_path"] == ""
    assert state["template_path"] == "D:/UploadFiles/template.docx"
