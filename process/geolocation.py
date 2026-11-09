import csv
import ipaddress
import logging
from pathlib import Path
from typing import List, Tuple, Union

from process.extract_transforme import AuthEvent

logger = logging.getLogger(__name__)

IPNetwork = Union[ipaddress.IPv4Network, ipaddress.IPv6Network]


class CountryLookup:
    def __init__(self, mapping_path: str) -> None:
        self._networks: List[Tuple[int, IPNetwork, str]] = []
        path = Path(mapping_path)
        if not path.exists():
            logger.warning("Country mapping file not found: %s", path)
            return

        try:
            with path.open("r", encoding="utf-8", newline="") as stream:
                for row_number, row in enumerate(csv.DictReader(stream), start=2):
                    try:
                        network = ipaddress.ip_network(row["network"].strip(), strict=False)
                        country = row["country"].strip()
                        if not country:
                            raise ValueError("country must not be empty")
                        self._networks.append((network.prefixlen, network, country))
                    except (KeyError, ValueError, AttributeError):
                        logger.exception(
                            "Invalid country mapping at %s:%d", path, row_number
                        )
                        raise
        except (OSError, UnicodeError, csv.Error):
            logger.exception("Unable to read country mapping file %s", path)
            raise

        self._networks.sort(key=lambda item: item[0], reverse=True)

    def get_location(self, ip: str) -> str:
        try:
            address = ipaddress.ip_address(ip)
        except ValueError:
            logger.exception("Invalid IP address: %s", ip)
            raise

        for _prefix_length, network, country in self._networks:
            if address.version == network.version and address in network:
                return country
        return "Unknown"


def enrich_events(events: List[AuthEvent], lookup: CountryLookup) -> List[AuthEvent]:
    return [
        AuthEvent(
            event_time=event.event_time,
            event_type=event.event_type,
            username=event.username,
            ip_address=event.ip_address,
            invalid_user=event.invalid_user,
            source_file=event.source_file,
            line_number=event.line_number,
            occurrence=event.occurrence,
            country=lookup.get_location(event.ip_address),
        )
        for event in events
    ]
