from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.config.tender_config import get_default_anchor_texts
from backend.models.generate import (
    EditTaskRequest,
    FormType,
    GenerateRequest,
    GenerationMode,
    GenerationStyle,
    LLMModel,
    StyleWritebackMode,
)
from backend.models.tender import TenderData
from backend.services.document_service import (
    DocumentService,
    REWRITE_DEFAULT_ANCHORS,
    REWRITE_STATE_KEYS,
)


def build_request(
    *,
    template: str | None,
    tender_params: list[str] | None = None,
    form_type: FormType = FormType.GJGK_TENDER,
    tender_lx: int = 0,
    fund_source_lx: int = 1,
    generation_mode: GenerationMode = GenerationMode.WORKFLOW,
    generation_style: GenerationStyle = GenerationStyle.TEMPLATE,
    style_writeback_mode: StyleWritebackMode = StyleWritebackMode.FULL,
    investment: str = "140",
) -> GenerateRequest:
    file_paths: dict[str, object] = {
        "tender_params": tender_params or ["D:/UploadFiles/params.docx"]
    }
    if template is not None:
        file_paths["template"] = template

    return GenerateRequest(
        form_type=form_type,
        tender_data=TenderData(
            project_name="国际公开测试项目",
            project_number="0811-254DSITC2512",
            project_content="采购内容",
            buyer_name="采购人",
            investment=investment,
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
        generation_mode=generation_mode,
        generation_style=generation_style,
        style_writeback_mode=style_writeback_mode,
        model=LLMModel.DEEPSEEK,
    )


def test_generate_request_requires_template_path() -> None:
    with pytest.raises(ValidationError, match="请上传模板文件"):
        build_request(template=None)


def test_build_initial_state_uses_template_and_tender_params_only() -> None:
    service = object.__new__(DocumentService)
    request = build_request(
        template=" D:/UploadFiles/template.docx ",
        tender_params=[
            "D:/UploadFiles/params1.docx",
            "D:/UploadFiles/params2.docx",
        ],
    )

    state = service._build_initial_state(request, task_id="task-1")

    assert state["template_path"] == "D:/UploadFiles/template.docx"
    assert state["tender_param_paths"] == [
        "D:/UploadFiles/params1.docx",
        "D:/UploadFiles/params2.docx",
    ]
    assert "origin_tender_path" not in state
    assert "clean_draft_path" not in state
    assert "source_origin_tender_path" not in state
    assert state["project_number"] == "254DSITC2512"
    assert "254DSITC2512" in state["tender_invitation"]


def test_build_initial_state_carries_generation_style() -> None:
    service = object.__new__(DocumentService)
    request = build_request(
        template="D:/UploadFiles/template.docx",
        generation_style=GenerationStyle.PARAM,
    )

    state = service._build_initial_state(request, task_id="task-3")

    assert state["generation_style"] == "param"


def test_build_initial_state_carries_generation_mode() -> None:
    service = object.__new__(DocumentService)
    request = build_request(
        template="D:/UploadFiles/template.docx",
        generation_mode=GenerationMode.AGENT,
    )

    state = service._build_initial_state(request, task_id="task-3a")

    assert state["generation_mode"] == "agent"


def test_build_initial_state_carries_style_writeback_mode() -> None:
    service = object.__new__(DocumentService)
    request = build_request(
        template="D:/UploadFiles/template.docx",
        style_writeback_mode=StyleWritebackMode.BOLD_ONLY,
    )

    state = service._build_initial_state(request, task_id="task-3b")

    assert state["style_writeback_mode"] == "bold_only"


def test_build_initial_state_carries_investment_and_rewrite_snapshot_key() -> None:
    service = object.__new__(DocumentService)
    request = build_request(
        template="D:/UploadFiles/template.docx",
        investment="140.0",
    )

    state = service._build_initial_state(request, task_id="task-investment")

    assert state["investment"] == "140.0"
    assert "investment" in REWRITE_STATE_KEYS


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
            FormType.GNGK_FW_ZC_TENDER,
            2,
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
            FormType.GNGK_FW_CZ_TENDER,
            2,
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
    form_type: FormType,
    tender_lx: int,
    fund_source_lx: int,
    expected_before: str,
    expected_after: str,
) -> None:
    service = object.__new__(DocumentService)
    request = build_request(
        template="D:/UploadFiles/template.docx",
        form_type=form_type,
        tender_lx=tender_lx,
        fund_source_lx=fund_source_lx,
    )

    state = service._build_initial_state(request, task_id="task-gngk-defaults")

    assert state["insertion_before_text"] == expected_before
    assert state["insertion_after_text"] == expected_after
    assert state["tender_lx"] == tender_lx


def test_edit_and_rewrite_initial_state_do_not_receive_generation_style() -> None:
    service = object.__new__(DocumentService)
    edit_request = EditTaskRequest(
        conversation_id="conv-1",
        form_type=FormType.XJCG_TENDER,
        model=LLMModel.DEEPSEEK,
        edit_prompt="请微调商务条款",
        file_path="D:/UploadFiles/output.docx",
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
    assert "generation_mode" not in edit_state
    assert "generation_mode" not in rewrite_state
