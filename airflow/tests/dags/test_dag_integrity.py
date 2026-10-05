"""DAG integrity: every DAG imports cleanly and has the shape we rely on."""

from pathlib import Path

import pytest
from airflow.models.dagbag import DagBag

DAGS_DIR = Path(__file__).resolve().parents[2] / "dags"


@pytest.fixture(scope="module")
def dagbag():
    # Only dag_folder: the constructor's other arguments changed across Airflow 3 releases.
    return DagBag(dag_folder=str(DAGS_DIR))


def test_no_import_errors(dagbag):
    assert dagbag.import_errors == {}


def test_expected_dags_are_present(dagbag):
    assert {"daily_pipeline", "trips_monthly"} <= set(dagbag.dag_ids)


@pytest.mark.parametrize(
    ("dag_id", "tasks"),
    [
        ("daily_pipeline", ["invoke_weather", "write_run_log"]),
        ("trips_monthly", ["wait_for_trip_file", "invoke_trips", "write_run_log"]),
    ],
)
def test_task_order(dagbag, dag_id, tasks):
    dag = dagbag.get_dag(dag_id)
    assert [t.task_id for t in dag.topological_sort()] == tasks


@pytest.mark.parametrize("dag_id", ["daily_pipeline", "trips_monthly"])
def test_dags_are_safe_for_backfill(dagbag, dag_id):
    dag = dagbag.get_dag(dag_id)
    assert dag.catchup is True
    assert dag.max_active_runs == 1
    assert "bikeshare" in dag.tags


@pytest.mark.parametrize("dag_id", ["daily_pipeline", "trips_monthly"])
def test_every_task_alerts_on_failure(dagbag, dag_id):
    for t in dagbag.get_dag(dag_id).tasks:
        assert t.on_failure_callback, f"{dag_id}.{t.task_id} has no failure alert"


def test_run_log_task_runs_even_after_failures(dagbag):
    for dag_id in ("daily_pipeline", "trips_monthly"):
        assert dagbag.get_dag(dag_id).get_task("write_run_log").trigger_rule == "all_done"
