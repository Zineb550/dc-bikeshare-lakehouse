"""Settings read from the container environment (airflow/.env, gitignored)."""

import os


def lake_bucket() -> str:
    return os.environ["BIKESHARE_LAKE_BUCKET"]


def ingest_function() -> str:
    return os.environ.get("BIKESHARE_INGEST_FUNCTION", "dc-bikeshare-ingest")


def alerts_topic_arn() -> str | None:
    return os.environ.get("BIKESHARE_ALERTS_TOPIC_ARN") or None


def aws_region() -> str:
    return os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
