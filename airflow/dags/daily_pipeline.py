"""daily_pipeline: weather for the day just finished, then (from group 6) dbt build.

Fires at 01:15 UTC on day D and processes day D-1. GBFS snapshots are not collected
here: EventBridge Scheduler + Lambda collect them every 15 minutes, laptop or not.
Catchup from 2026-04-02 (processing 2026-04-01 onward) is the backfill path: it
reuses exactly the same tasks.
"""

from datetime import UTC, datetime, timedelta

from airflow.sdk import TriggerRule, dag, task
from airflow.timetables.trigger import CronTriggerTimetable

from include.bikeshare import lambda_client, periods, runlog
from include.bikeshare.alerts import notify_failure

DEFAULT_ARGS = {
    "owner": "bikeshare",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": notify_failure,
}


@dag(
    dag_id="daily_pipeline",
    description="Daily weather ingestion and transformation",
    schedule=CronTriggerTimetable("15 1 * * *", timezone="UTC"),
    start_date=datetime(2026, 4, 2, tzinfo=UTC),
    catchup=True,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["bikeshare", "daily"],
)
def daily_pipeline():
    @task
    def invoke_weather(**context) -> dict:
        day = periods.target_day(context["logical_date"] or datetime.now(UTC))
        event = periods.weather_event(day, today=datetime.now(UTC).date())
        return lambda_client.invoke(event)

    @task(trigger_rule=TriggerRule.ALL_DONE, retries=0)
    def write_run_log(**context) -> str:
        ti, dag_run = context["ti"], context["dag_run"]
        day = periods.target_day(context["logical_date"] or datetime.now(UTC))
        records = [
            runlog.task_record(
                dag_id=ti.dag_id,
                task_id=task_id,
                run_id=ti.run_id,
                run_type=str(dag_run.run_type),
                period=day.isoformat(),
                result=ti.xcom_pull(task_ids=task_id),
            )
            for task_id in ["invoke_weather"]
        ]
        return runlog.write(records, dag_id=ti.dag_id, run_id=ti.run_id)

    invoke_weather() >> write_run_log()


daily_pipeline()
