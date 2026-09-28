from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._common import created_at_column, pk_column, updated_at_column


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    __table_args__ = (
        Index("approval_requests_status", "status", "expires_at"),
    )

    id: Mapped[int] = pk_column()
    project_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )
    tool: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    raw_input: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    normalized: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    risk: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    agent_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    policy_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="pending"
    )
    release_token: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


class ApprovalDecision(Base):
    __tablename__ = "approval_decisions"

    id: Mapped[int] = pk_column()
    approval_request_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("approval_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    decided_by: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="user"
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()", nullable=False
    )
    execution_result: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )
