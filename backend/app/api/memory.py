from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.projects import resolve_project_id
from app.db.session import get_session
from app.models.memory import MemoryChunk, MemoryEmbedding, MemoryItem
from app.models.tasks import TaskRun
from app.schemas.memory import (
    MemoryItemCreate,
    MemoryItemRead,
    SemanticSearchHit,
    SemanticSearchIn,
    SemanticSearchOut,
)
from app.services.audit import record as audit_record
from app.services.redaction import redact

router = APIRouter(prefix="/projects/{slug}/memory", tags=["memory"])


@router.get("", response_model=list[MemoryItemRead])
async def list_memory(
    slug: str,
    kind: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=50, le=500),
    session: AsyncSession = Depends(get_session),
):
    pid = await resolve_project_id(slug, session)
    stmt = select(MemoryItem).where(MemoryItem.project_id == pid)
    if kind:
        stmt = stmt.where(MemoryItem.kind == kind)
    if q:
        # Simple ILIKE search; FTS index also exists.
        like = f"%{q}%"
        stmt = stmt.where(
            (MemoryItem.body.ilike(like)) | (MemoryItem.title.ilike(like))
        )
    stmt = stmt.order_by(MemoryItem.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return [MemoryItemRead.model_validate(m) for m in result.scalars()]


@router.post("", response_model=MemoryItemRead, status_code=201)
async def create_memory(
    slug: str, body: MemoryItemCreate, session: AsyncSession = Depends(get_session)
):
    pid = await resolve_project_id(slug, session)
    # Redact BEFORE persisting.
    safe_body = redact(body.body)
    item = MemoryItem(
        project_id=pid,
        kind=body.kind,
        title=body.title,
        body=safe_body,
        tags=body.tags,
    )
    session.add(item)
    await session.flush()
    # Enqueue an embedding task for the worker.
    session.add(
        TaskRun(
            project_id=pid,
            kind="memory.embed",
            payload={"memory_item_id": item.id},
        )
    )
    await audit_record(
        session,
        event_type="memory.created",
        project_id=pid,
        payload={"id": item.id, "kind": item.kind},
    )
    await session.commit()
    await session.refresh(item)
    return MemoryItemRead.model_validate(item)


@router.post("/search/semantic", response_model=SemanticSearchOut)
async def semantic_search(
    slug: str, body: SemanticSearchIn, session: AsyncSession = Depends(get_session)
):
    pid = await resolve_project_id(slug, session)
    # Lazy import — embeddings model is heavy.
    try:
        from app.services.embeddings import EmbeddingService

        qvec = EmbeddingService.embed_one(body.query)
    except Exception:
        return SemanticSearchOut(hits=[])

    # pgvector cosine distance using <-> with vector_cosine_ops index.
    stmt = text(
        """
        SELECT mc.id AS chunk_id,
               mi.id AS memory_item_id,
               mc.text AS text,
               (me.embedding <=> CAST(:qvec AS vector)) AS distance
        FROM memory_embeddings me
        JOIN memory_chunks mc ON mc.id = me.chunk_id
        JOIN memory_items mi ON mi.id = mc.memory_item_id
        WHERE mi.project_id = :pid
        ORDER BY me.embedding <=> CAST(:qvec AS vector)
        LIMIT :k
        """
    )
    # Pass the vector as a Postgres array literal string for pgvector.
    qvec_str = "[" + ",".join(f"{x:.6f}" for x in qvec) + "]"
    rows = (await session.execute(stmt, {"qvec": qvec_str, "pid": pid, "k": body.top_k})).mappings().all()
    hits = [
        SemanticSearchHit(
            memory_item_id=r["memory_item_id"],
            chunk_id=r["chunk_id"],
            score=float(1.0 - r["distance"]),
            text=r["text"],
        )
        for r in rows
    ]
    return SemanticSearchOut(hits=hits)
