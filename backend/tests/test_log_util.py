import logging
from datetime import datetime
from unittest.mock import Mock

import backend.util.log_util.execution_log as execution_log_module
from backend.util.log_util.daily_file_handler import DailyFileHandler
from backend.util.log_util.log_cleanup import get_log_files


class FrozenClock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def now(self) -> datetime:
        return self.current


def test_daily_file_handler_switches_to_new_dated_file(tmp_path):
    clock = FrozenClock(datetime(2026, 3, 10, 10, 0, 0))
    handler = DailyFileHandler(
        log_dir=tmp_path,
        prefix="execution",
        backup_count=7,
        encoding="utf-8",
        delay=False,
        now_provider=clock.now,
    )
    logger = logging.getLogger("backend.tests.test_log_util.switch")
    logger.handlers = []
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    logger.info("day-one")
    clock.current = datetime(2026, 3, 11, 0, 1, 0)
    logger.info("day-two")

    handler.close()
    logger.handlers = []

    day_one_file = tmp_path / "execution-20260310.log"
    day_two_file = tmp_path / "execution-20260311.log"

    assert day_one_file.exists()
    assert day_two_file.exists()
    assert "day-one" in day_one_file.read_text(encoding="utf-8")
    assert "day-two" in day_two_file.read_text(encoding="utf-8")


def test_daily_file_handler_prunes_old_dated_files(tmp_path):
    clock = FrozenClock(datetime(2026, 3, 10, 10, 0, 0))
    handler = DailyFileHandler(
        log_dir=tmp_path,
        prefix="progress",
        backup_count=1,
        encoding="utf-8",
        delay=False,
        now_provider=clock.now,
    )
    logger = logging.getLogger("backend.tests.test_log_util.prune")
    logger.handlers = []
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    logger.info("day-one")
    clock.current = datetime(2026, 3, 11, 0, 1, 0)
    logger.info("day-two")
    clock.current = datetime(2026, 3, 12, 0, 1, 0)
    logger.info("day-three")

    handler.close()
    logger.handlers = []

    remaining_files = sorted(path.name for path in tmp_path.glob("progress-*.log"))

    assert remaining_files == ["progress-20260311.log", "progress-20260312.log"]


def test_get_log_files_includes_legacy_rotated_files(tmp_path):
    filenames = [
        "execution-20260306.log",
        "execution-20260306.log.2026-03-06",
        "progress-20260306.log",
        "progress-20260306.log.2026-03-06",
    ]
    for name in filenames:
        (tmp_path / name).write_text("log", encoding="utf-8")

    log_files = sorted(path.name for path in get_log_files(tmp_path))

    assert log_files == filenames


def test_log_generate_task_success_writes_fixed_audit_line(monkeypatch):
    mock_info = Mock()
    monkeypatch.setattr(execution_log_module._execution_logger, "info", mock_info)

    execution_log_module.log_generate_task_success(
        {
            "project_zbr_xbr": "徐旭东、任彧晟",
            "project_number": "253505",
            "project_name": "细胞电转仪",
        }
    )

    mock_info.assert_called_once_with(
        "徐旭东、任彧晟-253505-细胞电转仪结束生成，当前进入update_word"
    )


def test_log_generate_task_success_skips_incomplete_state(monkeypatch):
    mock_info = Mock()
    monkeypatch.setattr(execution_log_module._execution_logger, "info", mock_info)

    execution_log_module.log_generate_task_success(
        {
            "project_zbr_xbr": "徐旭东、任彧晟",
            "project_number": "253505",
            "project_name": "",
        }
    )

    mock_info.assert_not_called()
