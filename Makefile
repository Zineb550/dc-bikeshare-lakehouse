.DEFAULT_GOAL := help

AWS_REGION ?= us-east-1
ACCOUNT_ID = $(shell aws sts get-caller-identity --query Account --output text)
ECR_REGISTRY = $(ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com
ECR_REPO = $(ECR_REGISTRY)/dc-bikeshare-ingest
VENV = .venv
.PHONY: help setup lint update-hooks venv test tf-init tf-plan tf-apply tf-destroy tf-validate \
	tf-apply-ecr image-push invoke-gbfs invoke-trips invoke-weather deploy-image \
	airflow-start airflow-stop airflow-test airflow-parse

help: ## List available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

setup: ## Install the git hooks (pre-commit and commit-msg)
	pre-commit install --install-hooks

lint: ## Run every pre-commit check on all files
	pre-commit run --all-files

update-hooks: ## Bump pre-commit hooks to their latest versions
	pre-commit autoupdate

tf-init: ## Terraform init (downloads the AWS provider)
	terraform -chdir=infra init

tf-validate: ## Terraform format check and validate
	terraform -chdir=infra fmt -check -recursive
	terraform -chdir=infra validate

tf-plan: ## Show what Terraform would change
	terraform -chdir=infra plan -out=bikeshare.tfplan

tf-apply: ## Apply the plan saved by tf-plan
	terraform -chdir=infra apply bikeshare.tfplan

tf-destroy: ## Delete every resource this project created
	terraform -chdir=infra destroy

venv: ## Create .venv and install the ingestion package with test dependencies
	python3.12 -m venv $(VENV)
	$(VENV)/bin/pip install -q --upgrade pip
	$(VENV)/bin/pip install -q -e "ingestion[dev]"

test: ## Run the ingestion unit tests
	$(VENV)/bin/pytest ingestion -q

tf-apply-ecr: ## First deploy only: create the ECR repository before any image exists
	terraform -chdir=infra apply -target=aws_ecr_repository.ingest -target=aws_ecr_lifecycle_policy.ingest

image-push: ## Build the ingest image for Lambda (amd64) and push it as :latest
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(ECR_REGISTRY)
	docker build --platform linux/amd64 --provenance=false -t $(ECR_REPO):latest ingestion
	docker push $(ECR_REPO):latest

invoke-gbfs: ## Run one GBFS collection now (manual mode, includes station information)
	aws lambda invoke --function-name dc-bikeshare-ingest --cli-binary-format raw-in-base64-out \
		--payload '{"source": "gbfs", "mode": "manual", "force_info": true}' /dev/stdout

invoke-trips: ## Load one trip month into bronze, e.g. make invoke-trips MONTH=2026-08
	@test -n "$(MONTH)" || (echo "Usage: make invoke-trips MONTH=YYYY-MM" && exit 1)
	aws lambda invoke --function-name dc-bikeshare-ingest --cli-binary-format raw-in-base64-out \
		--cli-read-timeout 310 --payload '{"source": "trips", "month": "$(MONTH)"}' /dev/stdout

invoke-weather: ## Fetch the last 7 days of weather (forecast mode)
	aws lambda invoke --function-name dc-bikeshare-ingest --cli-binary-format raw-in-base64-out \
		--payload '{"source": "weather", "mode": "forecast"}' /dev/stdout

deploy-image: image-push tf-plan ## Push a new image, then plan (review it, then make tf-apply)

airflow-start: ## Start local Airflow (UI on http://localhost:8080)
	cd airflow && astro dev start

airflow-stop: ## Stop local Airflow and free its memory (collection keeps running in AWS)
	cd airflow && astro dev stop

airflow-test: ## Run the DAG integrity and helper tests inside the Airflow image
	cd airflow && astro dev pytest tests

airflow-parse: ## Check that every DAG imports without errors
	cd airflow && astro dev parse

# --- dbt: runs locally with the Airflow user's credentials from airflow/.env ---
DBT_VENV = .venv-dbt
DBT = cd airflow/dbt && set -a && . ../.env && set +a && DBT_PROFILES_DIR=. ../../$(DBT_VENV)/bin/dbt

.PHONY: dbt-venv dbt
dbt-venv: ## Create .venv-dbt with the pinned dbt-core and dbt-athena
	python3.12 -m venv $(DBT_VENV)
	$(DBT_VENV)/bin/pip install -q --upgrade pip
	$(DBT_VENV)/bin/pip install -q -r airflow/dbt/requirements.txt

dbt: ## Run dbt against Athena, e.g. make dbt ARGS="build -s staging"
	$(DBT) $(ARGS)

# --- Metabase (group 9): never run together with Airflow ---
.PHONY: metabase-start metabase-stop
metabase-start: ## Start Metabase on http://localhost:3000 (stop Airflow first)
	docker compose -f dashboards/docker-compose.metabase.yml up -d

metabase-stop: ## Stop Metabase
	docker compose -f dashboards/docker-compose.metabase.yml down
