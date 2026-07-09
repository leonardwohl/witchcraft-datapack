.PHONY: validate test test-all clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

validate: ## Run JSON schema validation on all recipes
	@test -d .venv || python3 -m venv .venv
	@.venv/bin/pip install -r tests/requirements.txt -q
	@.venv/bin/python3 tests/validate_recipes.py

test: ## Run Docker integration test (requires Docker)
	@tests/integration_test.sh

test-all: validate test ## Run all tests (schema + integration)

clean: ## Remove Docker containers and test artifacts
	@cd tests && docker compose down -v 2>/dev/null || true
	@rm -rf tests/server-data
