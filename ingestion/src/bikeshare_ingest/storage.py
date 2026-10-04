"""S3 writes. Bronze JSON is one document per line so Athena's JSON SerDe can read it."""

import gzip
import json
from typing import Any


def put_gzip_json(s3: Any, bucket: str, key: str, doc: dict) -> int:
    """Write a document as one gzipped JSON line; return the stored size in bytes."""
    line = json.dumps(doc, separators=(",", ":"), ensure_ascii=False) + "\n"
    return put_gzip_bytes(s3, bucket, key, line.encode("utf-8"))


def put_gzip_bytes(s3: Any, bucket: str, key: str, raw: bytes) -> int:
    body = gzip.compress(raw)
    s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/gzip")
    return len(body)
