# Agentic OS Backend

FastAPI + SQLAlchemy 2.x async + Alembic + Postgres + pgvector. Bound to
`127.0.0.1:8000` only — no auth (single-user local control plane).

## Quick start

```
cd backend
pip install -e ".[dev,embeddings]"
cd .. && docker compose up -d db && sleep 8
cd backend
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000
# in another shell
python -m app.worker
```

## Tests

```
cd ..  # repo root
pytest tests/backend -v -m "not db"   # unit tests, no DB needed
pytest tests/backend -v -m db         # requires running Postgres
```
