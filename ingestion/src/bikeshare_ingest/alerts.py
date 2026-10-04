"""SNS alerts (email). A missing topic disables alerts, e.g. in local tests."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def publish(sns: Any, topic_arn: str | None, subject: str, message: str) -> None:
    if not topic_arn:
        logger.warning("No alerts topic configured; alert not sent: %s", subject)
        return
    sns.publish(TopicArn=topic_arn, Subject=subject[:100], Message=message)
