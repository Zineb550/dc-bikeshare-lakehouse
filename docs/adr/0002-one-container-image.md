# ADR-0002: One container image for all ingestion handlers

- **Status:** accepted
- **Date:** 2026-10-03

## Context

Three sources (GBFS, trips, weather) share most of their code: HTTP with retries, validation, S3 keys, quarantine, run log and SNS alerts. The trips handler needs pyarrow, which is too large for a plain Lambda zip with its dependencies.

## Decision

Build one Python 3.12 container image, push it to ECR, and deploy it as a single Lambda function. The event payload (`{"source": "gbfs" | "trips" | "weather", ...}`) selects the handler.

## Alternatives rejected

| Alternative | Why rejected |
| --- | --- |
| One Lambda zip per source | Duplicated shared code; pyarrow does not fit the zip size limit. |
| Lambda layers | Layers have the same size limit and add a second artifact to version. |

## Consequences

One build, one deployment, one IAM role and one set of alarms. A change to one handler redeploys all three, so the unit tests in `ingestion/tests` run in CI before every merge. ECR keeps the last 3 images to limit storage.
