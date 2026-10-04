import json

from bikeshare_ingest.validation import validate_gbfs


def test_valid_status_payload(fixture_bytes):
    doc, errors = validate_gbfs(fixture_bytes("station_status.json"), "2.3")
    assert errors == []
    assert len(doc["data"]["stations"]) == 3


def test_html_error_page_is_rejected():
    doc, errors = validate_gbfs(b"<html><body>502 Bad Gateway</body></html>", "2.3")
    assert doc is None
    assert errors[0].startswith("invalid JSON")


def test_wrong_version_is_rejected(fixture_bytes):
    payload = json.loads(fixture_bytes("station_status.json"))
    payload["version"] = "3.0"
    _, errors = validate_gbfs(json.dumps(payload).encode(), "2.3")
    assert any("version" in e for e in errors)


def test_empty_station_list_is_rejected():
    body = json.dumps({"last_updated": 1, "version": "2.3", "data": {"stations": []}}).encode()
    _, errors = validate_gbfs(body, "2.3")
    assert errors == ["data.stations missing or empty"]


def test_missing_last_updated_is_rejected(fixture_bytes):
    payload = json.loads(fixture_bytes("station_status.json"))
    del payload["last_updated"]
    _, errors = validate_gbfs(json.dumps(payload).encode(), "2.3")
    assert "missing or non-integer last_updated" in errors


def test_station_without_id_is_rejected():
    body = json.dumps(
        {"last_updated": 1, "version": "2.3", "data": {"stations": [{"name": "x"}]}}
    ).encode()
    _, errors = validate_gbfs(body, "2.3")
    assert errors == ["at least one station has no station_id"]
