.PHONY: verify verify-layer-a verify-layer-b screenshot help \
        ui-start ui-stop ui-status ui-logs ui-smoke ui-test load

help:
	@grep -E '^[a-zA-Z_-]+:.*?## ' Makefile | awk 'BEGIN{FS=":.*?## "}{printf "  %-22s %s\n", $$1, $$2}'

verify: ## Run the full verification stack (Layer A + Layer B + bundling summary)
	@bash scripts/run_project_verification.sh

verify-layer-a: ## Run only the Playwright browser audit (Layer A)
	@npm --prefix e2e run audit

verify-layer-b: ## Run only the CLI probes (Layer B)
	@for probe in verification/probes/*; do \
	  case "$$probe" in *_common.sh) continue;; esac; \
	  echo "==> $$probe"; "$$probe" || exit $$?; \
	done

screenshot: ## Take a screenshot of a route. Usage: make screenshot ROUTE=/audit [THEME=dark|light]
	@npm --prefix e2e run screenshot -- --route "$(ROUTE)" $(if $(THEME),--theme $(THEME),)

# --- UI control CLI (agentos ui ...) --------------------------------------
ui-start: ## Launch persistent browser daemon for `agentos ui`
	@.venv/bin/agentos ui start

ui-stop: ## Stop the persistent browser daemon
	@.venv/bin/agentos ui stop

ui-status: ## Print agentos ui session status
	@.venv/bin/agentos ui status

ui-logs: ## Tail the persistent browser daemon log
	@.venv/bin/agentos ui logs --tail 50

ui-smoke: ## Drive every route and screenshot it (per-developer sanity sweep)
	@.venv/bin/agentos ui smoke

ui-test: ## Run the ui-control parity test suite
	@env -u PYTHONPATH .venv/bin/pytest tests/ui_control/ -v

# --- Load & performance ---------------------------------------------------
load: ## Run k6 load test suite (BLOCKED if k6 not installed)
	@bash tests/load/run_all.sh
