# ADR-0003: Raw bronze with partition projection, no crawlers

- **Status:** accepted
- **Date:** 2026-10-03

## Context

Bronze receives a new GBFS file every 15 minutes, partitioned by date. Athena must see new partitions immediately, without a scheduled job to register them.

## Decision

Keep bronze as raw files, exactly as received. Define the Glue tables in Terraform with partition projection, so Athena computes partition locations from the key pattern (`dt=YYYY-MM-DD`) at query time.

## Alternatives rejected

| Alternative | Why rejected |
| --- | --- |
| Glue crawlers | They run on a schedule, cost money per run, and can guess schemas wrongly. |
| `MSCK REPAIR TABLE` after each load | One more step that can be forgotten; slow as partitions grow. |
| Parsing GBFS into Parquet at ingestion | Loses the raw payload; any parsing bug would be permanent. |

## Consequences

New data is queryable the moment it lands, with no extra service. Bronze tables are versioned in Terraform. Parsing happens in dbt staging, so it can be fixed and replayed from raw files.
