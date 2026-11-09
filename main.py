import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ingestion.raw import read_log_files
from process.extract_transforme import extract_from_row
from process.geolocation import CountryLookup, enrich_events
from serving.dashboard import create_dashboard
from storage.postgresql import save_events


def configure_logging(project_dir: Path) -> None:
    log_path = project_dir / "logs" / "application.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[
            RotatingFileHandler(
                str(log_path), maxBytes=5_000_000, backupCount=3, encoding="utf-8"
            ),
            logging.StreamHandler(),
        ],
        force=True,
    )

    def log_uncaught_exception(exception_type, exception, traceback) -> None:
        if issubclass(exception_type, KeyboardInterrupt):
            sys.__excepthook__(exception_type, exception, traceback)
            return
        logging.getLogger(__name__).critical(
            "Uncaught application error",
            exc_info=(exception_type, exception, traceback),
        )

    sys.excepthook = log_uncaught_exception


def main() -> None:
    project_dir = Path(__file__).resolve().parent
    configure_logging(project_dir)
    logger = logging.getLogger(__name__)

    log_directory = Path(os.environ.get("LOG_INPUT_DIR", str(project_dir / "data")))
    country_file = Path(
        os.environ.get(
            "LOG_COUNTRY_FILE", str(project_dir / "data" / "ip_country.csv")
        )
    )
    dashboard_path = os.environ.get(
        "LOG_DASHBOARD_PATH", str(project_dir / "reports" / "dashboard.png")
    )

    lookup = CountryLookup(str(country_file))
    events = []
    for source_file, line_number, row in read_log_files(str(log_directory)):
        events.extend(
            extract_from_row(row, source_file=source_file, line_number=line_number)
        )
    events = enrich_events(events, lookup)
    imported_count = save_events(events)
    dashboard = create_dashboard(dashboard_path)
    logger.info(
        "Pipeline complete: %d parsed event(s), dashboard: %s",
        imported_count,
        dashboard,
    )


if __name__ == "__main__":
    main()
