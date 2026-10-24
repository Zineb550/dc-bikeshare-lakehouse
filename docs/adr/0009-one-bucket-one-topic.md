# ADR-0009: One S3 bucket with prefixes, one SNS topic

- **Status:** accepted
- **Date:** 2026-10-03

## Context

The lake has several areas (bronze, silver, gold, quarantine, Athena results, run log), and several components can fail (Lambda, Airflow, dbt tests, budget).

## Decision

Use one bucket, `dc-bikeshare-lake-<account-id>`, with one prefix per area, and one SNS topic, `bikeshare-alerts`, for every alert.

## Alternatives rejected

| Alternative | Why rejected |
| --- | --- |
| One bucket per layer | More policies and Terraform resources for no security gain at this scale. |
| One topic per component | More subscriptions to confirm; one inbox is enough for one operator. |

## Consequences

IAM policies scope access by prefix (for example, Metabase reads only `silver/` and `gold/`). Lifecycle rules apply per prefix: Athena results expire after 7 days, quarantine after 30. With a team, alerts would need routing by severity.
