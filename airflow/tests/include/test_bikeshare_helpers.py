import io
import json
from datetime import UTC, date, datetime

import pytest

from include.bikeshare import alerts, lambda_client, periods, runlog

# --- periods -----------------------------------------------------------------


def test_daily_run_processes_the_previous_utc_day():
    assert periods.target_day(datetime(2026, 10, 5, 1, 15, tzinfo=UTC)) == date(2026, 10, 4)


@pytest.mark.parametrize(
    ("fired", "month"),
    [
        (datetime(2026, 5, 1, 6, tzinfo=UTC), "2026-04"),
        (datetime(2026, 10, 1, 6, tzinfo=UTC), "2026-09"),
        (datetime(2027, 1, 1, 6, tzinfo=UTC), "2026-12"),
    ],
)
def test_monthly_run_processes_the_previous_month(fired, month):
    assert periods.target_month(fired) == month


def test_trip_file_url():
    assert periods.trip_file_url("2026-08") == (
        "https://s3.amazonaws.com/capitalbikeshare-data/202608-capitalbikeshare-tripdata.zip"
    )


def test_recent_day_uses_forecast_mode():
    event = periods.weather_event(date(2026, 10, 4), today=date(2026, 10, 5))
    assert event == {
        "source": "weather",
        "mode": "forecast",
        "start": "2026-09-27",
        "end": "2026-10-04",
        "fetch_date": "2026-10-04",
    }


def test_backfill_day_uses_archive_mode():
    event = periods.weather_event(date(2026, 4, 30), today=date(2026, 10, 5))
    assert event["mode"] == "archive"
    assert (event["start"], event["end"]) == ("2026-04-23", "2026-04-30")


# --- lambda_client -----------------------------------------------------------


class FakeLambda:
    def __init__(self, result, function_error=None):
        self.result, self.function_error, self.calls = result, function_error, []

    def invoke(self, **kwargs):
        self.calls.append(kwargs)
        response = {"Payload": io.BytesIO(json.dumps(self.result).encode())}
        if self.function_error:
            response["FunctionError"] = self.function_error
        return response


def test_invoke_is_synchronous_and_returns_result():
    client = FakeLambda({"status": "ok", "rows": 646082})

    result = lambda_client.invoke(
        {"source": "trips", "month": "2026-08"}, client=client, function_name="fn"
    )

    assert result["rows"] == 646082
    assert "duration_ms" in result
    call = client.calls[0]
    assert call["InvocationType"] == "RequestResponse"
    assert json.loads(call["Payload"]) == {"source": "trips", "month": "2026-08"}


def test_lambda_exception_raises():
    client = FakeLambda({"errorMessage": "boom"}, function_error="Unhandled")
    with pytest.raises(lambda_client.IngestError, match="boom"):
        lambda_client.invoke({"source": "trips"}, client=client, function_name="fn")


def test_quarantined_result_raises():
    client = FakeLambda({"status": "quarantined"})
    with pytest.raises(lambda_client.IngestError, match="quarantined"):
        lambda_client.invoke({"source": "weather"}, client=client, function_name="fn")


# --- alerts ------------------------------------------------------------------


class FakeTI:
    dag_id, task_id, run_id, try_number = "daily_pipeline", "invoke_weather", "scheduled__x", 3


class FakeSNS:
    def __init__(self):
        self.messages = []

    def publish(self, **kwargs):
        self.messages.append(kwargs)


def test_failure_alert_names_dag_and_task(monkeypatch):
    monkeypatch.setenv("BIKESHARE_ALERTS_TOPIC_ARN", "arn:aws:sns:us-east-1:1:t")
    sns = FakeSNS()

    alerts.notify_failure({"ti": FakeTI(), "exception": ValueError("bad")}, sns=sns)

    [msg] = sns.messages
    assert msg["Subject"] == "[bikeshare] Airflow failure: daily_pipeline.invoke_weather"
    assert "ValueError('bad')" in msg["Message"]


def test_no_topic_means_no_alert(monkeypatch):
    monkeypatch.delenv("BIKESHARE_ALERTS_TOPIC_ARN", raising=False)
    sns = FakeSNS()
    alerts.notify_failure({"ti": FakeTI()}, sns=sns)
    assert sns.messages == []


# --- runlog ------------------------------------------------------------------


def test_record_from_successful_task():
    record = runlog.task_record(
        dag_id="trips_monthly",
        task_id="invoke_trips",
        run_id="scheduled__2026-09-01T06:00:00+00:00",
        run_type="scheduled",
        period="2026-08",
        result={
            "status": "ok",
            "rows": 646082,
            "key": "bronze/trips/month=2026-08/trips.parquet",
            "duration_ms": 41000,
        },
    )
    assert record["status"] == "ok"
    assert record["rows"] == 646082
    assert record["source"] == "airflow:trips_monthly.invoke_trips"


def test_record_from_failed_task():
    record = runlog.task_record(
        dag_id="d", task_id="t", run_id="r", run_type="scheduled", period="p", result=None
    )
    assert record["status"] == "failed"
    assert record["error"]


def test_object_name_is_s3_safe():
    name = runlog.object_name("daily_pipeline", "scheduled__2026-10-05T01:15:00+00:00")
    assert name == "airflow-daily_pipeline-scheduled__2026-10-05T01_15_00_00_00"
