"""Run log records for Airflow tasks, same schema as the Lambda's (ops.run_log)."""

import json
import re
from datetime import UTC, datetime
from typing import Any

import boto3

from . import settings


def task_record(
    *,
    dag_id: str,
    task_id: str,
    run_id: str,
    run_type: str,
    period: str,
    result: dict | None,
) -> dict:
    """One record per task; a missing result means the task failed or was skipped."""
    result = result or {}
    return {
        "run_id": run_id,
        "source": f"airflow:{dag_id}.{task_id}",
        "mode": run_type,
        "period": period,
        "status": "ok" if result.get("status") == "ok" else "failed",
        "rows": int(result.get("rows") or result.get("hours") or 0),
        "bytes": 0,
        "object_key": result.get("key"),
        "duration_ms": int(result.get("duration_ms") or 0),
        "error": None if result.get("status") == "ok" else "no result (task failed or skipped)",
        "started_at": datetime.now(UTC).isoformat(),
    }


def object_name(dag_id: str, run_id: str) -> str:
    """S3-safe file name for a DAG run (run ids contain ':' and '+')."""
    return f"airflow-{dag_id}-" + re.sub(r"[^A-Za-z0-9_.-]", "_", run_id)


def write(records: list[dict], *, dag_id: str, run_id: str, s3: Any = None) -> str:
    s3 = s3 or boto3.client("s3", region_name=settings.aws_region())
    dt = datetime.now(UTC).strftime("%Y-%m-%d")
    key = f"ops/run_log/dt={dt}/{object_name(dag_id, run_id)}.json"
    body = "".join(json.dumps(r) + "\n" for r in records)
    s3.put_object(
        Bucket=settings.lake_bucket(), Key=key, Body=body.encode(), ContentType="application/json"
    )
    return key
