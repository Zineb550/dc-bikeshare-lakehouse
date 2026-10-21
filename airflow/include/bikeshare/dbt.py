"""Run dbt from Airflow tasks.

dbt lives in its own virtualenv inside the Airflow image (see the Dockerfile), so its
dependencies never clash with Airflow's. Each run writes its artifacts to a private
directory under /tmp, so the two DAGs can run dbt at the same time.
"""

import json
import os
import re
import subprocess  # noqa: S404 - dbt is a CLI; the command is built from fixed parts
import time
from datetime import date, timedelta
from pathlib import Path

AIRFLOW_HOME = Path(os.environ.get("AIRFLOW_HOME", "/usr/local/airflow"))
DBT_BIN = AIRFLOW_HOME / "dbt_venv" / "bin" / "dbt"
PROJECT_DIR = AIRFLOW_HOME / "dbt"


class DbtError(RuntimeError):
    """dbt exited with a non-zero code (a model, test or freshness check failed)."""


def day_vars(day: date) -> dict:
    """Run window for one UTC day: start inclusive, end exclusive."""
    return {"start": day.isoformat(), "end": (day + timedelta(days=1)).isoformat()}


def month_vars(month: str) -> dict:
    return {"month": month}


def artifacts_dir(dag_id: str, run_id: str, task_id: str) -> Path:
    safe_run = re.sub(r"[^A-Za-z0-9_.-]", "_", run_id)
    return Path("/tmp/dbt") / dag_id / safe_run / task_id  # noqa: S108 - per-run scratch dir


def build_command(args: list[str], target_dir: Path, dbt_vars: dict | None = None) -> list[str]:
    command = [
        str(DBT_BIN),
        *args,
        "--project-dir",
        str(PROJECT_DIR),
        "--profiles-dir",
        str(PROJECT_DIR),
        "--target-path",
        str(target_dir / "target"),
        "--log-path",
        str(target_dir / "logs"),
    ]
    if dbt_vars:
        command += ["--vars", json.dumps(dbt_vars)]
    return command


def summarize(results_file: Path) -> dict:
    """Counts per status from run_results.json (or sources.json for freshness)."""
    if not results_file.exists():
        return {}
    results = json.loads(results_file.read_text()).get("results", [])
    counts: dict[str, int] = {}
    for result in results:
        status = str(result.get("status"))
        counts[status] = counts.get(status, 0) + 1
    return counts


def run(args: list[str], *, target_dir: Path, dbt_vars: dict | None = None) -> dict:
    """Run one dbt command; raise DbtError on failure, return a run-log friendly result."""
    command = build_command(args, target_dir, dbt_vars)
    print("Running:", " ".join(command))
    started = time.monotonic()
    process = subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603
    print(process.stdout[-50_000:])
    if process.stderr:
        print(process.stderr[-10_000:])

    results_name = "sources.json" if args[:2] == ["source", "freshness"] else "run_results.json"
    counts = summarize(target_dir / "target" / results_name)
    if process.returncode != 0:
        raise DbtError(f"dbt {' '.join(args)} failed (exit {process.returncode}): {counts}")
    return {
        "status": "ok",
        "rows": sum(counts.values()),
        "counts": counts,
        "duration_ms": int((time.monotonic() - started) * 1000),
    }
