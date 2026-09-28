from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.projects import resolve_project_id
from app.db.session import get_session
from app.models.context import ContextDocument
from app.schemas.context import ContextDocumentRead, ContextDocumentUpdate

router = APIRouter(prefix="/projects/{slug}/context", tags=["context"])


@router.get("", response_model=list[ContextDocumentRead])
async def list_context(slug: str, session: AsyncSession = Depends(get_session)):
    pid = await resolve_project_id(slug, session)
    result = await session.execute(
        select(ContextDocument).where(
            or_(
                ContextDocument.project_id == pid,
                ContextDocument.scope == "global",
            )
        )
    )
    return [ContextDocumentRead.model_validate(d) for d in result.scalars()]


@router.put("/{doc_id}", response_model=ContextDocumentRead)
async def update_context(
    slug: str,
    doc_id: int,
    body: ContextDocumentUpdate,
    session: AsyncSession = Depends(get_session),
):
    await resolve_project_id(slug, session)
    result = await session.execute(select(ContextDocument).where(ContextDocument.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "document not found")
    doc.content = body.content
    if body.frontmatter is not None:
        doc.frontmatter = body.frontmatter
    doc.content_hash = hashlib.sha256(body.content.encode("utf-8")).hexdigest()
    await session.commit()
    await session.refresh(doc)
    return ContextDocumentRead.model_validate(doc)
