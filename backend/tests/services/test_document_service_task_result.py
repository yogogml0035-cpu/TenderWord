from __future__ import annotations

from pathlib import Path

from backend.services.document_service import DocumentService


def test_build_task_result_payload_includes_style_writeback(tmp_path: Path) -> None:
    output_path = tmp_path / "styled-output.docx"
    output_path.write_bytes(b"word")

    service = DocumentService.__new__(DocumentService)
    payload = service._build_task_result_payload(
        result_state={
            "prepared_doc_path": str(output_path),
            "style_writeback_summary": "样式回填: 抽取=2, 尝试=2, 成功=1, 跳过=1, 失败=0",
            "style_writeback_result": {
                "extracted": 2,
                "attempted": 2,
                "applied": 1,
                "skipped": 1,
                "failed": 0,
                "issues": [],
                "applied_by_style": {"bold": 1},
                "skipped_by_reason": {"low_confidence": 1},
            },
        },
        initial_state={},
        elapsed_time=12.3456,
        model_provider="deepseek",
    )

    assert payload["output_file"] == str(output_path)
    assert payload["file_name"] == "styled-output.docx"
    assert payload["file_size"] == 4
    assert payload["model_used"] == "deepseek"
    assert payload["total_time_seconds"] == 12.346
    assert payload["style_writeback"] == {
        "summary": "样式回填: 抽取=2, 尝试=2, 成功=1, 跳过=1, 失败=0",
        "extracted": 2,
        "attempted": 2,
        "applied": 1,
        "skipped": 1,
        "failed": 0,
        "applied_by_style": {"bold": 1},
        "skipped_by_reason": {"low_confidence": 1},
    }
