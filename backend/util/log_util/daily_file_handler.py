"""Daily file handler with date-based filenames.

This handler writes logs directly into files named like ``prefix-YYYYMMDD.log``.
When the date changes, it switches to the new day's file without adding a second
rotation suffix.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional


class DailyFileHandler(logging.FileHandler):
    """A file handler that rolls over by switching to a new dated filename."""

    def __init__(
        self,
        log_dir: Path,
        prefix: str,
        backup_count: int,
        encoding: Optional[str] = None,
        delay: bool = False,
        now_provider: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self.log_dir = log_dir
        self.prefix = prefix
        self.backup_count = backup_count
        self._now_provider = now_provider or datetime.now
        self._current_date = self._get_date_str()
        filename = self._build_filename(self._current_date)
        super().__init__(filename=str(filename), mode="a", encoding=encoding, delay=delay)
        self._prune_old_files()

    def emit(self, record: logging.LogRecord) -> None:
        self._switch_file_if_needed()
        super().emit(record)

    def _get_date_str(self) -> str:
        return self._now_provider().strftime("%Y%m%d")

    def _build_filename(self, date_str: str) -> Path:
        return self.log_dir / f"{self.prefix}-{date_str}.log"

    def _switch_file_if_needed(self) -> None:
        next_date = self._get_date_str()
        if next_date == self._current_date:
            return

        self.acquire()
        try:
            next_date = self._get_date_str()
            if next_date == self._current_date:
                return

            if self.stream:
                self.stream.flush()
                self.stream.close()
                self.stream = None

            self._current_date = next_date
            self.baseFilename = str(self._build_filename(next_date))
            self._prune_old_files()
        finally:
            self.release()

    def _prune_old_files(self) -> None:
        if self.backup_count <= 0:
            return

        current_path = self._build_filename(self._current_date)
        current_file = current_path.name
        log_files = list(self.log_dir.glob(f"{self.prefix}-*.log"))
        if all(path.name != current_file for path in log_files):
            log_files.append(current_path)
        log_files.sort(key=lambda path: path.name)
        keep_count = self.backup_count + 1

        if len(log_files) <= keep_count:
            return

        removable = [
            path
            for path in log_files[:-keep_count]
            if path.name != current_file and path.exists()
        ]
        for path in removable:
            try:
                path.unlink()
            except OSError:
                continue
