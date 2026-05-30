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
                "skipped_by_reason": {"font_color_full_container_blocked": 1},
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
        "skipped_by_reason": {"font_color_full_container_blocked": 1},
    }


def test_build_task_result_payload_includes_comment_writeback_without_internal_plans(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "comment-output.docx"
    output_path.write_bytes(b"word")

    service = DocumentService.__new__(DocumentService)
    payload = service._build_task_result_payload(
        result_state={
            "prepared_doc_path": str(output_path),
            "comment_writeback_result": {
                "summary": "AI批注写入: 生成=2, 成功=1, 失败=1, 跳过=0",
                "generated": 2,
                "added": 1,
                "failed": 1,
                "skipped": 0,
                "warning": True,
                "issues": [{"reference_text": "锚点", "error": "未命中"}],
            },
            "comment_plan_detail": [{"content": "内部批注依据"}],
            "strikethrough_plan": [{"content": "内部删除线依据"}],
            "non_black_font_plan": [{"content": "内部非黑字体依据"}],
        },
        initial_state={},
        elapsed_time=1.25,
        model_provider="deepseek",
    )

    assert payload["comment_writeback"] == {
        "summary": "AI批注写入: 生成=2, 成功=1, 失败=1, 跳过=0",
        "generated": 2,
        "added": 1,
        "failed": 1,
        "skipped": 0,
        "warning": True,
    }
    assert "comment_plan_detail" not in payload
    assert "strikethrough_plan" not in payload
    assert "non_black_font_plan" not in payload


def test_build_rewrite_state_snapshot_keeps_generate_comment_context_internal_only() -> None:
    service = DocumentService.__new__(DocumentService)

    snapshot = service._build_rewrite_state_snapshot(
        result_state={
            "tender_type": "xjcg",
            "prepared_doc_path": "D:/UploadFiles/output.docx",
            "polished_text": "生成正文",
            "comment_plan_detail": [{"content": "审查依据"}],
            "strikethrough_plan": [{"content": "删除线依据"}],
            "non_black_font_plan": [{"content": "非黑字体依据"}],
        },
        initial_state={
            "generation_mode": "agent",
            "project_name": "测试项目",
            "project_number": "XJ-001",
        },
    )

    assert snapshot["generation_mode"] == "agent"
    assert snapshot["comment_plan_detail"] == [{"content": "审查依据"}]
    assert snapshot["strikethrough_plan"] == [{"content": "删除线依据"}]
    assert snapshot["non_black_font_plan"] == [{"content": "非黑字体依据"}]
