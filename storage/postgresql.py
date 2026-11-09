import csv
import io
import logging
import subprocess
from typing import List, Sequence

from process.extract_transforme import AuthEvent

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS auth_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_time TIMESTAMPTZ NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('accepted', 'failed')),
    username TEXT NOT NULL,
    ip_address INET NOT NULL,
    country TEXT NOT NULL,
    invalid_user BOOLEAN NOT NULL,
    source_file TEXT NOT NULL,
    line_number INTEGER NOT NULL,
    occurrence INTEGER NOT NULL,
    UNIQUE (source_file, line_number, occurrence)
);
"""

METRIC_QUERIES = {
    "failed_by_country": """
        SELECT country AS label, COUNT(*) AS count
        FROM auth_events WHERE event_type = 'failed'
        GROUP BY country ORDER BY count DESC, label
    """,
    "successful_by_user": """
        SELECT username AS label, COUNT(*) AS count
        FROM auth_events WHERE event_type = 'accepted'
        GROUP BY username ORDER BY count DESC, label
    """,
    "invalid_user_failures": """
        SELECT username AS label, COUNT(*) AS count
        FROM auth_events
        WHERE event_type = 'failed' AND invalid_user
        GROUP BY username ORDER BY count DESC, label
    """,
}


def _run_psql(arguments: Sequence[str], input_text: str = "") -> str:
    try:
        result = subprocess.run(
            ["psql", "--no-psqlrc", "--set", "ON_ERROR_STOP=1"] + list(arguments),
            input=input_text,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
    except OSError:
        logger.exception("Unable to start psql; install PostgreSQL client tools and add psql to PATH")
        raise

    if result.returncode != 0:
        logger.error("psql failed with exit code %d: %s", result.returncode, result.stderr.strip())
        raise RuntimeError("PostgreSQL command failed: {}".format(result.stderr.strip()))
    return result.stdout


def save_events(events: List[AuthEvent]) -> int:
    """Create the table and idempotently import events through psql's CSV COPY."""
    script = [
        "BEGIN;",
        SCHEMA_SQL,
        """
        CREATE TEMP TABLE auth_events_stage (
            event_time TIMESTAMPTZ NOT NULL,
            event_type TEXT NOT NULL,
            username TEXT NOT NULL,
            ip_address INET NOT NULL,
            country TEXT NOT NULL,
            invalid_user BOOLEAN NOT NULL,
            source_file TEXT NOT NULL,
            line_number INTEGER NOT NULL,
            occurrence INTEGER NOT NULL
        ) ON COMMIT DROP;
        """,
        """
        COPY auth_events_stage
            (event_time, event_type, username, ip_address, country,
             invalid_user, source_file, line_number, occurrence)
        FROM STDIN WITH (FORMAT CSV);
        """,
    ]
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    for event in events:
        writer.writerow(
            [
                event.event_time.isoformat(),
                event.event_type,
                event.username,
                event.ip_address,
                event.country,
                str(event.invalid_user).lower(),
                event.source_file,
                event.line_number,
                event.occurrence,
            ]
        )
    script.append(output.getvalue())
    script.extend(
        [
            r"\.",
            """
            INSERT INTO auth_events
                (event_time, event_type, username, ip_address, country,
                 invalid_user, source_file, line_number, occurrence)
            SELECT event_time, event_type, username, ip_address, country,
                   invalid_user, source_file, line_number, occurrence
            FROM auth_events_stage
            ON CONFLICT (source_file, line_number, occurrence) DO NOTHING;
            """,
            "COMMIT;",
        ]
    )
    _run_psql([], "\n".join(script))
    logger.info("Imported %d authentication events", len(events))
    return len(events)


def fetch_metric(query_name: str) -> List[dict]:
    try:
        query = METRIC_QUERIES[query_name]
    except KeyError:
        logger.exception("Unknown dashboard metric: %s", query_name)
        raise

    output = _run_psql(["--quiet", "--csv", "--command", query])
    try:
        return [
            {"label": row["label"], "count": int(row["count"])}
            for row in csv.DictReader(io.StringIO(output))
        ]
    except (KeyError, TypeError, ValueError, csv.Error):
        logger.exception("Unable to parse PostgreSQL metric output for %s", query_name)
        raise
