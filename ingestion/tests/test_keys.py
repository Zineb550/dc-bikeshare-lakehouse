from datetime import UTC, datetime, timedelta, timezone

from bikeshare_ingest.keys import floor_to_slot, gbfs_key, run_log_key, slot_from_event


def test_floor_to_slot_rounds_down_to_quarter_hour():
    ts = datetime(2026, 10, 3, 1, 29, 59, 999, tzinfo=UTC)
    assert floor_to_slot(ts) == datetime(2026, 10, 3, 1, 15, tzinfo=UTC)


def test_floor_to_slot_converts_to_utc():
    ts = datetime(2026, 10, 3, 9, 7, tzinfo=timezone(timedelta(hours=-4)))  # 13:07 UTC
    assert floor_to_slot(ts) == datetime(2026, 10, 3, 13, 0, tzinfo=UTC)


def test_slot_from_scheduler_time():
    slot = slot_from_event({"scheduled_time": "2026-10-03T01:15:00Z"})
    assert slot == datetime(2026, 10, 3, 1, 15, tzinfo=UTC)


def test_slot_from_now_when_no_scheduled_time():
    now = datetime(2026, 10, 3, 23, 52, 10, tzinfo=UTC)
    assert slot_from_event({}, now=now) == datetime(2026, 10, 3, 23, 45, tzinfo=UTC)


def test_gbfs_key_layout():
    slot = datetime(2026, 10, 3, 1, 15, tzinfo=UTC)
    assert (
        gbfs_key("bronze", "station_status", slot)
        == "bronze/gbfs/station_status/dt=2026-10-03/slot=0115.json.gz"
    )


def test_run_log_key_layout():
    assert run_log_key("2026-10-03", "gbfs-x") == "ops/run_log/dt=2026-10-03/gbfs-x.json"
