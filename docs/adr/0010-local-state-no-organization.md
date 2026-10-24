# ADR-0010: Local Terraform state, no AWS Organization

- **Status:** accepted
- **Date:** 2026-10-03

## Context

The project runs on a single AWS account on the Free plan, with one operator. Creating an AWS Organization or Control Tower upgrades the account to the Paid plan.

## Decision

Keep the Terraform state in a local file (gitignored, never committed). Use one account, an admin IAM user with MFA for Terraform, and dedicated IAM users for Airflow and Metabase.

## Alternatives rejected

| Alternative | Why rejected |
| --- | --- |
| Remote state in S3 with DynamoDB locking | Useful for a team, not for one operator; the bucket would itself need bootstrapping. |
| AWS Organization with separate dev and prod accounts | Upgrades the account to the Paid plan. |

## Consequences

Setup stays simple and free. The state file exists on one laptop only: losing it means importing resources or destroying them by hand. Access keys are created with the AWS CLI, so secrets never land in the state file.
