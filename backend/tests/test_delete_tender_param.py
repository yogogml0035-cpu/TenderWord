import importlib

import pytest

from backend.graphs.base_graph import TaskCancelledException

delete_tender_param_module = importlib.import_module(
    "backend.nodes.common_word_nodes.delete_tender_param"
)


class _FakeSelection:
    def __init__(self):
        self.Start = 20

    def GoTo(self, *_args, **_kwargs):
        self.Start = 20


class _FakeWord:
    def __init__(self):
        self.Selection = _FakeSelection()
        self.ScreenUpdating = True


class _FakeContent:
    End = 1000


class _FakeDocument:
    def __init__(self):
        self.Content = _FakeContent()


class _CancelledQueue:
    @staticmethod
    def is_task_cancelled(_task_id: str) -> bool:
        return True


def test_delete_tender_param_checks_cancellation_inside_long_loop(monkeypatch):
    save_called = {"value": False}

    monkeypatch.setattr(
        delete_tender_param_module,
        "create_word_application",
        lambda **_kwargs: (_FakeWord(), False),
    )
    monkeypatch.setattr(
        delete_tender_param_module,
        "open_document_with_retry",
        lambda **_kwargs: _FakeDocument(),
    )
    monkeypatch.setattr(
        delete_tender_param_module,
        "unprotect_document",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        delete_tender_param_module,
        "find_anchor_range",
        lambda **_kwargs: (
            {"page": 1, "end": 10, "font": "宋体", "size": 18.0},
            {"page": 3, "start": 100, "end": 110, "font": "宋体", "size": 18.0},
        ),
    )
    monkeypatch.setattr(delete_tender_param_module, "close_word_application", lambda **_kwargs: None)
    monkeypatch.setattr(
        "backend.task.task_queue_manager.get_task_queue",
        lambda: _CancelledQueue(),
    )

    def mark_save(*_args, **_kwargs):
        save_called["value"] = True

    monkeypatch.setattr(delete_tender_param_module, "save_document_with_retry", mark_save)

    with pytest.raises(TaskCancelledException):
        delete_tender_param_module.delete_tender_param(
            {
                "prepared_doc_path": __file__,
                "insertion_before_text": "第三章 采购需求",
                "insertion_after_text": "第四章 响应文件有关格式",
                "tender_type": "xjcg",
            },
            config={"configurable": {"task_id": "task-1"}},
        )

    assert save_called["value"] is False
