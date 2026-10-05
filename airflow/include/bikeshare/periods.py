"""Which period a DAG run processes, derived only from its logical date.

Both DAGs use CronTriggerTimetable, so a run's logical date is the moment it was
scheduled to fire. Deriving the period from that date (never from "now") is what
makes reruns and backfills reprocess exactly the same period.
"""

from datetime import date, datetime, timedelta

TRIP_URL = "https://s3.amazonaws.com/capitalbikeshare-data/{yyyymm}-capitalbikeshare-tripdata.zip"

# Open-Meteo's Forecast API (past_days=7) has no publication delay; older days come
# from the Archive API (ERA5). Recent days use the forecast endpoint.
FORECAST_HORIZON_DAYS = 5
WEATHER_WINDOW_DAYS = 7


def target_day(logical_date: datetime) -> date:
    """The daily run fired at 01:15 UTC on day D processes day D-1 (complete in UTC)."""
    return (logical_date - timedelta(days=1)).date()


def target_month(logical_date: datetime) -> str:
    """The monthly run fired on the 1st of month M processes month M-1, as 'YYYY-MM'."""
    first_of_month = logical_date.date().replace(day=1)
    return (first_of_month - timedelta(days=1)).strftime("%Y-%m")


def trip_file_url(month: str) -> str:
    return TRIP_URL.format(yyyymm=month.replace("-", ""))


def weather_event(day: date, today: date) -> dict:
    """Lambda event fetching [day - 7, day]; forecast mode when day is recent."""
    start = day - timedelta(days=WEATHER_WINDOW_DAYS)
    mode = "forecast" if (today - day).days <= FORECAST_HORIZON_DAYS else "archive"
    return {
        "source": "weather",
        "mode": mode,
        "start": start.isoformat(),
        "end": day.isoformat(),
        "fetch_date": day.isoformat(),
    }
