# Cost

Expected spend is about **$1–2 per month**. The main risk is not the bill itself but a runaway query or a forgotten resource, so every service has a guardrail.

| Service | Expected usage | Guardrail |
| --- | --- | --- |
| Lambda | ~2,900 invocations a month (one every 15 minutes, plus trips and weather) | Inside the always-free tier of 1 million requests |
| S3 | Under 1 GB in total (~55 MB a month of GBFS snapshots) | Lifecycle rules: `athena-results/` expires after 7 days, `quarantine/` after 30 |
| Athena | Number of queries × 10 MB minimum billed per query | 1 GB per-query scan cap enforced by the `bikeshare` workgroup; Metabase reads gold and silver only |
| CloudWatch Logs | Small | 14-day retention on the Lambda log group |
| ECR | One image of ~300 MB | Lifecycle policy keeps the last 3 images |
| NAT Gateway | $0 | Lambda runs outside any VPC |
| Airflow, dbt, Metabase | $0 | Run locally in Docker |

## Alerts

- **AWS Budget** `bikeshare-monthly`, set by `monthly_budget_usd` (default $5), emails at 50%, 80% and 100% of actual spend, and when the forecast exceeds 100%.
- **SNS topic** `bikeshare-alerts` receives Lambda errors, the collection heartbeat alarm, Airflow task failures and failed dbt tests.

## Check the real spend

AWS console → **Billing and Cost Management** → **Cost Explorer**, filtered on the tag `Project = dc-bikeshare-lakehouse` (every Terraform resource carries it through `default_tags`).

## Pause or stop

- Pause collection without deleting anything: set `collection_enabled = false` in `infra/terraform.tfvars`, then `make tf-plan` and `make tf-apply`.
- Remove everything: see the teardown section of [runbook.md](runbook.md).
