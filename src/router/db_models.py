"""SQLAlchemy database models for the WhatsApp notification router."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from router.database import Base


class DBUserProfile(Base):
    """Database model for user profiles and preferences."""
    
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    priority_contacts: Mapped[list[str]] = mapped_column(JSON, default=list)
    muted_chats: Mapped[list[str]] = mapped_column(JSON, default=list)
    interests: Mapped[list[str]] = mapped_column(JSON, default=list)
    blocked_categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    work_hours: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    sensitivity: Mapped[str] = mapped_column(String, default="balanced")


class DBSenderContext(Base):
    """Database model for sender context metadata."""
    
    __tablename__ = "senders"

    sender_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    sender_type: Mapped[str] = mapped_column(String, default="unknown")
    is_in_contacts: Mapped[bool] = mapped_column(Boolean, default=False)
    trust_score: Mapped[float] = mapped_column(Float, default=0.3)
    relationship: Mapped[str | None] = mapped_column(String, nullable=True)
    recent_message_count_24h: Mapped[int] = mapped_column(Integer, default=0)
    spam_reports: Mapped[int] = mapped_column(Integer, default=0)


class DBGroupContext(Base):
    """Database model for group chat context metadata."""
    
    __tablename__ = "groups"

    chat_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    chat_name: Mapped[str] = mapped_column(String, nullable=False)
    chat_type: Mapped[str] = mapped_column(String, default="group")
    member_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    user_engagement_rate: Mapped[float] = mapped_column(Float, default=0.5)
    is_muted_by_user: Mapped[bool] = mapped_column(Boolean, default=False)


class DBInteractionHistory(Base):
    """Database model for history of routing decisions."""
    
    __tablename__ = "history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    message_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    sender_id: Mapped[str] = mapped_column(String, index=True, nullable=True)
    chat_id: Mapped[str] = mapped_column(String, index=True, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    action: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    ai_reply_text: Mapped[str | None] = mapped_column(Text, nullable=True)
