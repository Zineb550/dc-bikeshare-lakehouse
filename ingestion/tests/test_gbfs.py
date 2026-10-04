import gzip
import json

import pytest
from conftest import BUCKET, list_keys

from bikeshare_ingest import gbfs


def make_fetch(fixture_bytes, overrides=None):
    """Fake HTTP fetch serving fixtures; `overrides` maps feed name -> bytes or Exception."""
    overrides = overrides or {}

    def _fetch(url: str) -> bytes:
        feed = url.rsplit("/", 1)[-1].removesuffix(".json")
        result = overrides.get(feed)
        if isinstance(result, Exception):
            raise result
        return result if result is not None else fixture_bytes(f"{feed}.json")

    return _fetch


def read_gzip_lines(s3, key):
    body = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()
    return gzip.decompress(body).decode().splitlines()


def read_run_log(s3, key):
    body = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read().decode()
    return [json.loads(line) for line in body.splitlines()]


EVENT_0115 = {"source": "gbfs", "mode": "scheduled", "scheduled_time": "2026-10-03T01:15:00Z"}
EVENT_0100 = {"source": "gbfs", "mode": "scheduled", "scheduled_time": "2026-10-03T01:00:00Z"}


def test_quarter_hour_slot_writes_status_only(s3, sns, settings, fixture_bytes):
    gbfs.run(EVENT_0115, settings=settings, s3=s3, sns=sns, fetch=make_fetch(fixture_bytes))

    assert list_keys(s3, "bronze/") == [
        "bronze/gbfs/station_status/dt=2026-10-03/slot=0115.json.gz"
    ]
    lines = read_gzip_lines(s3, "bronze/gbfs/station_status/dt=2026-10-03/slot=0115.json.gz")
    assert len(lines) == 1, "Athena's JSON SerDe needs one document per line"
    assert len(json.loads(lines[0])["data"]["stations"]) == 3

    [record] = read_run_log(s3, "ops/run_log/dt=2026-10-03/gbfs-20261003T0115.json")
    assert record["status"] == "ok"
    assert record["rows"] == 3
    assert record["mode"] == "scheduled"
    assert sns.messages == []


def test_top_of_hour_slot_also_writes_station_information(s3, sns, settings, fixture_bytes):
    gbfs.run(EVENT_0100, settings=settings, s3=s3, sns=sns, fetch=make_fetch(fixture_bytes))

    assert list_keys(s3, "bronze/") == [
        "bronze/gbfs/station_information/dt=2026-10-03/slot=0100.json.gz",
        "bronze/gbfs/station_status/dt=2026-10-03/slot=0100.json.gz",
    ]
    records = read_run_log(s3, "ops/run_log/dt=2026-10-03/gbfs-20261003T0100.json")
    assert [r["source"] for r in records] == ["gbfs_station_status", "gbfs_station_information"]


def test_rerun_of_same_slot_overwrites_instead_of_duplicating(s3, sns, settings, fixture_bytes):
    for _ in range(2):
        gbfs.run(EVENT_0115, settings=settings, s3=s3, sns=sns, fetch=make_fetch(fixture_bytes))

    assert len(list_keys(s3, "bronze/")) == 1
    assert len(list_keys(s3, "ops/")) == 1


def test_invalid_payload_goes_to_quarantine_and_alerts(s3, sns, settings, fixture_bytes):
    fetch = make_fetch(fixture_bytes, {"station_status": b"<html>502 Bad Gateway</html>"})

    result = gbfs.run(EVENT_0115, settings=settings, s3=s3, sns=sns, fetch=fetch)

    assert list_keys(s3, "bronze/") == []
    assert list_keys(s3, "quarantine/") == [
        "quarantine/gbfs/station_status/dt=2026-10-03/slot=0115.json.gz"
    ]
    assert result["results"][0]["status"] == "quarantined"
    assert len(sns.messages) == 1
    assert "quarantined station_status" in sns.messages[0]["Subject"]
    [record] = read_run_log(s3, "ops/run_log/dt=2026-10-03/gbfs-20261003T0115.json")
    assert record["status"] == "quarantined"
    assert record["error"].startswith("invalid JSON")


def test_fetch_failure_is_logged_then_raised(s3, sns, settings, fixture_bytes):
    fetch = make_fetch(fixture_bytes, {"station_status": ConnectionError("timeout")})

    with pytest.raises(RuntimeError, match="GBFS fetch failed"):
        gbfs.run(EVENT_0115, settings=settings, s3=s3, sns=sns, fetch=fetch)

    [record] = read_run_log(s3, "ops/run_log/dt=2026-10-03/gbfs-20261003T0115.json")
    assert record["status"] == "failed"
    assert "ConnectionError" in record["error"]
    assert list_keys(s3, "bronze/") == []


def test_info_failure_does_not_lose_the_status_snapshot(s3, sns, settings, fixture_bytes):
    fetch = make_fetch(fixture_bytes, {"station_information": ConnectionError("timeout")})

    with pytest.raises(RuntimeError):
        gbfs.run(EVENT_0100, settings=settings, s3=s3, sns=sns, fetch=fetch)

    assert list_keys(s3, "bronze/") == [
        "bronze/gbfs/station_status/dt=2026-10-03/slot=0100.json.gz"
    ]
