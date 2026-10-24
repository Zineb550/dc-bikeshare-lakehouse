# ADR-0007: File-level quarantine, row-level flags

- **Status:** accepted
- **Date:** 2026-10-03

## Context

Bad data comes in two forms. A whole payload can be unusable (invalid JSON, missing fields, wrong station count). Or a few rows inside a good file can be odd (a ride shorter than 1 minute or longer than 24 hours, a stale station snapshot).

## Decision

At ingestion, a payload that fails validation goes to `quarantine/` (kept 30 days) and triggers an SNS alert; it never reaches bronze. In silver, odd rows are kept and flagged (`is_short`, `is_long`, `is_stale`, dockless flags), and gold KPIs filter on those flags.

## Alternatives rejected

| Alternative | Why rejected |
| --- | --- |
| Drop odd rows in silver | Loses information; filters cannot be changed later. |
| Quarantine individual rows | Splits files and makes reprocessing harder for little benefit. |

## Consequences

Bronze only contains payloads that passed validation, and every exclusion in gold is visible and reversible. Quarantined files can be inspected and replayed by hand.
