from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.models.generate import (
    GenerateFilePaths,
    GenerateRequest,
    TenderParamFile,
)
from backend.models.tender import TenderData


def _tender_data() -> TenderData:
    return TenderData(
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
    )


def test_generate_file_paths_accepts_legacy_string_list() -> None:
    paths = GenerateFilePaths(
        template="D:/UploadFiles/template.docx",
        tender_params=["D:/UploadFiles/params1.docx", "D:/UploadFiles/params2.docx"],
    )

    assert paths.template == "D:/UploadFiles/template.docx"
    assert paths.tender_params == [
        "D:/UploadFiles/params1.docx",
        "D:/UploadFiles/params2.docx",
    ]


def test_generate_file_paths_accepts_object_form_with_original_name() -> None:
    paths = GenerateFilePaths(
        template="D:/UploadFiles/template.docx",
        tender_params=[
            {"file_path": "D:/UploadFiles/uuid-1.docx", "original_name": "第一包技术参数.docx"},
            {"file_path": "D:/UploadFiles/uuid-2.docx", "original_name": "第二包技术参数.docx"},
        ],
    )

    assert paths.tender_params == [
        TenderParamFile(
            file_path="D:/UploadFiles/uuid-1.docx",
            original_name="第一包技术参数.docx",
        ),
        TenderParamFile(
            file_path="D:/UploadFiles/uuid-2.docx",
            original_name="第二包技术参数.docx",
        ),
    ]


def test_generate_file_paths_accepts_object_form_without_original_name() -> None:
    paths = GenerateFilePaths(
        template="D:/UploadFiles/template.docx",
        tender_params=[{"file_path": "D:/UploadFiles/uuid-1.docx"}],
    )

    assert paths.tender_params == [
        TenderParamFile(file_path="D:/UploadFiles/uuid-1.docx", original_name=None),
    ]


def test_generate_file_paths_accepts_mixed_string_and_object_forms() -> None:
    paths = GenerateFilePaths(
        template="D:/UploadFiles/template.docx",
        tender_params=[
            "D:/UploadFiles/params1.docx",
            {"file_path": "D:/UploadFiles/uuid-2.docx", "original_name": "第二包.docx"},
        ],
    )

    assert paths.tender_params[0] == "D:/UploadFiles/params1.docx"
    assert isinstance(paths.tender_params[1], TenderParamFile)
    assert paths.tender_params[1].file_path == "D:/UploadFiles/uuid-2.docx"
    assert paths.tender_params[1].original_name == "第二包.docx"


def test_generate_file_paths_rejects_empty_object_file_path() -> None:
    with pytest.raises(ValidationError, match="技术参数文件路径不能为空"):
        GenerateFilePaths(
            template="D:/UploadFiles/template.docx",
            tender_params=[{"file_path": "   ", "original_name": "x.docx"}],
        )


def test_generate_request_accepts_object_form_tender_params() -> None:
    request = GenerateRequest(
        form_type="xjcg_tender",
        tender_data=_tender_data(),
        file_paths={
            "template": "D:/UploadFiles/template.docx",
            "tender_params": [
                {"file_path": "D:/UploadFiles/uuid-1.docx", "original_name": "第一包.docx"},
            ],
        },
        model="deepseek",
    )

    assert request.file_paths.tender_params == [
        TenderParamFile(
            file_path="D:/UploadFiles/uuid-1.docx",
            original_name="第一包.docx",
        ),
    ]


def test_generate_request_accepts_legacy_string_tender_params() -> None:
    request = GenerateRequest(
        form_type="xjcg_tender",
        tender_data=_tender_data(),
        file_paths={
            "template": "D:/UploadFiles/template.docx",
            "tender_params": ["D:/UploadFiles/params.docx"],
        },
        model="deepseek",
    )

    assert request.file_paths.tender_params == ["D:/UploadFiles/params.docx"]
