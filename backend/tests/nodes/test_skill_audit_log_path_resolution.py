from __future__ import annotations

from backend.nodes.skills_nodes.rewrite_nodes import _get_rewrite_log_path
from backend.util.log_util.skill_audit_log import resolve_task_audit_log_path


def test_resolve_task_audit_log_path_prefers_neutral_alias():
    config = {
        "configurable": {
            "task_audit_log_path": "/tmp/task-audit.json",
            "rewrite_log_path": "/tmp/legacy-rewrite.json",
        }
    }

    assert resolve_task_audit_log_path(config) == "/tmp/task-audit.json"
    assert _get_rewrite_log_path(config) == "/tmp/task-audit.json"


def test_resolve_task_audit_log_path_falls_back_to_legacy_key():
    config = {
        "configurable": {
            "rewrite_log_path": "/tmp/legacy-rewrite.json",
        }
    }

    assert resolve_task_audit_log_path(config) == "/tmp/legacy-rewrite.json"
    assert _get_rewrite_log_path(config) == "/tmp/legacy-rewrite.json"


def test_resolve_task_audit_log_path_returns_empty_string_without_any_key():
    config = {"configurable": {}}

    assert resolve_task_audit_log_path(config) == ""
    assert _get_rewrite_log_path(config) == ""
