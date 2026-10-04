"""Run log: one JSON line per feed processed, queryable in Athena as ops.run_log."""

import json
from dataclasses import asdict, dataclass
from typing import Any

from .keys import run_log_key


@dataclass
class RunRecord:
    run_id: str
    source: str
    mode: str
    period: str
    status: str  # ok | quarantined | failed
    rows: int
    bytes: int
    object_key: str | None
    duration_ms: int
    error: str | None
    started_at: str


def write_run_log(s3: Any, bucket: str, records: list[RunRecord], *, dt: str, name: str) -> str:
    key = run_log_key(dt, name)
    body = "".join(json.dumps(asdict(r)) + "\n" for r in records)
    s3.put_object(Bucket=bucket, Key=key, Body=body.encode("utf-8"), ContentType="application/json")
    return key
