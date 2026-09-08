.DEFAULT_GOAL := help
SHELL := /bin/bash

.PHONY: help`
help:
	@grep -E \
		'^.PHONY: .*?## .*$$' $(MAKEFILE_LIST) | \
		sort | \
		awk 'BEGIN {FS = ".PHONY: |## "}; {printf "\033[36m%-16s\033[0m %s\n", $$2, $$3}'

.PHONY: install ## install required dependencies on bare metal
install:
	uv sync --refresh
	uv run pre-commit install

.PHONY: format ## Run the formatter on bare metal
format:
	uv run ruff format
	uv run ruff check --fix

.PHONY: lint ## run the linter on bare metal
lint:
	uv run ruff check
	uv run ruff format --check

.PHONY: test ## run unit tests on bare metal
test:
	uv run python -m pytest -v -m "not integration"
