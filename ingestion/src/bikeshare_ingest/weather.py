"""Hourly weather for one point (DC centroid) from Open-Meteo.

Two modes, same output:
- forecast: Forecast API with past_days=7, no publication delay (daily runs)
- archive:  Archive API (ERA5) for an explicit date range (backfill)

One file per run date: bronze/weather/fetch_date=YYYY-MM-DD/<mode>.json.gz. Overlapping
windows are intentional; silver keeps the most recent value for each hour.
"""

import json
import logging
import time
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from . import alerts, http, storage
from .config import Settings
from .runlog import RunRecord, write_run_log

logger = logging.getLogger(__name__)

LATITUDE = 38.9072
LONGITUDE = -77.0369
HOURLY_VARIABLES = [
    "temperature_2m",
    "precipitation",
    "rain",
    "snowfall",
    "wind_speed_10m",
    "weather_code",
]
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def build_url(mode: str, start: str, end: str) -> str:
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "hourly": ",".join(HOURLY_VARIABLES),
        "timezone": "GMT",
    }
    if mode == "forecast":
        return f"{FORECAST_URL}?{urlencode({**params, 'past_days': 7, 'forecast_days': 1})}"
    if mode == "archive":
        return f"{ARCHIVE_URL}?{urlencode({**params, 'start_date': start, 'end_date': end})}"
    raise ValueError(f"mode must be 'forecast' or 'archive', got {mode!r}")


def validate_weather(body: bytes) -> tuple[dict | None, list[str]]:
    try:
        doc = json.loads(body)
    except (ValueError, UnicodeDecodeError) as exc:
        return None, [f"invalid JSON: {exc}"]
    if not isinstance(doc, dict):
        return None, ["top-level JSON is not an object"]
    if doc.get("error"):
        return doc, [f"API error: {doc.get('reason')}"]

    hourly = doc.get("hourly")
    times = hourly.get("time") if isinstance(hourly, dict) else None
    if not isinstance(times, list) or not times:
        return doc, ["hourly.time missing or empty"]

    errors = [
        f"hourly.{var} missing or length != {len(times)}"
        for var in HOURLY_VARIABLES
        if not isinstance(hourly.get(var), list) or len(hourly[var]) != len(times)
    ]
    return doc, errors


def bronze_key(fetch_date: str, mode: str) -> str:
    return f"bronze/weather/fetch_date={fetch_date}/{mode}.json.gz"


def run(
    event: dict,
    *,
    settings: Settings,
    s3: Any,
    sns: Any,
    fetch: Callable[[str], bytes] = http.fetch,
) -> dict:
    mode = event.get("mode", "forecast")
    end_d = date.fromisoformat(event.get("end") or date.today().isoformat())
    start_d = (
        date.fromisoformat(event["start"]) if event.get("start") else end_d - timedelta(days=7)
    )
    if start_d > end_d:
        raise ValueError(f"start {start_d} is after end {end_d}")
    start, end = start_d.isoformat(), end_d.isoformat()
    fetch_date = event.get("fetch_date") or end

    run_id = f"weather-{mode}-{fetch_date}"
    started = time.monotonic()
    started_at = datetime.now(UTC)
    status, rows, size, key, error = "ok", 0, 0, None, None

    try:
        body = fetch(build_url(mode, start, end))
        doc, problems = validate_weather(body)
        if problems:
            status, error = "quarantined", "; ".join(problems)
            key = f"quarantine/weather/fetch_date={fetch_date}/{mode}.json.gz"
            size = storage.put_gzip_bytes(s3, settings.lake_bucket, key, body)
            alerts.publish(
                sns,
                settings.alerts_topic_arn,
                subject=f"[bikeshare] quarantined weather {mode} {fetch_date}",
                message=f"Weather payload failed validation: {error}\nStored at s3://{settings.lake_bucket}/{key}",
            )
        else:
            doc["ingest_meta"] = {
                "mode": mode,
                "start_date": start,
                "end_date": end,
                "fetched_at": started_at.isoformat(),
            }
            key = bronze_key(fetch_date, mode)
            size = storage.put_gzip_json(s3, settings.lake_bucket, key, doc)
            rows = len(doc["hourly"]["time"])
    except Exception as exc:
        status, error = "failed", f"{type(exc).__name__}: {exc}"
        logger.exception("Weather ingestion failed (%s, %s..%s)", mode, start, end)

    record = RunRecord(
        run_id=run_id,
        source="weather",
        mode=mode,
        period=f"{start}/{end}",
        status=status,
        rows=rows,
        bytes=size,
        object_key=key,
        duration_ms=int((time.monotonic() - started) * 1000),
        error=error,
        started_at=started_at.isoformat(),
    )
    write_run_log(s3, settings.lake_bucket, [record], dt=f"{started_at:%Y-%m-%d}", name=run_id)
    logger.info("weather mode=%s %s..%s status=%s hours=%d", mode, start, end, status, rows)

    if status == "failed":
        raise RuntimeError(f"Weather ingestion failed: {error}")
    return {"mode": mode, "start": start, "end": end, "status": status, "hours": rows, "key": key}
