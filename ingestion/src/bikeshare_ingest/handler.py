"""Single Lambda entry point; dispatches on event["source"].

Event examples:
  {"source": "gbfs", "mode": "scheduled", "scheduled_time": "2026-10-03T01:15:00Z"}
  {"source": "gbfs", "mode": "manual", "force_info": true}
  {"source": "trips", "month": "2026-08"}
  {"source": "weather", "mode": "forecast", "end": "2026-10-04"}
  {"source": "weather", "mode": "archive", "start": "2026-03-25", "end": "2026-04-01", "fetch_date": "2026-04-01"}
"""

import logging

import boto3

from . import gbfs, trips, weather
from .config import Settings

logging.getLogger().setLevel(logging.INFO)

RUNNERS = {"gbfs": gbfs.run, "trips": trips.run, "weather": weather.run}


def handler(event: dict, context: object) -> dict:
    source = event.get("source")
    runner = RUNNERS.get(source)
    if runner is None:
        raise ValueError(f"Unknown source: {source!r}")
    return runner(
        event,
        settings=Settings.from_env(),
        s3=boto3.client("s3"),
        sns=boto3.client("sns"),
    )
