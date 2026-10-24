# Runbook

Day-to-day operations, alert responses, and teardown. All commands run from the repository root unless noted.

## Daily use

| Task | Command |
| --- | --- |
| Start Airflow (UI on http://localhost:8080) | `make airflow-start` |
| Stop Airflow | `make airflow-stop` |
| Start Metabase (http://localhost:3000) | `make metabase-start` (stop Airflow first: both need RAM) |
| Stop Metabase | `make metabase-stop` |
| Run dbt by hand | `make dbt ARGS="build --select <model>"` |
| Collect one GBFS snapshot now | `make invoke-gbfs` |

GBFS collection runs in AWS every 15 minutes whether the laptop is on or off. Starting Airflow catches up any missed daily runs automatically (`catchup=True`, one run at a time).

## Alerts

All alerts arrive by email through the SNS topic `bikeshare-alerts`.

### `dc-bikeshare-ingest-errors`: the Lambda failed

1. Open CloudWatch → Log groups → `/aws/lambda/dc-bikeshare-ingest` and read the latest error.
2. Check the run log in Athena:
   ```sql
   select started_at, source, status, error
   from ops.run_log
   where status <> 'ok'
   order by started_at desc
   limit 20;
   ```
3. A source outage (HTTP 5xx, timeout) usually fixes itself at the next slot. A code error needs a fix and a new image: `make deploy-image`, review the plan, then `make tf-apply`.

### `dc-bikeshare-collection-heartbeat`: no collection for 30 minutes

The schedule stopped or the function cannot be invoked.

1. Check that `collection_enabled` is `true` in `infra/terraform.tfvars`.
2. EventBridge → Schedules → `dc-bikeshare-gbfs-15min` must be **Enabled**.
3. Run `make invoke-gbfs`. If it works, the problem is the schedule or its IAM role; `make tf-plan` shows any drift.

Snapshots missed during an outage cannot be recovered: GBFS is a live feed.

### Quarantined payload

A payload failed validation and was written to `quarantine/<source>/dt=YYYY-MM-DD/` instead of bronze (kept 30 days). Download it, compare it with the expected format, and fix the validation or the parser. Once fixed, replay the source for that period (`make invoke-trips MONTH=YYYY-MM` for trips).

### Airflow task failure or failed dbt test

1. Open the failed task log in the Airflow UI. dbt prints the failing model or test.
2. For a test failure, run the compiled test query from `airflow/dbt/target/compiled/` in Athena to see the offending rows.
3. After the fix, clear the failed task in the UI (or run `make dbt ARGS="build --select <model>+"`).

### Trip file late

`trips_monthly` waits up to 12 days after the 1st for the previous month's file, checking every 6 hours. If it times out, check the Capital Bikeshare data page; when the file appears, clear the DAG run to start again.

## Monthly tasks

- **After the new trip file lands** (early in the month): check that `trips_monthly` succeeded, then check Q3 (`gold.station_rebalancing_priority`). Its demand comes from the latest complete trip month, so the ranking changes when a new month arrives.
- **Iceberg maintenance** (every few months): run `OPTIMIZE <table> REWRITE DATA USING BIN_PACK` and `VACUUM <table>` in Athena on the silver tables to compact the small files left by MERGE.

## Rotate an access key

```bash
aws iam create-access-key --user-name dc-bikeshare-airflow
# put the new key in airflow/.env, restart Airflow, check a run, then:
aws iam delete-access-key --user-name dc-bikeshare-airflow --access-key-id <OLD_KEY_ID>
```

For Metabase, use `dc-bikeshare-metabase` and update the key in Metabase → Admin → Databases → the Athena connection.

## Teardown and re-apply

`make tf-destroy` deletes every project resource, **including the lake bucket and all its data**. Bronze GBFS snapshots cannot be downloaded again, so back them up first.

### 1. Back up bronze

```bash
BUCKET=$(terraform -chdir=infra output -raw lake_bucket)
aws s3 sync s3://$BUCKET/bronze/ data/backup/bronze/
aws s3 sync s3://$BUCKET/ops/ data/backup/ops/
```

`data/` is gitignored, so the backup never reaches the repository.

### 2. Delete the access keys created with the CLI

Terraform cannot delete an IAM user that still has access keys it did not create.

```bash
for user in dc-bikeshare-airflow dc-bikeshare-metabase; do
  for key in $(aws iam list-access-keys --user-name $user --query 'AccessKeyMetadata[].AccessKeyId' --output text); do
    aws iam delete-access-key --user-name $user --access-key-id $key
  done
done
```

### 3. Destroy

```bash
make airflow-stop
make metabase-stop
make tf-destroy
```

Collection stops from this moment until the re-apply.

### 4. Re-apply

Follow **Setup** in the README from step 3 (`make tf-init` onward). The bucket name derives from the account ID, so it is the same as before.

### 5. Restore bronze and rebuild

```bash
BUCKET=$(terraform -chdir=infra output -raw lake_bucket)
aws s3 sync data/backup/bronze/ s3://$BUCKET/bronze/
aws s3 sync data/backup/ops/ s3://$BUCKET/ops/
```

Then recreate silver and gold from bronze. Airflow remembers its past runs, so ask it to run them again:

```bash
cd airflow
astro dev run backfill create --dag-id trips_monthly --from-date 2026-05-01 --to-date <today> --reprocess-behavior completed
astro dev run backfill create --dag-id daily_pipeline --from-date 2026-04-02 --to-date <today> --reprocess-behavior completed
```

Check the result with the row-count query in the README: the counts must match the ones recorded before the teardown.
