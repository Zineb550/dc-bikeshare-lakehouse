"""daily_pipeline: weather for the day just finished, then dbt (freshness, build).

Fires at 01:15 UTC on day D and processes day D-1. GBFS snapshots are not collected
here: EventBridge Scheduler + Lambda collect them every 15 minutes, laptop or not.
Catchup from 2026-04-02 (processing 2026-04-01 onward) is the backfill path: it
reuses exactly the same tasks.
"""

from datetime import UTC, datetime, timedelta

from airflow.sdk import TriggerRule, dag, task
from airflow.timetables.trigger import CronTriggerTimetable

from include.bikeshare import dbt, lambda_client, periods, runlog
from include.bikeshare.alerts import notify_failure

TASKS_LOGGED = ["invoke_weather", "dbt_source_freshness", "dbt_build"]

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

    @task(retries=0)
    def dbt_source_freshness(**context) -> dict:
        ti = context["ti"]
        return dbt.run(
            [
                "source",
                "freshness",
                "--select",
                "source:bronze.gbfs_station_status",
                "source:bronze.weather_raw",
            ],
            target_dir=dbt.artifacts_dir(ti.dag_id, ti.run_id, ti.task_id),
        )

    @task(retries=1)
    def dbt_build(**context) -> dict:
        # Everything except fct_trip itself (trips_monthly loads it); gold is rebuilt daily
        # from the current fct_trip, so daily snapshots refresh the rankings.
        # Catching up on old days, gold is skipped: it is a full rebuild, done once at the end.
        ti = context["ti"]
        day = periods.target_day(context["logical_date"] or datetime.now(UTC))
        exclude = ["fct_trip"]
        if periods.is_catch_up(day, today=datetime.now(UTC).date()):
            exclude.append("path:models/gold")
        return dbt.run(
            ["build", "--exclude", *exclude],
            target_dir=dbt.artifacts_dir(ti.dag_id, ti.run_id, ti.task_id),
            dbt_vars=dbt.day_vars(day),
        )

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
            for task_id in TASKS_LOGGED
        ]
        return runlog.write(records, dag_id=ti.dag_id, run_id=ti.run_id)

    invoke_weather() >> dbt_source_freshness() >> dbt_build() >> write_run_log()


daily_pipeline()
