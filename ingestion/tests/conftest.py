from pathlib import Path

import boto3
import pytest
from moto import mock_aws

from bikeshare_ingest.config import Settings

FIXTURES = Path(__file__).parent / "fixtures"
BUCKET = "test-lake"
TOPIC = "arn:aws:sns:us-east-1:123456789012:bikeshare-alerts"


@pytest.fixture
def fixture_bytes():
    def _load(name: str) -> bytes:
        return (FIXTURES / name).read_bytes()

    return _load


@pytest.fixture
def s3(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


class FakeSNS:
    """Records published alerts instead of sending them."""

    def __init__(self):
        self.messages: list[dict] = []

    def publish(self, **kwargs):
        self.messages.append(kwargs)


@pytest.fixture
def sns():
    return FakeSNS()


@pytest.fixture
def settings():
    return Settings(lake_bucket=BUCKET, alerts_topic_arn=TOPIC)


def list_keys(s3_client, prefix: str = "") -> list[str]:
    response = s3_client.list_objects_v2(Bucket=BUCKET, Prefix=prefix)
    return sorted(obj["Key"] for obj in response.get("Contents", []))
