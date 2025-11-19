.DEFAULT_GOAL := help

# Keep uv caches inside the repo to avoid permission issues on systems that sandbox
# access to user-level cache directories.
UV_CACHE_DIR ?= $(CURDIR)/.uv-cache
export UV_CACHE_DIR

.PHONY: help
help: ## Show available make targets.
	@echo "Available make targets:"
	@awk 'BEGIN { FS = ":.*## " } /^[A-Za-z0-9_.-]+:.*## / { printf "  %-20s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

.PHONY: prepare
prepare: ## Sync dependencies using locked versions.
	uv sync --frozen

.PHONY: format
format: ## Auto-format Python sources with ruff.
	uv run ruff check --fix
	uv run ruff format

.PHONY: check
check: ## Run linting and type checks.
	uv run ruff check
	uv run ruff format
	uv run pyright

.PHONY: test
test: ## Run the test suite with pytest.
	uv run pytest -vv

.PHONY: clean
clean: ## Remove local cache and build artifacts.
	rm -rf .ruff_cache .pytest_cache .pyright .mypy_cache build dist .uv-cache
	find . -path './.venv' -prune -o -name '__pycache__' -type d -exec rm -rf {} +
