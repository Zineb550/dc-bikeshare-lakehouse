# ADR-0005: Full rebuild for gold tables

- **Status:** accepted
- **Date:** 2026-10-21

## Context

Gold tables are small aggregates (one row per station, per station × hour, or per day). Several use windows over the whole history: percentiles, trailing 28 days, gaps-and-islands streaks. Updating them incrementally would require tracking which aggregates a new row affects.

## Decision

Rebuild every gold table from silver on each run (dbt `table` materialization).

## Alternatives rejected

| Alternative | Why rejected |
| --- | --- |
| Incremental gold | Complex logic to recompute affected windows; a subtle bug would silently corrupt KPIs. |

## Consequences

Gold is always consistent with silver, and a logic fix applies to the whole history on the next run. Each run scans silver again, which is cheap at this volume (a few million rows). If volumes grew by orders of magnitude, the heaviest tables would need to become incremental.
