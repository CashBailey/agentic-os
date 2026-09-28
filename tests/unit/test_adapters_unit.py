"""Unit tests for adapter schemas/models — no DB, no FastAPI startup."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.schemas.adapters import AdapterGenerationRead


def _valid_payload(**overrides):
    base = {
        "id": 1,
        "project_id": 42,
        "cli": "claude",
        "generated_at": datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        "source_hash": "abc123",
        "output_hash": "def456",
        "files": [{"path": "out/claude.md", "size": 1024}],
    }
    base.update(overrides)
    return base


class TestAdapterGenerationRead:
    def test_valid_construction(self):
        m = AdapterGenerationRead(**_valid_payload())
        assert m.id == 1
        assert m.cli == "claude"
        assert m.project_id == 42

    def test_project_id_optional(self):
        m = AdapterGenerationRead(**_valid_payload(project_id=None))
        assert m.project_id is None

    def test_files_list_of_dicts(self):
        files = [{"path": "a"}, {"path": "b", "size": 7}]
        m = AdapterGenerationRead(**_valid_payload(files=files))
        assert m.files == files

    def test_serialization_roundtrip(self):
        payload = _valid_payload()
        m = AdapterGenerationRead(**payload)
        dumped = m.model_dump()
        assert dumped["id"] == 1
        assert dumped["cli"] == "claude"
        assert dumped["files"][0]["path"] == "out/claude.md"

    def test_missing_required_raises(self):
        from pydantic import ValidationError
        bad = _valid_payload()
        del bad["cli"]
        with pytest.raises(ValidationError):
            AdapterGenerationRead(**bad)

    def test_wrong_type_for_id_raises(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AdapterGenerationRead(**_valid_payload(id="not-an-int-and-not-coercible-xx"))

    def test_from_attributes_compatible_orm_like(self):
        """ORMBase has from_attributes=True; ensure we can build from an object."""
        class Stub:
            id = 7
            project_id = None
            cli = "gemini"
            generated_at = datetime.now(timezone.utc)
            source_hash = "h1"
            output_hash = "h2"
            files = [{"path": "x"}]

        m = AdapterGenerationRead.model_validate(Stub())
        assert m.cli == "gemini"
        assert m.id == 7

    def test_empty_files_allowed(self):
        m = AdapterGenerationRead(**_valid_payload(files=[]))
        assert m.files == []

    def test_cli_must_be_string(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AdapterGenerationRead(**_valid_payload(cli=None))


class TestAdapterModelImport:
    """Just make sure the SQLAlchemy model module imports cleanly without DB."""

    def test_model_class_exists(self):
        from app.models.adapters import AdapterGeneration
        assert AdapterGeneration.__tablename__ == "adapter_generations"

    def test_model_columns(self):
        from app.models.adapters import AdapterGeneration
        cols = {c.name for c in AdapterGeneration.__table__.columns}
        assert {"id", "project_id", "cli", "generated_at",
                "source_hash", "output_hash", "files"}.issubset(cols)
