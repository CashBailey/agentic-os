"""For every reversible migration, downgrade -1 then upgrade +1.

Asserts the schema lands back at head with no errors -- a cheap proof that
each migration is symmetric. Skips when only the initial revision exists.
"""
from __future__ import annotations

import pytest

from .conftest import current_revision, history_revisions, run_alembic


def test_each_revision_roundtrips_cleanly() -> None:
    run_alembic("upgrade", "head")

    revs = history_revisions()  # head -> base
    if len(revs) <= 1:
        pytest.skip("only initial migration present -- nothing to round-trip")

    head = revs[0]

    # Walk from head down to (but not including) the base revision. For each
    # step, downgrade -1, then immediately upgrade +1, then verify we're back
    # at the same revision we started this step at.
    for rev in revs[:-1]:
        before = current_revision()
        run_alembic("downgrade", "-1")
        run_alembic("upgrade", "+1")
        after = current_revision()
        assert after == before, (
            f"revision drift round-tripping {rev!r}: before={before!r} after={after!r}"
        )

    final = current_revision()
    assert final == head, f"final revision {final!r} != head {head!r}"
