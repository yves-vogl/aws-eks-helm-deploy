.PHONY: bootstrap lint type-check unit integration integration-test acceptance acceptance-test all

## bootstrap: install uv (if missing), sync all extras, install pre-commit hooks
bootstrap:
	@command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
	uv sync --all-extras
	uv run pre-commit install --install-hooks

## lint: run ruff check + format check on src/ and tests/
lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

## type-check: run mypy --strict on src/
type-check:
	uv run mypy --strict src

## unit: run the unit tier with 100% line+branch coverage gate (TOOL-06)
unit:
	uv run pytest

## integration: run the integration tier (requires kind + helm on PATH)
integration:
	uv run pytest -m integration --no-cov

## integration-test: alias for integration target
integration-test: integration

## acceptance: run the acceptance tier (requires docker; builds image from Dockerfile)
acceptance:
	uv run pytest -m acceptance --no-cov

## acceptance-test: alias for acceptance target
acceptance-test: acceptance

## all: run lint + type-check + unit (standard CI gate)
all: lint type-check unit
