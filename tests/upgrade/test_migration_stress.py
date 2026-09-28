"""Upgrade stress: write chain-hashed audit rows, downgrade -1, upgrade +1.

For each row, the payload is ``{"seq": i, "prev_hash": h_{i-1},
"data": {...}, "hash": sha256(prev_hash + canonical_json(data))}``. After the
round-trip we assert every stored hash matches the recomputed hash and the
row count is intact.

Caveat for a single-revision repo: when the only revision is the initial
schema, ``downgrade -1`` drops the data alongside the schema. In that case
this test asserts: (a) the chain verifies before the downgrade, (b) the
schema is re-creatable end-to-end, and (c) the chain still verifies after a
fresh upgrade + reseed -- which is the strongest invariant the schema can
actually offer.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Dict, List, Tuple

import pytest

from .conftest import history_revisions, run_alembic

ROW_COUNT = 50
EVENT_TYPE = "chain.test"
ACTOR_TAG = "tests.upgrade.test_migration_stress"


def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _chain_payload(seq: int, prev_hash: str, marker: str) -> Dict[str, Any]:
    data = {"i": seq, "msg": f"row-{seq}", "marker": marker}
    h = hashlib.sha256(prev_hash.encode("utf-8") + _canon(data)).hexdigest()
    return {"seq": seq, "prev_hash": prev_hash, "data": data, "hash": h}


def _seed_chain(marker: str) -> List[Dict[str, Any]]:
    from sqlalchemy import text

    from app.db.session import SyncSessionLocal

    payloads: List[Dict[str, Any]] = []
    prev = "GENESIS"
    with SyncSessionLocal() as s:
        for i in range(ROW_COUNT):
            p = _chain_payload(i, prev, marker)
            payloads.append(p)
            s.execute(
                text(
                    """
                    INSERT INTO audit_events (event_type, project_id, actor, payload)
                    VALUES (:et, NULL, :actor, CAST(:p AS jsonb))
                    """
                ),
                {"et": EVENT_TYPE, "actor": ACTOR_TAG, "p": json.dumps(p)},
            )
            prev = p["hash"]
        s.commit()
    return payloads


def _read_chain(marker: str) -> List[Dict[str, Any]]:
    from sqlalchemy import text

    from app.db.session import SyncSessionLocal

    with SyncSessionLocal() as s:
        rows = s.execute(
            text(
                """
                SELECT payload FROM audit_events
                 WHERE event_type = :et AND actor = :actor
                   AND payload->>'marker' IS NULL OR payload->'data'->>'marker' = :m
                 ORDER BY (payload->>'seq')::int
                """
            ),
            {"et": EVENT_TYPE, "actor": ACTOR_TAG, "m": marker},
        ).all()
    return [r[0] for r in rows]


def _verify_chain(rows: List[Dict[str, Any]]) -> Tuple[bool, str]:
    if len(rows) != ROW_COUNT:
        return False, f"expected {ROW_COUNT} rows, got {len(rows)}"
    prev = "GENESIS"
    for i, p in enumerate(rows):
        if p.get("seq") != i:
            return False, f"row {i}: seq mismatch ({p.get('seq')!r})"
        if p.get("prev_hash") != prev:
            return False, f"row {i}: prev_hash mismatch"
        expected = hashlib.sha256(prev.encode() + _canon(p["data"])).hexdigest()
        if p.get("hash") != expected:
            return False, f"row {i}: hash mismatch (stored={p.get('hash')!r}, expected={expected!r})"
        prev = p["hash"]
    return True, ""


def _delete_marker_rows(marker: str) -> None:
    from sqlalchemy import text

    from app.db.session import SyncSessionLocal

    with SyncSessionLocal() as s:
        s.execute(
            text(
                "DELETE FROM audit_events WHERE event_type = :et AND actor = :actor "
                "AND payload->'data'->>'marker' = :m"
            ),
            {"et": EVENT_TYPE, "actor": ACTOR_TAG, "m": marker},
        )
        s.commit()


def test_audit_chain_survives_round_trip() -> None:
    marker = f"stress-{uuid.uuid4().hex[:12]}"

    # Ensure we're at head before doing anything.
    run_alembic("upgrade", "head")

    payloads = _seed_chain(marker)
    rows_before = _read_chain(marker)
    ok, reason = _verify_chain(rows_before)
    assert ok, f"chain invalid before round-trip: {reason}"
    assert [r["hash"] for r in rows_before] == [p["hash"] for p in payloads]

    revs = history_revisions()
    if len(revs) <= 1:
        # Single-revision repo: downgrade -1 = drop everything. Best we can
        # do is prove a full schema rebuild + reseed yields a valid chain.
        try:
            run_alembic("downgrade", "base")
            run_alembic("upgrade", "head")
            payloads2 = _seed_chain(marker)
            rows_after = _read_chain(marker)
            ok2, reason2 = _verify_chain(rows_after)
            assert ok2, f"chain invalid after rebuild: {reason2}"
            assert [r["hash"] for r in rows_after] == [p["hash"] for p in payloads2]
        finally:
            _delete_marker_rows(marker)
        return

    # Multi-revision repo: real round trip.
    try:
        run_alembic("downgrade", "-1")
        run_alembic("upgrade", "+1")
        rows_after = _read_chain(marker)
        ok2, reason2 = _verify_chain(rows_after)
        assert ok2, f"chain invalid after downgrade/upgrade: {reason2}"
        assert [r["hash"] for r in rows_after] == [p["hash"] for p in payloads]
    finally:
        _delete_marker_rows(marker)
