import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from process.extract_transforme import extract_from_row
from process.geolocation import CountryLookup, enrich_events
from serving.dashboard import create_dashboard
from storage.postgresql import fetch_metric, save_events


class AuthenticationParserTests(unittest.TestCase):
    def test_failed_attempt_with_invalid_user(self):
        events = extract_from_row(
            "May 24 00:28:00 host sshd[1]: Failed password for invalid user "
            "test from 45.156.87.204 port 41740 ssh2",
            year=2026,
            source_file="auth.log.1",
            line_number=12,
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "failed")
        self.assertEqual(events[0].username, "test")
        self.assertTrue(events[0].invalid_user)
        self.assertEqual(events[0].line_number, 12)

    def test_successful_attempt(self):
        events = extract_from_row(
            "May 24 01:00:00 host sshd[2]: Accepted publickey for alice "
            "from 192.0.2.4 port 22 ssh2",
            year=2026,
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "accepted")
        self.assertEqual(events[0].username, "alice")
        self.assertFalse(events[0].invalid_user)

    def test_repeated_message_expands_to_attempt_count(self):
        events = extract_from_row(
            "May 24 01:00:00 host sshd[3]: message repeated 3 times: "
            "[ Failed password for root from 192.0.2.5 port 22 ssh2 ]",
            year=2026,
        )

        self.assertEqual([event.occurrence for event in events], [1, 2, 3])

    def test_country_lookup_matches_network(self):
        with tempfile.TemporaryDirectory() as directory:
            mapping_path = Path(directory) / "countries.csv"
            with mapping_path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["network", "country"])
                writer.writerow(["192.0.2.0/24", "Example"])
            lookup = CountryLookup(str(mapping_path))

            events = extract_from_row(
                "May 24 01:00:00 host sshd[4]: Failed password for root "
                "from 192.0.2.5 port 22 ssh2",
                year=2026,
            )
            enriched = enrich_events(events, lookup)

        self.assertEqual(enriched[0].country, "Example")
        self.assertEqual(lookup.get_location("198.51.100.1"), "Unknown")

    def test_non_authentication_line_is_ignored(self):
        self.assertEqual(
            extract_from_row("May 24 00:09:01 host CRON: session opened"), []
        )

    @patch("storage.postgresql._run_psql")
    def test_postgresql_import_uses_copy_and_is_repeatable(self, run_psql):
        events = extract_from_row(
            "May 24 01:00:00 host sshd[5]: Failed password for invalid user "
            "test from 192.0.2.5 port 22 ssh2",
            year=2026,
            source_file="auth.log",
            line_number=7,
        )

        self.assertEqual(save_events(events), 1)
        script = run_psql.call_args.args[1]
        self.assertIn("COPY auth_events_stage", script)
        self.assertIn("ON CONFLICT (source_file, line_number, occurrence) DO NOTHING", script)
        self.assertIn("test,192.0.2.5,Unknown,true,auth.log,7,1", script)

    @patch("storage.postgresql._run_psql")
    def test_fetch_metric_parses_csv_output(self, run_psql):
        run_psql.return_value = 'label,count\n"France",4\n'

        self.assertEqual(
            fetch_metric("failed_by_country"),
            [{"label": "France", "count": 4}],
        )

    @patch("serving.dashboard.fetch_metric")
    def test_dashboard_writes_image(self, fetch):
        fetch.side_effect = [
            [{"label": "France", "count": 3}],
            [{"label": "alice", "count": 1}],
            [{"label": "unknown", "count": 2}],
        ]
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "reports" / "dashboard.png"

            result = create_dashboard(str(output_path))

            self.assertEqual(result, output_path)
            self.assertGreater(output_path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
