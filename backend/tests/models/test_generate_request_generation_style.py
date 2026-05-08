from __future__ import annotations

from backend.models.generate import GenerateRequest, GenerationStyle, StyleWritebackMode
from backend.models.tender import TenderData


def build_payload() -> dict[str, object]:
    return {
        "form_type": "xjcg_tender",
        "tender_data": TenderData(
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
        "file_paths": {"tender_params": ["D:/UploadFiles/params.docx"]},
        "model": "deepseek",
    }


def test_generate_request_defaults_generation_style_to_template() -> None:
    request = GenerateRequest(**build_payload())

    assert request.generation_style == GenerationStyle.TEMPLATE


def test_generate_request_accepts_param_generation_style() -> None:
    request = GenerateRequest(**{**build_payload(), "generation_style": "param"})

    assert request.generation_style == GenerationStyle.PARAM


def test_generate_request_defaults_style_writeback_mode_to_full() -> None:
    request = GenerateRequest(**build_payload())

    assert request.style_writeback_mode == StyleWritebackMode.FULL


def test_generate_request_accepts_bold_only_style_writeback_mode() -> None:
    request = GenerateRequest(**{**build_payload(), "style_writeback_mode": "bold_only"})

    assert request.style_writeback_mode == StyleWritebackMode.BOLD_ONLY
