"""Local embeddings via sentence-transformers all-MiniLM-L6-v2 (dim 384).

Redaction is applied to every text BEFORE encoding. Model is lazy-loaded so the
backend can boot (and unit tests can run) without sentence-transformers
installed.
"""

from __future__ import annotations

import threading
from typing import Iterable

from app.config import settings
from app.services.redaction import redact_many

EMBEDDING_DIM = 384


class EmbeddingService:
    _lock = threading.Lock()
    _model = None  # type: ignore[var-annotated]

    @classmethod
    def _ensure_model(cls):
        if cls._model is not None:
            return cls._model
        with cls._lock:
            if cls._model is None:
                from sentence_transformers import SentenceTransformer

                cls._model = SentenceTransformer(settings.EMBEDDING_MODEL)
        return cls._model

    @classmethod
    def embed(cls, texts: Iterable[str]) -> list[list[float]]:
        # Redact BEFORE embedding so secrets never leave the box in a vector.
        cleaned = redact_many(list(texts))
        model = cls._ensure_model()
        vecs = model.encode(cleaned, normalize_embeddings=True)
        return [list(map(float, v)) for v in vecs]

    @classmethod
    def embed_one(cls, text: str) -> list[float]:
        return cls.embed([text])[0]
