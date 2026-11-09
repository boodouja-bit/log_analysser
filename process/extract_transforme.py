import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)

TIMESTAMP_PATTERN = re.compile(
    r"^([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})"
)
AUTH_PATTERN = re.compile(
    r"\b(Accepted|Failed) (?:password|publickey) for "
    r"(?:(invalid user)\s+)?(\S+)\s+from\s+"
    r"([0-9A-Fa-f:.]+)\s+port\s+\d+"
)
REPEATED_PATTERN = re.compile(
    r"message repeated (\d+) times:\s*\[\s*(.*?)\s*\]\s*$"
)


@dataclass(frozen=True)
class AuthEvent:
    event_time: datetime
    event_type: str
    username: str
    ip_address: str
    invalid_user: bool
    source_file: str
    line_number: int
    occurrence: int
    country: str = "Unknown"


def extract_from_row(
    row: str,
    year: Optional[int] = None,
    source_file: str = "<memory>",
    line_number: int = 1,
) -> List[AuthEvent]:
    """Extract successful and failed SSH password/public-key authentications."""
    timestamp_match = TIMESTAMP_PATTERN.search(row)
    if not timestamp_match:
        return []

    message = row
    occurrences = 1
    repeated_match = REPEATED_PATTERN.search(row)
    if repeated_match:
        occurrences = int(repeated_match.group(1))
        message = repeated_match.group(2)

    auth_match = AUTH_PATTERN.search(message)
    if not auth_match:
        return []

    try:
        event_year = (
            year
            if year is not None
            else int(os.environ.get("LOG_YEAR", datetime.now().year))
        )
        parsed_time = datetime.strptime(
            "{} {}".format(event_year, timestamp_match.group(1)),
            "%Y %b %d %H:%M:%S",
        ).replace(tzinfo=timezone.utc)
        event_time = parsed_time
    except (ValueError, TypeError):
        logger.exception(
            "Invalid timestamp or LOG_YEAR at %s:%d", source_file, line_number
        )
        raise

    try:
        event_type = auth_match.group(1).lower()
        username = auth_match.group(3)
        ip_address = auth_match.group(4)
        invalid_user = auth_match.group(2) is not None
        return [
            AuthEvent(
                event_time=event_time,
                event_type=event_type,
                username=username,
                ip_address=ip_address,
                invalid_user=invalid_user,
                source_file=source_file,
                line_number=line_number,
                occurrence=occurrence,
            )
            for occurrence in range(1, occurrences + 1)
        ]
    except (ValueError, OverflowError):
        logger.exception(
            "Unable to extract authentication event at %s:%d",
            source_file,
            line_number,
        )
        raise
