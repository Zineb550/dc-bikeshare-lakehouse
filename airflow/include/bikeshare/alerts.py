"""Failure alerts: Airflow tasks publish to the same SNS topic as the AWS alarms."""

import logging
from typing import Any

import boto3

from . import settings

logger = logging.getLogger(__name__)


def failure_message(context: dict) -> tuple[str, str]:
    ti = context.get("task_instance") or context.get("ti")
    dag_id = getattr(ti, "dag_id", "?")
    task_id = getattr(ti, "task_id", "?")
    run_id = getattr(ti, "run_id", "?")
    try_number = getattr(ti, "try_number", "?")
    error = context.get("exception")
    subject = f"[bikeshare] Airflow failure: {dag_id}.{task_id}"
    body = (
        f"DAG: {dag_id}\nTask: {task_id}\nRun: {run_id}\nTry: {try_number}\n"
        f"Error: {error!r}\n\nOpen the Airflow UI for the full log."
    )
    return subject, body


def notify_failure(context: dict, sns: Any = None) -> None:
    """on_failure_callback: runs once a task has failed after all its retries."""
    topic = settings.alerts_topic_arn()
    subject, body = failure_message(context)
    if not topic:
        logger.warning("BIKESHARE_ALERTS_TOPIC_ARN not set; alert not sent: %s", subject)
        return
    sns = sns or boto3.client("sns", region_name=settings.aws_region())
    sns.publish(TopicArn=topic, Subject=subject[:100], Message=body)
