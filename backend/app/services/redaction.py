"""Secret-pattern redaction. Applied BEFORE storing memory bodies AND before embedding.

Patterns scrubbed:
- AWS access keys: AKIA[0-9A-Z]{16}
- GitHub personal tokens: ghp_[A-Za-z0-9]{36}
- OpenAI-style keys: sk-[A-Za-z0-9]{20,}
- key=value pairs where key matches /password|secret|token|api[_-]?key/i
- bearer tokens: Bearer <token>
"""

from __future__ import annotations

import re

REDACTED = "[REDACTED]"

_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(
        r"(?i)\b(password|secret|token|api[_-]?key)\s*[=:]\s*([\"']?)[^\s\"'&]+\2",
    ),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]+"),
]


def redact(text: str) -> str:
    """Return *text* with known secret patterns replaced by ``[REDACTED]``."""
    if not text:
        return text
    out = text
    # Pattern 0-2 & 4: direct full-match replacement.
    for pat in (_PATTERNS[0], _PATTERNS[1], _PATTERNS[2], _PATTERNS[4]):
        out = pat.sub(REDACTED, out)
    # Pattern 3 (key=value): keep the key, replace the value.
    out = _PATTERNS[3].sub(
        lambda m: f"{m.group(1)}={REDACTED}", out
    )
    return out


def redact_many(texts: list[str]) -> list[str]:
    return [redact(t) for t in texts]
