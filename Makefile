.DEFAULT_GOAL := help
PY ?= python

.PHONY: help install lint format typecheck test cov check demo clean

help:  ## List targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

install:  ## Editable install with all extras and dev tools, plus git hooks
	$(PY) -m pip install -e ".[dev]"
	pre-commit install

lint:  ## Lint and check formatting
	ruff check .
	ruff format --check .

format:  ## Auto-fix lint issues and format
	ruff check --fix .
	ruff format .

typecheck:  ## Strict mypy over src/
	mypy

test:  ## Run the test suite
	pytest

cov:  ## Run tests with branch coverage
	pytest --cov --cov-report=term-missing

check: lint typecheck cov  ## Everything CI runs

demo:  ## Regenerate the README chart
	trading-backtest --config config/demo.yaml --save-chart docs/images/backtest.png

clean:  ## Remove caches and build artifacts
	rm -rf build dist *.egg-info src/*.egg-info .pytest_cache .mypy_cache .ruff_cache .hypothesis .coverage htmlcov
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
