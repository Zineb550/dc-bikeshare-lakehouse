"""trips_monthly: wait for last month's trip file, land it in bronze, then (from group 6) dbt.

Fires at 06:00 UTC on the 1st of month M and processes month M-1. Capital Bikeshare
publishes a few days into the month, so the sensor checks every 6 hours for up to
12 days in reschedule mode (it frees its worker slot between checks).
Catchup from 2026-05-01 backfills April onward.
"""

from datetime import UTC, datetime, timedelta

import requests
from airflow.sdk import TriggerRule, dag, task
from airflow.timetables.trigger import CronTriggerTimetable

from include.bikeshare import lambda_client, periods, runlog
from include.bikeshare.alerts import notify_failure

DEFAULT_ARGS = {
    "owner": "bikeshare",
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "on_failure_callback": notify_failure,
}


@dag(
    dag_id="trips_monthly",
    description="Monthly trip history ingestion and transformation",
    schedule=CronTriggerTimetable("0 6 1 * *", timezone="UTC"),
    start_date=datetime(2026, 5, 1, tzinfo=UTC),
    catchup=True,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["bikeshare", "monthly"],
)
def trips_monthly():
    @task.sensor(poke_interval=6 * 3600, timeout=12 * 86400, mode="reschedule", retries=0)
    def wait_for_trip_file(**context) -> bool:
        month = periods.target_month(context["logical_date"] or datetime.now(UTC))
        response = requests.head(periods.trip_file_url(month), timeout=30)
        return response.status_code == 200

    @task(retries=1)
    def invoke_trips(**context) -> dict:
        month = periods.target_month(context["logical_date"] or datetime.now(UTC))
        return lambda_client.invoke({"source": "trips", "mode": "airflow", "month": month})

    @task(trigger_rule=TriggerRule.ALL_DONE, retries=0)
    def write_run_log(**context) -> str:
        ti, dag_run = context["ti"], context["dag_run"]
        month = periods.target_month(context["logical_date"] or datetime.now(UTC))
        records = [
            runlog.task_record(
                dag_id=ti.dag_id,
                task_id="invoke_trips",
                run_id=ti.run_id,
                run_type=str(dag_run.run_type),
                period=month,
                result=ti.xcom_pull(task_ids="invoke_trips"),
            )
        ]
        return runlog.write(records, dag_id=ti.dag_id, run_id=ti.run_id)

    wait_for_trip_file() >> invoke_trips() >> write_run_log()


trips_monthly()
