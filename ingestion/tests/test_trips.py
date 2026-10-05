import io
import zipfile

import pyarrow.parquet as pq
import pytest
from conftest import BUCKET, list_keys

from bikeshare_ingest import trips
from bikeshare_ingest.http import NotFoundError

HEADER = ",".join(trips.EXPECTED_COLUMNS)
ROWS = [
    # docked trip, timestamps in local time with milliseconds, as published
    "A6A53E597CC656B6,electric_bike,2026-08-07 18:19:10.375,2026-08-07 18:34:20.225,"
    "Wisconsin Ave & O St NW,31312,16th & Irving St NW,31122,38.90849,-77.063586,38.928893,-77.03625,member",
    # dockless start: empty station name and id
    "29030C8FA7C55451,electric_bike,2026-08-05 09:11:56.298,2026-08-05 09:22:53.613,"
    ",,Medical Center Metro,32053,38.96,-77.08,38.999378,-77.097882,casual",
    # ride that started in the previous month (163 such rides in the real August file)
    "DFE69DD43739BA23,classic_bike,2026-07-31 23:43:35.917,2026-08-01 00:07:21.009,"
    "20th & M St NW,31139,15th & L St NW,31276,38.905496,-77.044976,38.903967,-77.034602,member",
]


def make_zip(
    csv_text: str, *, macos_junk: bool = True, name="202608-capitalbikeshare-tripdata.csv"
):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(name, csv_text)
        if macos_junk:
            zf.writestr(f"__MACOSX/._{name}", b"\x00\x05\x16\x07 binary junk")
    return buffer.getvalue()


def fake_download(body: bytes, etag: str = "abc123"):
    calls = []

    def _download(url):
        calls.append(url)
        return body, etag

    _download.calls = calls
    return _download


def valid_csv():
    return "\n".join([HEADER, *ROWS]) + "\n"


def read_bronze(s3, month="2026-08"):
    body = s3.get_object(Bucket=BUCKET, Key=f"bronze/trips/month={month}/trips.parquet")["Body"]
    return pq.read_table(io.BytesIO(body.read()))


def test_valid_month_lands_as_string_parquet(s3, sns, settings):
    download = fake_download(make_zip(valid_csv()))

    result = trips.run({"month": "2026-08"}, settings=settings, s3=s3, sns=sns, download=download)

    assert download.calls == [
        "https://s3.amazonaws.com/capitalbikeshare-data/202608-capitalbikeshare-tripdata.zip"
    ]
    assert result == {
        "month": "2026-08",
        "status": "ok",
        "rows": 3,
        "key": "bronze/trips/month=2026-08/trips.parquet",
    }
    table = read_bronze(s3)
    assert table.column_names == [*trips.EXPECTED_COLUMNS, "source_file", "source_etag"]
    assert all(str(field.type) == "string" for field in table.schema)
    rows = table.to_pylist()
    assert rows[0]["started_at"] == "2026-08-07 18:19:10.375"  # untouched, still local time
    assert rows[1]["start_station_id"] is None  # empty string becomes null
    assert rows[2]["started_at"].startswith("2026-07-31")  # previous-month ride kept
    assert {r["source_etag"] for r in rows} == {"abc123"}
    assert sns.messages == []


def test_rerun_replaces_the_month_file(s3, sns, settings):
    for _ in range(2):
        trips.run(
            {"month": "2026-08"},
            settings=settings,
            s3=s3,
            sns=sns,
            download=fake_download(make_zip(valid_csv())),
        )

    assert list_keys(s3, "bronze/") == ["bronze/trips/month=2026-08/trips.parquet"]
    assert read_bronze(s3).num_rows == 3


def test_changed_columns_are_quarantined(s3, sns, settings):
    csv = "\n".join([HEADER.replace("member_casual", "user_type"), *ROWS])

    result = trips.run(
        {"month": "2026-08"},
        settings=settings,
        s3=s3,
        sns=sns,
        download=fake_download(make_zip(csv)),
    )

    assert result["status"] == "quarantined"
    assert list_keys(s3, "bronze/") == []
    assert list_keys(s3, "quarantine/") == ["quarantine/trips/month=2026-08/tripdata.zip"]
    assert "quarantined trips 2026-08" in sns.messages[0]["Subject"]


def test_zip_without_csv_is_quarantined(s3, sns, settings):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("readme.txt", "nothing here")

    result = trips.run(
        {"month": "2026-08"},
        settings=settings,
        s3=s3,
        sns=sns,
        download=fake_download(buffer.getvalue()),
    )

    assert result["status"] == "quarantined"


def test_not_a_zip_is_quarantined(s3, sns, settings):
    result = trips.run(
        {"month": "2026-08"},
        settings=settings,
        s3=s3,
        sns=sns,
        download=fake_download(b"<html>Access Denied</html>"),
    )

    assert result["status"] == "quarantined"


def test_unpublished_month_fails_and_raises(s3, sns, settings):
    def not_found(url):
        raise NotFoundError(url)

    with pytest.raises(RuntimeError, match="Trip ingestion failed for 2026-09"):
        trips.run({"month": "2026-09"}, settings=settings, s3=s3, sns=sns, download=not_found)

    assert list_keys(s3, "bronze/") == []
    assert len(list_keys(s3, "ops/run_log/")) == 1


@pytest.mark.parametrize("month", ["2026-8", "202608", "2026-13", "", None])
def test_bad_month_is_rejected(s3, sns, settings, month):
    with pytest.raises(ValueError, match="YYYY-MM"):
        trips.run({"month": month} if month else {}, settings=settings, s3=s3, sns=sns)
