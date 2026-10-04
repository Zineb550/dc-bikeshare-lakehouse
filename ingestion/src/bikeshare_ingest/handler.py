"""Single Lambda entry point; dispatches on event["source"].

Event examples:
  {"source": "gbfs", "mode": "scheduled", "scheduled_time": "2026-10-03T01:15:00Z"}
  {"source": "gbfs", "mode": "manual", "force_info": true}
"""

import logging

import boto3

from . import gbfs
from .config import Settings

logging.getLogger().setLevel(logging.INFO)


def handler(event: dict, context: object) -> dict:
    settings = Settings.from_env()
    source = event.get("source")
    if source == "gbfs":
        return gbfs.run(event, settings=settings, s3=boto3.client("s3"), sns=boto3.client("sns"))
    raise ValueError(f"Unknown source: {source!r}")
