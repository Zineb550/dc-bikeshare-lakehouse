"""Runtime settings, read from the Lambda environment."""

import os
from dataclasses import dataclass

GBFS_BASE_URL = "https://gbfs.lyft.com/gbfs/2.3/dca-cabi/en"
EXPECTED_GBFS_VERSION = "2.3"


@dataclass(frozen=True)
class Settings:
    lake_bucket: str
    alerts_topic_arn: str | None = None
    gbfs_base_url: str = GBFS_BASE_URL
    expected_gbfs_version: str = EXPECTED_GBFS_VERSION

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            lake_bucket=os.environ["LAKE_BUCKET"],
            alerts_topic_arn=os.environ.get("ALERTS_TOPIC_ARN") or None,
            gbfs_base_url=os.environ.get("GBFS_BASE_URL", GBFS_BASE_URL),
        )
