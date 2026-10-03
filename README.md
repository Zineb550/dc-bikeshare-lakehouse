# dc-bikeshare-lakehouse

A batch data platform on AWS that tracks Capital Bikeshare (Washington DC) station availability, trips and weather, and answers operational questions: where riders find no bike or no dock, how many rides that costs, where rebalancing trucks should go, and how weather and rider type shape demand.

> **Status:** under construction.

## Stack

| Layer | Tools |
| --- | --- |
| Ingestion | AWS Lambda (container image), EventBridge Scheduler |
| Storage | Amazon S3 (bronze / silver / gold), Apache Iceberg, Parquet |
| Catalog and SQL | AWS Glue Data Catalog, Amazon Athena |
| Transformation | dbt (dbt-athena) |
| Orchestration | Apache Airflow (Astro CLI) |
| Infrastructure | Terraform |
| Observability | CloudWatch, SNS, run log |
| Dashboard | Metabase |
| CI | GitHub Actions, pre-commit |

## Data sources and attribution

- **Capital Bikeshare** trip history and GBFS real-time feeds, used under the [Capital Bikeshare Data License Agreement](https://capitalbikeshare.com/data-license-agreement). This repository contains code only, no data files.
- **Weather data** by [Open-Meteo.com](https://open-meteo.com/), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## Development

Requires WSL2 or Linux, Python 3.12, Docker, Terraform, AWS CLI v2, Astro CLI and pre-commit.

```bash
make setup   # install git hooks
make lint    # run all pre-commit checks
```

## License

[MIT](LICENSE)
