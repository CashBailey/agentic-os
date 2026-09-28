from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class PolicyFileRead(BaseModel):
    kind: str  # shell|file|mcp|approval
    path: str
    content: str
    parsed_ok: bool
    parse_error: Optional[str] = None


class PolicyUpdateIn(BaseModel):
    content: str


class PolicySimulateIn(BaseModel):
    tool: str
    action: str
    args: list[str] = []
    path: Optional[str] = None


class PolicySimulateOut(BaseModel):
    decision: str
    matched_rule: Optional[dict[str, Any]] = None
