# ADR-0004: Iceberg MERGE for silver tables

- **Status:** accepted
- **Date:** 2026-10-20

## Context

Silver tables are loaded incrementally and must stay correct when a run is retried or a period is backfilled. Monthly trip files do not split cleanly by month: the August file contained 163 rides that started on July 30–31. A plain `INSERT` would duplicate rows on every rerun, and replacing a whole partition would lose rides that belong to the previous month's file.

## Decision

Materialize silver tables as Apache Iceberg tables with dbt's incremental `merge` strategy, keyed on natural keys: `ride_id` for trips, station × slot for status, `hour_ts` for weather (keeping the latest fetch).

## Alternatives rejected

| Alternative | Why rejected |
| --- | --- |
| Append (`insert into`) | Duplicates on every retry or backfill. |
| Insert-overwrite by partition | Month-boundary rides fall into a partition loaded by another file and would be lost or duplicated. |
| Full rebuild of silver | Rescans all bronze every day; cost and time grow with history. |

## Consequences

Reruns are idempotent: the backfill was run twice and gave identical row counts. MERGE needs Athena engine v3 and leaves small files behind, so Iceberg `OPTIMIZE` and `VACUUM` should run from time to time. A `unique` test on each natural key catches any regression.
