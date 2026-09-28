from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.projects import Project
from app.schemas.projects import ProjectCreate, ProjectRead
from app.services.audit import record as audit_record

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectRead])
async def list_projects(session: AsyncSession = Depends(get_session)) -> list[ProjectRead]:
    result = await session.execute(select(Project).order_by(Project.id))
    return [ProjectRead.model_validate(p) for p in result.scalars()]


@router.post("", response_model=ProjectRead, status_code=201)
async def create_project(
    body: ProjectCreate, session: AsyncSession = Depends(get_session)
) -> ProjectRead:
    existing = await session.execute(select(Project).where(Project.slug == body.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "project slug already exists")
    p = Project(slug=body.slug, name=body.name, root_path=body.root_path)
    session.add(p)
    try:
        await session.flush()
        await audit_record(
            session,
            event_type="project.created",
            project_id=p.id,
            payload={"slug": p.slug, "name": p.name},
        )
        await session.commit()
    except IntegrityError:
        # A concurrent request won the slug between our pre-check SELECT and
        # this INSERT (TOCTOU). Surface the same clean 409 as the sequential
        # duplicate path instead of leaking a raw 500 from the DB driver.
        await session.rollback()
        raise HTTPException(409, "project slug already exists")
    await session.refresh(p)
    return ProjectRead.model_validate(p)


@router.get("/{slug}", response_model=ProjectRead)
async def get_project(slug: str, session: AsyncSession = Depends(get_session)) -> ProjectRead:
    result = await session.execute(select(Project).where(Project.slug == slug))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "project not found")
    return ProjectRead.model_validate(p)


async def resolve_project_id(slug: str, session: AsyncSession) -> int:
    result = await session.execute(select(Project.id).where(Project.slug == slug))
    pid = result.scalar_one_or_none()
    if pid is None:
        raise HTTPException(404, "project not found")
    return pid
