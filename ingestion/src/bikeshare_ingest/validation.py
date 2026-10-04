"""File-level checks run before anything is written to bronze.

A payload that fails goes to quarantine/ instead, so one broken response can never
make bronze unreadable for Athena.
"""

import json
from typing import Any


def validate_gbfs(body: bytes, expected_version: str) -> tuple[dict[str, Any] | None, list[str]]:
    """Return (parsed document, list of problems). An empty list means valid."""
    try:
        doc = json.loads(body)
    except (ValueError, UnicodeDecodeError) as exc:
        return None, [f"invalid JSON: {exc}"]

    if not isinstance(doc, dict):
        return None, ["top-level JSON is not an object"]

    errors: list[str] = []
    if not isinstance(doc.get("last_updated"), int):
        errors.append("missing or non-integer last_updated")

    version = doc.get("version")
    if str(version) != expected_version:
        errors.append(f"version {version!r} != expected {expected_version!r}")

    data = doc.get("data")
    stations = data.get("stations") if isinstance(data, dict) else None
    if not isinstance(stations, list) or not stations:
        errors.append("data.stations missing or empty")
    elif not all(isinstance(s, dict) and s.get("station_id") for s in stations):
        errors.append("at least one station has no station_id")

    return doc, errors
