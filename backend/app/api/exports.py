from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SyncSessionLocal, get_session
from app.services.markdown_io import export_tarball, import_tarball

router = APIRouter(tags=["exports"])


@router.get("/export/markdown")
async def export_markdown(project: str | None = Query(default=None)):
    # Use sync session inside a thread to avoid mixing async + heavy file ops.
    def _do() -> bytes:
        with SyncSessionLocal() as s:
            return export_tarball(s, project)

    import anyio

    blob = await anyio.to_thread.run_sync(_do)
    return StreamingResponse(
        BytesIO(blob),
        media_type="application/x-tar",
        headers={"Content-Disposition": "attachment; filename=agentos-export.tar"},
    )


@router.post("/import/markdown")
async def import_markdown(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),  # noqa: ARG001 (use sync below)
):
    blob = await file.read()

    def _do() -> dict:
        with SyncSessionLocal() as s:
            return import_tarball(s, blob)

    import anyio

    counts = await anyio.to_thread.run_sync(_do)
    return {"imported": counts}
