.PHONY: validate test test-all clean help drift-check update-recipes

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

validate: ## Run JSON schema validation on all recipes
	@test -d .venv || python3 -m venv .venv
	@.venv/bin/pip install -r tests/requirements.txt -q
	@.venv/bin/python3 tests/validate_recipes.py

test: ## Run integration test (requires Docker or Podman)
	@tests/integration_test.sh

MC_VERSION ?= latest-release

drift-check: ## Check recipes and pack format against vanilla (MC_VERSION=latest-release|latest-snapshot|<id>)
	@test -d .venv || python3 -m venv .venv
	@.venv/bin/python3 scripts/extract_vanilla_recipes.py --version $(MC_VERSION)

update-recipes: ## Regenerate recipes and bump pack format from vanilla (MC_VERSION=...)
	@test -d .venv || python3 -m venv .venv
	@.venv/bin/python3 scripts/extract_vanilla_recipes.py --version $(MC_VERSION) --update

test-all: validate test ## Run all tests (schema + integration)

clean: ## Remove containers and test artifacts
	@cd tests && (podman compose down -v 2>/dev/null || docker compose down -v 2>/dev/null || true)
	@rm -rf tests/server-data
