# ADR-0006: Data-interval windows for idempotency

- **Status:** accepted
- **Date:** 2026-10-20

## Context

A run must give the same result whether it executes on time, late, twice, or during a backfill months later. Filters based on `now()` or `max(ts)` change with the moment the run executes.

## Decision

Every DAG run passes its own period to dbt: `--vars '{start, end}'` for the daily DAG and `--vars '{month}'` for the monthly DAG, derived from the run's logical date. Every S3 object key also derives from the scheduled time or the requested period, never from the wall clock.

## Alternatives rejected

| Alternative | Why rejected |
| --- | --- |
| Process "the last N days" from `now()` | A rerun next week would process a different window. |
| Process "everything after `max(ts)`" | A failed partial load would be skipped forever. |

## Consequences

Retries overwrite instead of duplicating, and backfills reprocess exactly the requested period. Without vars (a manual run), dbt falls back to the last 2 days. When the daily DAG catches up on old dates, it also rebuilds gold so that KPIs stay consistent.
