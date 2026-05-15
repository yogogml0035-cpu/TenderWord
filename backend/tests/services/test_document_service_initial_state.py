from __future__ import annotations

import pytest

from backend.config.settings import settings
from backend.config.tender_config import get_default_anchor_texts
from backend.models.generate import (
    EditTaskRequest,
    FormType,
    GenerateRequest,
    GenerationStyle,
    LLMModel,
    StyleWritebackMode,
)
from backend.models.tender import TenderData
from backend.services import document_service
from backend.services.document_service import DocumentService, REWRITE_DEFAULT_ANCHORS


def upload_path(tmp_path, name: str) -> str:
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(exist_ok=True)
    document = upload_dir / name
    document.write_bytes(b"doc")
    return str(document)


def build_request(
    *,
    origin_tender: str | None,
    template: str | None,
    form_type: FormType = FormType.GJGK_TENDER,
    tender_lx: int = 0,
    fund_source_lx: int = 1,
    generation_style: GenerationStyle = GenerationStyle.TEMPLATE,
    style_writeback_mode: StyleWritebackMode = StyleWritebackMode.FULL,
) -> GenerateRequest:
    file_paths: dict[str, object] = {}
    if origin_tender is not None:
        file_paths["origin_tender"] = origin_tender
    if template is not None:
        file_paths["template"] = template
    file_paths["tender_params"] = ["D:/UploadFiles/params.docx"]

    return GenerateRequest(
        form_type=form_type,
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
            tender_lx=tender_lx,
            fund_source_lx=fund_source_lx,
        ),
        file_paths=file_paths,
        generation_style=generation_style,
        style_writeback_mode=style_writeback_mode,
        model=LLMModel.DEEPSEEK,
    )


def test_build_initial_state_prefers_explicit_origin_tender(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    review_path = upload_path(tmp_path, "review.docx")
    template_path = upload_path(tmp_path, "template.docx")
    params_path = upload_path(tmp_path, "params.docx")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_dir))
    service = object.__new__(DocumentService)
    request = build_request(
        origin_tender=f" {review_path} ",
        template=template_path,
    )
    request.file_paths["tender_params"] = [params_path]

    state = service._build_initial_state(request, task_id="task-1")

    assert state["origin_tender_path"] == review_path
    assert state["source_origin_tender_path"] == review_path
    assert state["template_path"] == template_path
    assert state["tender_param_paths"] == [params_path]
    assert state["project_number"] == "254DSITC2512"
    assert "254DSITC2512" in state["tender_invitation"]


def test_build_initial_state_falls_back_to_template_without_origin_tender(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    template_path = upload_path(tmp_path, "template.docx")
    params_path = upload_path(tmp_path, "params.docx")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_dir))
    service = object.__new__(DocumentService)
    request = build_request(
        origin_tender=None,
        template=template_path,
    )
    request.file_paths["tender_params"] = [params_path]

    state = service._build_initial_state(request, task_id="task-2")

    assert state["origin_tender_path"] == template_path
    assert state["source_origin_tender_path"] == ""
    assert state["template_path"] == template_path


def test_build_initial_state_carries_generation_style(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    review_path = upload_path(tmp_path, "review.docx")
    template_path = upload_path(tmp_path, "template.docx")
    params_path = upload_path(tmp_path, "params.docx")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_dir))
    service = object.__new__(DocumentService)
    request = build_request(
        origin_tender=review_path,
        template=template_path,
        generation_style=GenerationStyle.PARAM,
    )
    request.file_paths["tender_params"] = [params_path]

    state = service._build_initial_state(request, task_id="task-3")

    assert state["generation_style"] == "param"


def test_build_initial_state_carries_style_writeback_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    review_path = upload_path(tmp_path, "review.docx")
    template_path = upload_path(tmp_path, "template.docx")
    params_path = upload_path(tmp_path, "params.docx")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_dir))
    service = object.__new__(DocumentService)
    request = build_request(
        origin_tender=review_path,
        template=template_path,
        style_writeback_mode=StyleWritebackMode.BOLD_ONLY,
    )
    request.file_paths["tender_params"] = [params_path]

    state = service._build_initial_state(request, task_id="task-3b")

    assert state["style_writeback_mode"] == "bold_only"


@pytest.mark.parametrize(
    ("tender_type", "expected_before", "expected_after"),
    [
        ("gngk_fw_zc", "第三章 招标内容及要求", "第四章 投标文件有关格式"),
        ("gngk_fw_cz", "第三章 招标内容及要求", "第四章 投标文件有关格式"),
        ("gngk_hw_zc", "第三章 招标内容及要求", "第四章 投标文件有关格式"),
        ("gngk_hw_cz", "第四章  招标需求", "第五章  评标方法与程序"),
    ],
)
def test_gngk_anchor_config_defaults_follow_goods_and_service_rules(
    tender_type: str, expected_before: str, expected_after: str
) -> None:
    assert get_default_anchor_texts(tender_type) == (expected_before, expected_after)


@pytest.mark.parametrize(
    ("tender_type", "expected_before", "expected_after"),
    [
        ("gngk_fw_zc", "第三章 招标内容及要求", "第四章 投标文件有关格式"),
        ("gngk_fw_cz", "第三章 招标内容及要求", "第四章 投标文件有关格式"),
        ("gngk_hw_zc", "第三章 招标内容及要求", "第四章 投标文件有关格式"),
        ("gngk_hw_cz", "第四章  招标需求", "第五章  评标方法与程序"),
    ],
)
def test_rewrite_default_anchors_follow_gngk_goods_and_service_rules(
    tender_type: str, expected_before: str, expected_after: str
) -> None:
    assert REWRITE_DEFAULT_ANCHORS[tender_type] == (expected_before, expected_after)


@pytest.mark.parametrize(
    ("form_type", "tender_lx", "fund_source_lx", "expected_before", "expected_after"),
    [
        (
            FormType.GNGK_FW_ZC_TENDER,
            1,
            0,
            "第三章 招标内容及要求",
            "第四章 投标文件有关格式",
        ),
        (
            FormType.GNGK_FW_CZ_TENDER,
            1,
            1,
            "第三章 招标内容及要求",
            "第四章 投标文件有关格式",
        ),
        (
            FormType.GNGK_HW_ZC_TENDER,
            0,
            0,
            "第三章 招标内容及要求",
            "第四章 投标文件有关格式",
        ),
        (
            FormType.GNGK_HW_CZ_TENDER,
            0,
            1,
            "第四章  招标需求",
            "第五章  评标方法与程序",
        ),
    ],
)
def test_build_initial_state_uses_gngk_mode_specific_default_anchors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    form_type: FormType,
    tender_lx: int,
    fund_source_lx: int,
    expected_before: str,
    expected_after: str,
) -> None:
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    review_path = upload_path(tmp_path, "review.docx")
    template_path = upload_path(tmp_path, "template.docx")
    params_path = upload_path(tmp_path, "params.docx")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_dir))
    service = object.__new__(DocumentService)
    request = build_request(
        origin_tender=review_path,
        template=template_path,
        form_type=form_type,
        tender_lx=tender_lx,
        fund_source_lx=fund_source_lx,
    )
    request.file_paths["tender_params"] = [params_path]

    state = service._build_initial_state(request, task_id="task-gngk-defaults")

    assert state["insertion_before_text"] == expected_before
    assert state["insertion_after_text"] == expected_after


def test_edit_and_rewrite_initial_state_do_not_receive_generation_style(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    output_path = upload_path(tmp_path, "output.docx")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_dir))
    service = object.__new__(DocumentService)
    edit_request = EditTaskRequest(
        conversation_id="conv-1",
        form_type=FormType.XJCG_TENDER,
        model=LLMModel.DEEPSEEK,
        edit_prompt="请微调商务条款",
        file_path=output_path,
        tender_lx=0,
        fund_source_lx=1,
        tender_data_snapshot=TenderData(
            project_name="测试项目",
            project_number="XJ-001",
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
    )

    edit_state = service._build_edit_graph_initial_state(request=edit_request, task_id="task-4")
    rewrite_state = service._build_skill_graph_initial_state(
        task_id="task-5",
        skill_id="rewrite",
        conversation_id="conv-1",
        user_prompt="请重写技术要求",
    )

    assert "generation_style" not in edit_state
    assert "generation_style" not in rewrite_state


def test_build_initial_state_rejects_template_outside_upload_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    outside_path = tmp_path / "outside.docx"
    outside_path.write_bytes(b"doc")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_dir))
    service = object.__new__(DocumentService)
    request = build_request(
        origin_tender=None,
        template=str(outside_path),
    )
    request.file_paths["tender_params"] = []

    with pytest.raises(ValueError, match="file_paths.template"):
        service._build_initial_state(request, task_id="task-invalid-template")


def test_build_initial_state_rejects_tender_param_outside_upload_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    template_path = upload_path(tmp_path, "template.docx")
    outside_path = tmp_path / "outside-param.docx"
    outside_path.write_bytes(b"doc")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_dir))
    service = object.__new__(DocumentService)
    request = build_request(origin_tender=None, template=template_path)
    request.file_paths["tender_params"] = [str(outside_path)]

    with pytest.raises(ValueError, match=r"file_paths\.tender_params\[0\]"):
        service._build_initial_state(request, task_id="task-invalid-param")


def test_create_task_rejects_invalid_upload_path_before_submit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    outside_path = tmp_path / "outside.docx"
    outside_path.write_bytes(b"doc")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_dir))
    monkeypatch.setitem(document_service.GRAPH_REGISTRY, "gjgk_tender", object())

    service = object.__new__(DocumentService)
    service._allocate_task_callback_pair = lambda: ("task-invalid", object())
    service._submit_graph_task = lambda **_kwargs: pytest.fail("should not submit task")
    request = build_request(origin_tender=None, template=str(outside_path))
    request.file_paths["tender_params"] = []

    response = service.create_task(request)

    assert response.success is False
    assert response.error == document_service.UPLOAD_PATH_ERROR_CODE
    assert "file_paths.template" in response.message


@pytest.mark.asyncio
async def test_create_edit_task_rejects_invalid_request_file_path_before_submit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    outside_path = tmp_path / "outside-edit.docx"
    outside_path.write_bytes(b"doc")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_dir))
    monkeypatch.setattr(document_service, "EDIT_SKILL_GRAPH_CLASS", object())

    service = object.__new__(DocumentService)
    service._conversation_service = object()
    service._allocate_task_callback_pair = lambda: ("task-edit-invalid", object())
    service._submit_graph_task = lambda **_kwargs: pytest.fail("should not submit task")
    edit_request = EditTaskRequest(
        conversation_id="conv-invalid-edit",
        form_type=FormType.XJCG_TENDER,
        model=LLMModel.DEEPSEEK,
        edit_prompt="请修改",
        file_path=str(outside_path),
        tender_lx=0,
        fund_source_lx=1,
    )

    response = await service.create_edit_task(edit_request)

    assert response.success is False
    assert response.error == document_service.UPLOAD_PATH_ERROR_CODE
    assert "file_path" in response.message


@pytest.mark.asyncio
async def test_create_edit_task_rejects_invalid_conversation_prepared_doc_before_submit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    outside_path = tmp_path / "outside-history.docx"
    outside_path.write_bytes(b"doc")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_dir))
    monkeypatch.setattr(document_service, "EDIT_SKILL_GRAPH_CLASS", object())

    service = object.__new__(DocumentService)
    service._conversation_service = type(
        "FakeConversationService",
        (),
        {
            "get_latest_rewrite_state": lambda self, conversation_id: {
                "prepared_doc_path": str(outside_path)
            }
        },
    )()
    service._allocate_task_callback_pair = lambda: ("task-edit-history-invalid", object())
    service._submit_graph_task = lambda **_kwargs: pytest.fail("should not submit task")
    edit_request = EditTaskRequest(
        conversation_id="conv-invalid-history",
        form_type=FormType.XJCG_TENDER,
        model=LLMModel.DEEPSEEK,
        edit_prompt="请修改",
        file_path=None,
        tender_lx=0,
        fund_source_lx=1,
    )

    response = await service.create_edit_task(edit_request)

    assert response.success is False
    assert response.error == document_service.UPLOAD_PATH_ERROR_CODE
    assert "prepared_doc_path" in response.message
