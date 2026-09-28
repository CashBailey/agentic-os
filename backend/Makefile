PY ?= python3
PIP ?= pip

.PHONY: install db-up db-setup migrate serve worker test smoke

install:
	$(PIP) install -e ".[dev]"

db-up:
	cd .. && docker compose up -d db

db-setup:
	@echo "Manual Postgres setup (if not using docker):"
	@echo "  - Install Postgres 16 + pgvector + pg_trgm extensions"
	@echo "  - createdb agentos; createuser agentos --pwprompt"
	@echo "  - psql agentos -c 'CREATE EXTENSION vector; CREATE EXTENSION pg_trgm;'"
	@echo "  - Set DATABASE_URL=postgresql+psycopg://agentos:agentos@127.0.0.1:5432/agentos"

migrate:
	alembic upgrade head

serve:
	uvicorn app.main:app --host 127.0.0.1 --port 8000

worker:
	$(PY) -m app.worker

test:
	cd .. && pytest tests/backend -v -m "not db"

smoke:
	curl -s http://127.0.0.1:8000/healthz; echo
	curl -s http://127.0.0.1:8000/auth-status; echo
