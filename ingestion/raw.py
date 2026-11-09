import gzip
import logging
from pathlib import Path
from typing import Iterator, List, Tuple

logger = logging.getLogger(__name__)


def read_log_files(path: str) -> Iterator[Tuple[str, int, str]]:
    """Yield each log line together with its source file and 1-based line number."""
    directory = Path(path)
    if not directory.is_dir():
        raise FileNotFoundError("Log directory does not exist: {}".format(directory))

    files = sorted(
        file_path
        for file_path in directory.iterdir()
        if file_path.is_file() and ".log" in file_path.name
    )
    for file_path in files:
        opener = gzip.open if file_path.suffix == ".gz" else open
        try:
            with opener(file_path, "rt", encoding="utf-8", errors="replace") as stream:
                for line_number, row in enumerate(stream, start=1):
                    yield file_path.name, line_number, row.rstrip("\r\n")
        except (OSError, EOFError, UnicodeError):
            logger.exception("Unable to read log file %s", file_path)
            raise


def toRows(path: str) -> List[str]:
    """Return all log lines; kept for compatibility with the original module."""
    return [row for _source, _line_number, row in read_log_files(path)]
