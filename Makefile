.DEFAULT_GOAL := help

AWS_REGION ?= us-east-1
ACCOUNT_ID = $(shell aws sts get-caller-identity --query Account --output text)
ECR_REGISTRY = $(ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com
ECR_REPO = $(ECR_REGISTRY)/dc-bikeshare-ingest
VENV = .venv
.PHONY: help setup lint update-hooks venv test tf-init tf-plan tf-apply tf-destroy tf-validate \
	tf-apply-ecr image-push invoke-gbfs

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
