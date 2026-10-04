"""Deterministic S3 keys and time slots.

Keys derive from the scheduled slot, never the wall clock, so a retry of the same
slot overwrites its object instead of creating a duplicate.
"""

from datetime import UTC, datetime

SLOT_MINUTES = 15


def floor_to_slot(ts: datetime) -> datetime:
    """Round a timestamp down to its 15-minute slot, in UTC."""
    ts = ts.astimezone(UTC)
    return ts.replace(minute=ts.minute - ts.minute % SLOT_MINUTES, second=0, microsecond=0)


def slot_from_event(event: dict, now: datetime | None = None) -> datetime:
    """Slot from the Scheduler's `scheduled_time`, or from `now` for manual runs."""
    raw = event.get("scheduled_time")
    ts = datetime.fromisoformat(raw) if raw else (now or datetime.now(UTC))
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return floor_to_slot(ts)


def gbfs_key(layer: str, feed: str, slot: datetime) -> str:
    """e.g. bronze/gbfs/station_status/dt=2026-10-03/slot=0115.json.gz"""
    return f"{layer}/gbfs/{feed}/dt={slot:%Y-%m-%d}/slot={slot:%H%M}.json.gz"


def run_log_key(dt: str, name: str) -> str:
    return f"ops/run_log/dt={dt}/{name}.json"
