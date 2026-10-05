"""Monthly trip history: zip from Capital Bikeshare's public bucket -> one Parquet file in bronze.

Bronze keeps every column as a string, exactly as published; typing, time zones and
deduplication happen in dbt. The output key depends only on the month, so a rerun
replaces the file instead of adding a second copy.

Outcomes:
- valid file          -> bronze/trips/month=YYYY-MM/trips.parquet, run log "ok"
- unexpected content  -> raw zip to quarantine/ + SNS alert, run log "quarantined"
- not published (404) or download error -> run log "failed", then raise
"""

import io
import logging
import re
import time
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from . import alerts, http
from .config import Settings
from .runlog import RunRecord, write_run_log

logger = logging.getLogger(__name__)

TRIP_URL = "https://s3.amazonaws.com/capitalbikeshare-data/{yyyymm}-capitalbikeshare-tripdata.zip"

EXPECTED_COLUMNS = [
    "ride_id",
    "rideable_type",
    "started_at",
    "ended_at",
    "start_station_name",
    "start_station_id",
    "end_station_name",
    "end_station_id",
    "start_lat",
    "start_lng",
    "end_lat",
    "end_lng",
    "member_casual",
]

MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class InvalidTripFile(ValueError):
    """The zip does not contain the expected single CSV with the expected columns."""


def bronze_key(month: str) -> str:
    return f"bronze/trips/month={month}/trips.parquet"


def quarantine_key(month: str) -> str:
    return f"quarantine/trips/month={month}/tripdata.zip"


def find_csv(zf: zipfile.ZipFile) -> str:
    """The single trip CSV, ignoring macOS metadata entries."""
    names = [
        n
        for n in zf.namelist()
        if n.lower().endswith(".csv") and not n.startswith("__MACOSX/") and "/._" not in f"/{n}"
    ]
    if len(names) != 1:
        raise InvalidTripFile(f"expected exactly one CSV in the zip, found {names}")
    return names[0]


def csv_to_table(raw_csv: bytes, *, source_file: str, source_etag: str | None) -> pa.Table:
    """Parse the CSV with every column as a string and add lineage columns."""
    header = raw_csv.split(b"\n", 1)[0].decode("utf-8-sig").strip().split(",")
    header = [h.strip().strip('"') for h in header]
    if header != EXPECTED_COLUMNS:
        raise InvalidTripFile(f"unexpected columns: {header}")

    table = pacsv.read_csv(
        io.BytesIO(raw_csv),
        convert_options=pacsv.ConvertOptions(
            column_types=dict.fromkeys(EXPECTED_COLUMNS, pa.string()),
            strings_can_be_null=True,
        ),
    )
    if table.num_rows == 0:
        raise InvalidTripFile("CSV has no rows")

    n = table.num_rows
    table = table.append_column("source_file", pa.array([source_file] * n, pa.string()))
    return table.append_column("source_etag", pa.array([source_etag] * n, pa.string()))


def run(
    event: dict,
    *,
    settings: Settings,
    s3: Any,
    sns: Any,
    download: Callable[[str], tuple[bytes, str | None]] = http.download,
) -> dict:
    month = event.get("month", "")
    if not MONTH_RE.match(month):
        raise ValueError(f"event['month'] must be YYYY-MM, got {month!r}")

    mode = event.get("mode", "manual")
    url = TRIP_URL.format(yyyymm=month.replace("-", ""))
    run_id = f"trips-{month}"
    started = time.monotonic()
    started_at = datetime.now(UTC)
    status, rows, size, key, error = "ok", 0, 0, None, None

    try:
        body, etag = download(url)
        try:
            with zipfile.ZipFile(io.BytesIO(body)) as zf:
                csv_name = find_csv(zf)
                table = csv_to_table(zf.read(csv_name), source_file=csv_name, source_etag=etag)
        except (InvalidTripFile, zipfile.BadZipFile, pa.ArrowInvalid) as exc:
            status, error = "quarantined", f"{type(exc).__name__}: {exc}"
            key = quarantine_key(month)
            s3.put_object(Bucket=settings.lake_bucket, Key=key, Body=body)
            size = len(body)
            alerts.publish(
                sns,
                settings.alerts_topic_arn,
                subject=f"[bikeshare] quarantined trips {month}",
                message=f"Trip file failed validation: {error}\nStored at s3://{settings.lake_bucket}/{key}",
            )
        else:
            buffer = io.BytesIO()
            pq.write_table(table, buffer, compression="snappy")
            key = bronze_key(month)
            s3.put_object(Bucket=settings.lake_bucket, Key=key, Body=buffer.getvalue())
            rows, size = table.num_rows, buffer.tell()
    except Exception as exc:
        status, error = "failed", f"{type(exc).__name__}: {exc}"
        logger.exception("Trip ingestion failed for %s", month)

    record = RunRecord(
        run_id=run_id,
        source="trips",
        mode=mode,
        period=month,
        status=status,
        rows=rows,
        bytes=size,
        object_key=key,
        duration_ms=int((time.monotonic() - started) * 1000),
        error=error,
        started_at=started_at.isoformat(),
    )
    write_run_log(s3, settings.lake_bucket, [record], dt=f"{started_at:%Y-%m-%d}", name=run_id)
    logger.info("trips month=%s status=%s rows=%d key=%s", month, status, rows, key)

    if status == "failed":
        raise RuntimeError(f"Trip ingestion failed for {month}: {error}")
    return {"month": month, "status": status, "rows": rows, "key": key}
