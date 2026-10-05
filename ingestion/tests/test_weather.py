import gzip
import json
from urllib.parse import parse_qs, urlparse

import pytest
from conftest import BUCKET, list_keys

from bikeshare_ingest import weather


def weather_payload(hours=3, **overrides):
    times = [f"2026-10-04T{h:02d}:00" for h in range(hours)]
    doc = {
        "latitude": 38.9,
        "longitude": -77.04,
        "timezone": "GMT",
        "hourly": {
            "time": times,
            "temperature_2m": [15.1] * hours,
            "precipitation": [0.0] * hours,
            "rain": [0.0] * hours,
            "snowfall": [0.0] * hours,
            "wind_speed_10m": [8.2] * hours,
            "weather_code": [3] * hours,
        },
    }
    doc["hourly"].update(overrides)
    return json.dumps(doc).encode()


def fake_fetch(body: bytes):
    calls = []

    def _fetch(url):
        calls.append(url)
        return body

    _fetch.calls = calls
    return _fetch


def query(url):
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


def test_forecast_mode_uses_past_days(s3, sns, settings):
    fetch = fake_fetch(weather_payload())

    result = weather.run(
        {"mode": "forecast", "end": "2026-10-04"}, settings=settings, s3=s3, sns=sns, fetch=fetch
    )

    [url] = fetch.calls
    assert url.startswith(weather.FORECAST_URL)
    params = query(url)
    assert params["past_days"] == "7"
    assert params["timezone"] == "GMT"
    assert params["hourly"].split(",") == weather.HOURLY_VARIABLES
    assert result["start"] == "2026-09-27"
    assert result["key"] == "bronze/weather/fetch_date=2026-10-04/forecast.json.gz"
    assert result["hours"] == 3


def test_archive_mode_requests_the_exact_range(s3, sns, settings):
    fetch = fake_fetch(weather_payload())

    weather.run(
        {"mode": "archive", "start": "2026-03-25", "end": "2026-04-01", "fetch_date": "2026-04-01"},
        settings=settings,
        s3=s3,
        sns=sns,
        fetch=fetch,
    )

    params = query(fetch.calls[0])
    assert fetch.calls[0].startswith(weather.ARCHIVE_URL)
    assert (params["start_date"], params["end_date"]) == ("2026-03-25", "2026-04-01")
    assert list_keys(s3, "bronze/") == ["bronze/weather/fetch_date=2026-04-01/archive.json.gz"]


def test_stored_document_is_one_line_with_ingest_metadata(s3, sns, settings):
    weather.run(
        {"mode": "forecast", "end": "2026-10-04"},
        settings=settings,
        s3=s3,
        sns=sns,
        fetch=fake_fetch(weather_payload()),
    )

    body = s3.get_object(
        Bucket=BUCKET, Key="bronze/weather/fetch_date=2026-10-04/forecast.json.gz"
    )["Body"].read()
    lines = gzip.decompress(body).decode().splitlines()
    assert len(lines) == 1
    meta = json.loads(lines[0])["ingest_meta"]
    assert meta["mode"] == "forecast"
    assert meta["end_date"] == "2026-10-04"
    assert "fetched_at" in meta


def test_mismatched_lengths_are_quarantined(s3, sns, settings):
    body = weather_payload(rain=[0.0])  # 1 value for 3 hours

    result = weather.run(
        {"mode": "forecast", "end": "2026-10-04"},
        settings=settings,
        s3=s3,
        sns=sns,
        fetch=fake_fetch(body),
    )

    assert result["status"] == "quarantined"
    assert list_keys(s3, "bronze/") == []
    assert list_keys(s3, "quarantine/") == [
        "quarantine/weather/fetch_date=2026-10-04/forecast.json.gz"
    ]
    assert len(sns.messages) == 1


def test_api_error_is_quarantined(s3, sns, settings):
    body = json.dumps({"error": True, "reason": "Parameter end_date is out of range"}).encode()

    result = weather.run(
        {"mode": "archive", "start": "2026-01-01", "end": "2026-01-02"},
        settings=settings,
        s3=s3,
        sns=sns,
        fetch=fake_fetch(body),
    )

    assert result["status"] == "quarantined"


def test_start_after_end_is_rejected(s3, sns, settings):
    with pytest.raises(ValueError, match="after end"):
        weather.run(
            {"mode": "archive", "start": "2026-05-02", "end": "2026-05-01"},
            settings=settings,
            s3=s3,
            sns=sns,
        )


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError, match="mode must be"):
        weather.build_url("hourly", "2026-01-01", "2026-01-02")
