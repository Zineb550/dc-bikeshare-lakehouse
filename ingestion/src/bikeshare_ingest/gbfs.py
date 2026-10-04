"""GBFS collector: one station_status snapshot per 15-minute slot, station_information hourly.

Outcomes per feed:
- valid payload   -> bronze/, run log status "ok"
- invalid payload -> quarantine/ + SNS alert, status "quarantined" (no retry: it would not help)
- fetch failure   -> status "failed", then raise so Lambda retries and the error alarm fires
"""

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from . import alerts, http, keys, storage
from .config import Settings
from .runlog import RunRecord, write_run_log
from .validation import validate_gbfs

logger = logging.getLogger(__name__)

STATUS_FEED = "station_status"
INFO_FEED = "station_information"


def feeds_for_slot(slot: datetime, force_info: bool = False) -> list[str]:
    """Status every slot; station information on the :00 slot only."""
    return [STATUS_FEED, INFO_FEED] if (slot.minute == 0 or force_info) else [STATUS_FEED]


def run(
    event: dict,
    *,
    settings: Settings,
    s3: Any,
    sns: Any,
    fetch: Callable[[str], bytes] = http.fetch,
    now: datetime | None = None,
) -> dict:
    slot = keys.slot_from_event(event, now)
    mode = event.get("mode", "manual")
    run_id = f"gbfs-{slot:%Y%m%dT%H%M}"
    records: list[RunRecord] = []
    failed: list[str] = []

    for feed in feeds_for_slot(slot, bool(event.get("force_info"))):
        started = time.monotonic()
        started_at = datetime.now(UTC).isoformat()
        status, rows, size, key, error = "ok", 0, 0, None, None
        try:
            body = fetch(f"{settings.gbfs_base_url}/{feed}.json")
            doc, problems = validate_gbfs(body, settings.expected_gbfs_version)
            if problems:
                status, error = "quarantined", "; ".join(problems)
                key = keys.gbfs_key("quarantine", feed, slot)
                size = storage.put_gzip_bytes(s3, settings.lake_bucket, key, body)
                alerts.publish(
                    sns,
                    settings.alerts_topic_arn,
                    subject=f"[bikeshare] quarantined {feed} {slot:%Y-%m-%d %H:%M}Z",
                    message=f"Payload failed validation: {error}\nStored at s3://{settings.lake_bucket}/{key}",
                )
            else:
                key = keys.gbfs_key("bronze", feed, slot)
                size = storage.put_gzip_json(s3, settings.lake_bucket, key, doc)
                rows = len(doc["data"]["stations"])
        except Exception as exc:
            status, error = "failed", f"{type(exc).__name__}: {exc}"
            failed.append(feed)
            logger.exception("GBFS %s failed for slot %s", feed, slot.isoformat())

        records.append(
            RunRecord(
                run_id=run_id,
                source=f"gbfs_{feed}",
                mode=mode,
                period=slot.isoformat(),
                status=status,
                rows=rows,
                bytes=size,
                object_key=key,
                duration_ms=int((time.monotonic() - started) * 1000),
                error=error,
                started_at=started_at,
            )
        )
        logger.info("gbfs %s slot=%s status=%s rows=%d key=%s", feed, slot, status, rows, key)

    write_run_log(s3, settings.lake_bucket, records, dt=f"{slot:%Y-%m-%d}", name=run_id)

    if failed:
        raise RuntimeError(f"GBFS fetch failed for {failed} at slot {slot.isoformat()}")

    return {
        "slot": slot.isoformat(),
        "results": [{"feed": r.source, "status": r.status, "key": r.object_key} for r in records],
    }
