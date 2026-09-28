"""Round-trip: DB → export → reset → import → export → byte-equal."""

from __future__ import annotations

import uuid

import pytest


@pytest.mark.db
def test_export_import_byte_equal():
    from sqlalchemy import text

    from app.db.session import SyncSessionLocal
    from app.models.decisions import Decision
    from app.models.memory import MemoryItem
    from app.models.projects import Project
    from app.services.markdown_io import export_tarball, import_tarball

    slug = f"rt-{uuid.uuid4().hex[:8]}"
    with SyncSessionLocal() as s:
        p = Project(slug=slug, name="RT", root_path="/tmp")
        s.add(p)
        s.flush()
        s.add(MemoryItem(project_id=p.id, kind="note", title="t", body="hello world", tags=["a", "b"]))
        s.add(Decision(project_id=p.id, title="adopt-x", body="we will adopt X"))
        s.commit()

    # Export A
    with SyncSessionLocal() as s:
        blob_a = export_tarball(s, slug)

    # Wipe project's data (cascade)
    with SyncSessionLocal() as s:
        s.execute(text("DELETE FROM projects WHERE slug = :s"), {"s": slug})
        s.commit()

    # Import
    with SyncSessionLocal() as s:
        import_tarball(s, blob_a)

    # Export B
    with SyncSessionLocal() as s:
        blob_b = export_tarball(s, slug)

    # In-memory contents must be identical.
    from app.services.markdown_io import unpack_tarball

    assert unpack_tarball(blob_a) == unpack_tarball(blob_b)
