# ADR-0008: Join trips to stations through GBFS `short_name`

- **Status:** accepted
- **Date:** 2026-10-20

## Context

Trip files and GBFS feeds identify stations differently. GBFS uses a `station_id` (a UUID or a long number), while trip files carry the station code that GBFS exposes as `short_name`.

## Decision

Resolve trip start and end stations to GBFS `station_id` by joining on `short_name`. A dbt test (`crosswalk_rate`) checks, per source month, the share of docked trips that resolve.

## Alternatives rejected

| Alternative | Why rejected |
| --- | --- |
| Join on station name | Names change and are spelled inconsistently. |
| Join on coordinates | Nearby stations would collide; coordinates in trip files are rounded. |

## Consequences

The match was measured at 100% on August 2026 trips. If the operator changes station codes, the crosswalk test fails and alerts before KPIs drift. Stations are type 1 (latest attributes only), so historical renames are not kept.
