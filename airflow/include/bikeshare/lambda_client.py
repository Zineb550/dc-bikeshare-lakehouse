"""Synchronous invocation of the ingest Lambda.

Airflow waits for the result, so a failure or a quarantined payload fails the task
(and triggers its retries and alert) instead of being lost in an async queue.
"""

import json
import time
from typing import Any

import boto3
from botocore.config import Config

from . import settings


class IngestError(RuntimeError):
    """The Lambda raised, or reported a status other than ok."""


def make_client() -> Any:
    # Lambda can run up to 300 s; no SDK retries, Airflow owns retries.
    config = Config(read_timeout=310, connect_timeout=10, retries={"max_attempts": 0})
    return boto3.client("lambda", region_name=settings.aws_region(), config=config)


def invoke(payload: dict, *, client: Any = None, function_name: str | None = None) -> dict:
    """Invoke the ingest function and return its result plus the call duration."""
    client = client or make_client()
    started = time.monotonic()
    response = client.invoke(
        FunctionName=function_name or settings.ingest_function(),
        InvocationType="RequestResponse",
        Payload=json.dumps(payload).encode(),
    )
    raw = response["Payload"].read()
    result = json.loads(raw) if raw else None

    if response.get("FunctionError"):
        message = result.get("errorMessage") if isinstance(result, dict) else raw
        raise IngestError(f"Lambda error for {payload}: {message}")
    if not isinstance(result, dict) or result.get("status") != "ok":
        status = result.get("status") if isinstance(result, dict) else None
        raise IngestError(f"Ingest status {status!r} for {payload}: {result}")

    result["duration_ms"] = int((time.monotonic() - started) * 1000)
    return result
