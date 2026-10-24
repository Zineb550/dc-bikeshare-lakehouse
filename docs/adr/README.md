# Architecture Decision Records

One page per significant decision: context, decision, rejected alternative, consequence.
Copy `0000-template.md` to `NNNN-short-title.md` for each new record.

| ADR | Decision | Status |
| --- | --- | --- |
| [0001](0001-collection-outside-airflow.md) | Collect GBFS with EventBridge Scheduler and Lambda, outside Airflow | accepted |
| [0002](0002-one-container-image.md) | One container image for all ingestion handlers | accepted |
| [0003](0003-bronze-partition-projection.md) | Raw bronze with partition projection, no crawlers | accepted |
| [0004](0004-iceberg-merge-silver.md) | Iceberg MERGE for silver tables | accepted |
| [0005](0005-gold-full-rebuild.md) | Full rebuild for gold tables | accepted |
| [0006](0006-data-interval-windows.md) | Data-interval windows for idempotency | accepted |
| [0007](0007-quarantine-vs-flags.md) | File-level quarantine, row-level flags | accepted |
| [0008](0008-station-key-short-name.md) | Join trips to stations through GBFS `short_name` | accepted |
| [0009](0009-one-bucket-one-topic.md) | One S3 bucket with prefixes, one SNS topic | accepted |
| [0010](0010-local-state-no-organization.md) | Local Terraform state, no AWS Organization | accepted |
