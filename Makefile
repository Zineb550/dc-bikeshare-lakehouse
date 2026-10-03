.DEFAULT_GOAL := help
.PHONY: help setup lint update-hooks

help: ## List available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

setup: ## Install the git hooks (pre-commit and commit-msg)
	pre-commit install --install-hooks

lint: ## Run every pre-commit check on all files
	pre-commit run --all-files

update-hooks: ## Bump pre-commit hooks to their latest versions
	pre-commit autoupdate
