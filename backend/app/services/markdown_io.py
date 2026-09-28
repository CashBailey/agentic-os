"""Canonical markdown tarball export/import.

The tarball is deterministic: entries sorted by name, mtime=0, uid/gid=0,
uname/gname="". This guarantees round-trip byte equality:
  DB -> export -> import -> export should produce identical bytes.

Layout inside the tarball:
  projects/<slug>/project.json                 (metadata)
  projects/<slug>/context/<doc.path>           (context_documents.content)
  projects/<slug>/memory/<id>.md               (memory_items as markdown)
  projects/<slug>/decisions/<id>.md            (decisions)
  projects/<slug>/sessions/<id>.md             (session_summaries)
  globals/context/<doc.path>                   (global-scope context docs)
"""

from __future__ import annotations

import io
import json
import tarfile
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.context import ContextDocument
from app.models.decisions import Decision
from app.models.memory import MemoryItem
from app.models.projects import Project
from app.models.sessions import SessionSummary
from app.services.redaction import redact


def _memory_md(item: MemoryItem) -> str:
    fm_lines = ["---"]
    fm_lines.append(f"kind: {item.kind}")
    if item.title:
        fm_lines.append(f"title: {item.title}")
    if item.tags:
        fm_lines.append("tags: [" + ", ".join(item.tags) + "]")
    fm_lines.append("---")
    return "\n".join(fm_lines) + "\n" + item.body.rstrip("\n") + "\n"


def _decision_md(d: Decision) -> str:
    return f"---\ntitle: {d.title}\n---\n{d.body.rstrip(chr(10))}\n"


def _session_md(s: SessionSummary) -> str:
    return f"---\nstarted_at: {s.started_at}\nended_at: {s.ended_at}\n---\n{s.summary.rstrip(chr(10))}\n"


def _project_json(p: Project) -> str:
    return json.dumps(
        {"slug": p.slug, "name": p.name, "root_path": p.root_path},
        sort_keys=True,
        ensure_ascii=False,
        indent=2,
    ) + "\n"


def _collect(session: Session, project_slug: str | None) -> dict[str, bytes]:
    files: dict[str, bytes] = {}

    project_q = select(Project)
    if project_slug:
        project_q = project_q.where(Project.slug == project_slug)
    projects = list(session.execute(project_q).scalars())
    project_ids_by_slug: dict[int, str] = {p.id: p.slug for p in projects}

    for p in projects:
        files[f"projects/{p.slug}/project.json"] = _project_json(p).encode("utf-8")

    # context_documents
    ctx_q = select(ContextDocument)
    if project_slug:
        ctx_q = ctx_q.where(
            (ContextDocument.project_id.in_(list(project_ids_by_slug.keys())))
            | (ContextDocument.scope == "global")
        )
    for doc in session.execute(ctx_q).scalars():
        if doc.scope == "global" or doc.project_id is None:
            key = f"globals/context/{doc.path}"
        else:
            slug = project_ids_by_slug.get(doc.project_id)
            if slug is None:
                continue
            key = f"projects/{slug}/context/{doc.path}"
        files[key] = doc.content.encode("utf-8")

    # memory_items — use content hash as filename so round-trip is stable across re-import.
    import hashlib

    mem_q = select(MemoryItem)
    if project_slug:
        mem_q = mem_q.where(MemoryItem.project_id.in_(list(project_ids_by_slug.keys())))
    for it in session.execute(mem_q).scalars():
        slug = project_ids_by_slug.get(it.project_id) if it.project_id else None
        prefix = f"projects/{slug}" if slug else "globals"
        body_bytes = _memory_md(it).encode("utf-8")
        fname = hashlib.sha256(body_bytes).hexdigest()[:16]
        files[f"{prefix}/memory/{fname}.md"] = body_bytes

    # decisions
    dec_q = select(Decision)
    if project_slug:
        dec_q = dec_q.where(Decision.project_id.in_(list(project_ids_by_slug.keys())))
    for d in session.execute(dec_q).scalars():
        slug = project_ids_by_slug.get(d.project_id) if d.project_id else None
        prefix = f"projects/{slug}" if slug else "globals"
        body_bytes = _decision_md(d).encode("utf-8")
        fname = hashlib.sha256(body_bytes).hexdigest()[:16]
        files[f"{prefix}/decisions/{fname}.md"] = body_bytes

    # session_summaries
    ses_q = select(SessionSummary)
    if project_slug:
        ses_q = ses_q.where(SessionSummary.project_id.in_(list(project_ids_by_slug.keys())))
    for s in session.execute(ses_q).scalars():
        slug = project_ids_by_slug.get(s.project_id) if s.project_id else None
        prefix = f"projects/{slug}" if slug else "globals"
        body_bytes = _session_md(s).encode("utf-8")
        fname = hashlib.sha256(body_bytes).hexdigest()[:16]
        files[f"{prefix}/sessions/{fname}.md"] = body_bytes

    return files


def export_tarball(session: Session, project_slug: str | None = None) -> bytes:
    files = _collect(session, project_slug)
    return pack_files(files)


def pack_files(files: dict[str, bytes]) -> bytes:
    """Deterministic tarball: sorted, mtime=0, uid/gid=0, owners blanked."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for name in sorted(files.keys()):
            data = files[name]
            ti = tarfile.TarInfo(name=name)
            ti.size = len(data)
            ti.mtime = 0
            ti.mode = 0o644
            ti.uid = 0
            ti.gid = 0
            ti.uname = ""
            ti.gname = ""
            ti.type = tarfile.REGTYPE
            tf.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


def unpack_tarball(blob: bytes) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    buf = io.BytesIO(blob)
    with tarfile.open(fileobj=buf, mode="r") as tf:
        for ti in tf.getmembers():
            if not ti.isfile():
                continue
            f = tf.extractfile(ti)
            if f is None:
                continue
            out[ti.name] = f.read()
    return out


def import_tarball(session: Session, blob: bytes) -> dict[str, int]:
    """Import a tarball into the DB. Replaces existing rows per (slug,path) for
    context_documents; creates new memory_items/decisions/session_summaries.

    Returns counts per kind.
    """
    files = unpack_tarball(blob)
    counts = {"projects": 0, "context": 0, "memory": 0, "decisions": 0, "sessions": 0}

    # First pass: projects.
    project_id_by_slug: dict[str, int] = {}
    for name, data in sorted(files.items()):
        parts = name.split("/")
        if len(parts) >= 3 and parts[0] == "projects" and parts[2] == "project.json":
            meta = json.loads(data.decode("utf-8"))
            slug = meta["slug"]
            existing = session.execute(
                select(Project).where(Project.slug == slug)
            ).scalar_one_or_none()
            if existing is None:
                p = Project(slug=slug, name=meta.get("name", slug), root_path=meta.get("root_path", "/"))
                session.add(p)
                session.flush()
                project_id_by_slug[slug] = p.id
            else:
                project_id_by_slug[slug] = existing.id
            counts["projects"] += 1

    # Second pass: everything else.
    for name, data in sorted(files.items()):
        parts = name.split("/")
        if parts[0] == "projects" and len(parts) >= 4:
            slug = parts[1]
            pid = project_id_by_slug.get(slug)
            kind = parts[2]
            rest = "/".join(parts[3:])
            if kind == "context":
                _upsert_context(session, pid, "project", rest, data.decode("utf-8"))
                counts["context"] += 1
            elif kind == "memory":
                session.add(_memory_from_md(pid, data.decode("utf-8")))
                counts["memory"] += 1
            elif kind == "decisions":
                session.add(_decision_from_md(pid, data.decode("utf-8")))
                counts["decisions"] += 1
            elif kind == "sessions":
                session.add(_session_from_md(pid, data.decode("utf-8")))
                counts["sessions"] += 1
        elif parts[0] == "globals" and len(parts) >= 3:
            kind = parts[1]
            rest = "/".join(parts[2:])
            if kind == "context":
                _upsert_context(session, None, "global", rest, data.decode("utf-8"))
                counts["context"] += 1
    session.commit()
    return counts


def _upsert_context(session: Session, project_id: int | None, scope: str, path: str, content: str) -> None:
    import hashlib

    h = hashlib.sha256(content.encode("utf-8")).hexdigest()
    existing = session.execute(
        select(ContextDocument).where(
            ContextDocument.project_id.is_(project_id) if project_id is None else ContextDocument.project_id == project_id,
            ContextDocument.scope == scope,
            ContextDocument.path == path,
        )
    ).scalar_one_or_none()
    if existing:
        existing.content = content
        existing.content_hash = h
    else:
        # Best-effort category from first path segment
        cat = path.split("/")[0] if "/" in path else path.split(".")[0]
        session.add(
            ContextDocument(
                project_id=project_id,
                scope=scope,
                category=cat,
                path=path,
                content=content,
                content_hash=h,
            )
        )


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_block = text[3:end].strip("\n")
    body_start = end + len("\n---")
    if text[body_start:body_start + 1] == "\n":
        body_start += 1
    body = text[body_start:]
    fm: dict[str, Any] = {}
    for line in fm_block.splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        fm[k.strip()] = v.strip()
    return fm, body


def _memory_from_md(project_id: int | None, text: str) -> MemoryItem:
    fm, body = _parse_frontmatter(text)
    tags_raw = fm.get("tags", "")
    tags: list[str] = []
    if tags_raw:
        tags_raw = tags_raw.strip()
        if tags_raw.startswith("[") and tags_raw.endswith("]"):
            tags_raw = tags_raw[1:-1]
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
    return MemoryItem(
        project_id=project_id,
        kind=fm.get("kind", "note"),
        title=fm.get("title"),
        body=redact(body.rstrip("\n") + "\n"),
        tags=tags,
    )


def _decision_from_md(project_id: int | None, text: str) -> Decision:
    fm, body = _parse_frontmatter(text)
    return Decision(
        project_id=project_id,
        title=fm.get("title", "untitled"),
        body=body.rstrip("\n") + "\n",
    )


def _session_from_md(project_id: int | None, text: str) -> SessionSummary:
    from datetime import datetime

    fm, body = _parse_frontmatter(text)

    def _parse_dt(v: str | None):
        if not v or v == "None":
            return None
        try:
            return datetime.fromisoformat(v)
        except Exception:
            return None

    return SessionSummary(
        project_id=project_id,
        summary=body.rstrip("\n") + "\n",
        started_at=_parse_dt(fm.get("started_at")),
        ended_at=_parse_dt(fm.get("ended_at")),
    )
