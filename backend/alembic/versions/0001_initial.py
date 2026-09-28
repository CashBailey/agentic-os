"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-28
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')

    # projects
    op.create_table(
        "projects",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("slug", sa.Text, unique=True, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("root_path", sa.Text, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # context_documents
    op.create_table(
        "context_documents",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("scope", sa.Text, nullable=False),
        sa.Column("category", sa.Text, nullable=False),
        sa.Column("path", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("frontmatter", postgresql.JSONB, nullable=True),
        sa.Column("content_hash", sa.Text, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("project_id", "scope", "path", name="uq_ctx_proj_scope_path"),
    )
    op.create_index("context_documents_project_scope", "context_documents", ["project_id", "scope"])
    op.execute(
        "CREATE INDEX context_documents_fts ON context_documents USING gin (to_tsvector('english', content));"
    )

    # memory_items
    op.create_table(
        "memory_items",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("memory_items_project_kind", "memory_items", ["project_id", "kind"])
    op.execute(
        "CREATE INDEX memory_items_fts ON memory_items USING gin (to_tsvector('english', coalesce(title,'') || ' ' || body));"
    )

    # memory_chunks
    op.create_table(
        "memory_chunks",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("memory_item_id", sa.BigInteger, sa.ForeignKey("memory_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("text_hash", sa.Text, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("memory_chunks_item", "memory_chunks", ["memory_item_id"])

    # memory_embeddings
    op.create_table(
        "memory_embeddings",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("chunk_id", sa.BigInteger, sa.ForeignKey("memory_chunks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_name", sa.Text, nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("chunk_id", "model_name", name="uq_mem_emb_chunk_model"),
    )
    op.execute(
        "CREATE INDEX memory_embeddings_ann ON memory_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);"
    )

    # decisions
    op.create_table(
        "decisions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # session_summaries
    op.create_table(
        "session_summaries",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # task_runs
    op.create_table(
        "task_runs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="queued"),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("result", postgresql.JSONB, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("claimed_by", sa.Text, nullable=True),
        sa.Column("claimed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="3"),
        sa.Column("timeout_seconds", sa.Integer, nullable=False, server_default="600"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute(
        "CREATE INDEX task_runs_claim ON task_runs(status, created_at) WHERE status IN ('queued','claimed','running');"
    )

    # task_steps
    op.create_table(
        "task_steps",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("task_run_id", sa.BigInteger, sa.ForeignKey("task_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("log", sa.Text, nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # approval_requests
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("tool", sa.Text, nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("raw_input", postgresql.JSONB, nullable=False),
        sa.Column("normalized", postgresql.JSONB, nullable=True),
        sa.Column("risk", sa.Text, nullable=True),
        sa.Column("agent_reason", sa.Text, nullable=True),
        sa.Column("policy_reason", sa.Text, nullable=True),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column(
            "release_token",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("approval_requests_status", "approval_requests", ["status", "expires_at"])

    # approval_decisions
    op.create_table(
        "approval_decisions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "approval_request_id",
            sa.BigInteger,
            sa.ForeignKey("approval_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("decision", sa.Text, nullable=False),
        sa.Column("decided_by", sa.Text, nullable=False, server_default="user"),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("execution_result", postgresql.JSONB, nullable=True),
    )

    # audit_events
    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("actor", sa.Text, nullable=True),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute(
        "CREATE INDEX audit_events_project_time ON audit_events(project_id, occurred_at DESC);"
    )

    # adapter_generations
    op.create_table(
        "adapter_generations",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("cli", sa.Text, nullable=False),
        sa.Column("generated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source_hash", sa.Text, nullable=False),
        sa.Column("output_hash", sa.Text, nullable=False),
        sa.Column("files", postgresql.JSONB, nullable=False),
    )

    # policy_evaluations
    op.create_table(
        "policy_evaluations",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("policy_kind", sa.Text, nullable=False),
        sa.Column("input", postgresql.JSONB, nullable=False),
        sa.Column("decision", sa.Text, nullable=False),
        sa.Column("matched_rule", postgresql.JSONB, nullable=True),
        sa.Column("evaluated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    for t in [
        "policy_evaluations",
        "adapter_generations",
        "audit_events",
        "approval_decisions",
        "approval_requests",
        "task_steps",
        "task_runs",
        "session_summaries",
        "decisions",
        "memory_embeddings",
        "memory_chunks",
        "memory_items",
        "context_documents",
        "projects",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE;")
