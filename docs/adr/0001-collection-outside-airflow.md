# ADR-0001: Collect GBFS with EventBridge Scheduler and Lambda, outside Airflow

- **Status:** accepted
- **Date:** 2026-10-03

## Context

GBFS station status is a live feed: each 15-minute snapshot exists only at the moment it is published and cannot be fetched later. Trips and weather, by contrast, can be downloaded again at any time. Airflow runs locally on a laptop that is often off.

## Decision

EventBridge Scheduler invokes the ingest Lambda every 15 minutes (`cron(0/15 * * * ? *)`, UTC). Airflow handles only what can be backfilled: monthly trips, weather and dbt.

## Alternatives rejected

| Alternative | Why rejected |
| --- | --- |
| Airflow task every 15 minutes | Every hour the laptop is off becomes a permanent hole in the data. |
| Managed Airflow (MWAA) | Several hundred dollars a month, far above the budget. |
| ECS task on a schedule | More moving parts (cluster, task definition, networking) for a job that runs a few seconds. |

## Consequences

Collection keeps running whatever the laptop does, at almost no cost (about 2,900 invocations a month, inside the Lambda free tier). The pipeline has two schedulers to understand instead of one, and KPIs refresh only when Airflow runs.
