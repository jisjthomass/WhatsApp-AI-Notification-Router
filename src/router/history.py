"""Database-backed interaction history tracker."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from router.db_models import DBInteractionHistory
from router.models import IncomingMessage, RoutingDecision


class InteractionHistory:
    """Database-backed history of routing decisions per user.

    Tracks recent routing outcomes for context-aware prompt injection,
    chat-specific history lookups, and sender interaction statistics.
    """

    async def record(
        self,
        db: AsyncSession,
        user_id: str,
        message: IncomingMessage,
        decision: RoutingDecision,
    ) -> None:
        """Record a routing decision for a message.

        Args:
            db: Async database session.
            user_id: Unique identifier for the receiving user.
            message: The IncomingMessage that was routed.
            decision: The RoutingDecision produced by the router.
        """
        db_history = DBInteractionHistory(
            user_id=user_id,
            message_id=message.message_id,
            sender_id=message.sender_id,
            chat_id=message.chat_id,
            timestamp=message.timestamp,
            action=decision.action,
            confidence=decision.confidence,
            reasoning=decision.reasoning,
        )
        db.add(db_history)
        await db.commit()

    async def get_recent(
        self, db: AsyncSession, user_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get the N most recent decisions for a user (newest first).

        Args:
            db: Async database session.
            user_id: Unique identifier for the user.
            limit: Maximum number of recent decisions to return.

        Returns:
            List of recent decision entry dictionaries, ordered from newest to oldest.
        """
        if limit <= 0:
            return []

        stmt = (
            select(DBInteractionHistory)
            .where(DBInteractionHistory.user_id == user_id)
            .order_by(desc(DBInteractionHistory.timestamp))
            .limit(limit)
        )
        result = await db.execute(stmt)
        entries = result.scalars().all()

        return [
            {
                "message_id": e.message_id,
                "sender_id": e.sender_id,
                "chat_id": e.chat_id,
                "action": e.action,
                "confidence": e.confidence,
                "reasoning": e.reasoning,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            }
            for e in entries
        ]

    async def get_chat_recent(
        self,
        db: AsyncSession,
        user_id: str,
        chat_id: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Get recent decisions for a specific chat (newest first).

        Args:
            db: Async database session.
            user_id: Unique identifier for the user.
            chat_id: Identifier of the group or DM chat.
            limit: Maximum number of recent decisions to return.

        Returns:
            List of decision entry dictionaries for the chat, ordered newest first.
        """
        if limit <= 0:
            return []

        stmt = (
            select(DBInteractionHistory)
            .where(
                DBInteractionHistory.user_id == user_id,
                DBInteractionHistory.chat_id == chat_id,
            )
            .order_by(desc(DBInteractionHistory.timestamp))
            .limit(limit)
        )
        result = await db.execute(stmt)
        entries = result.scalars().all()

        return [
            {
                "message_id": e.message_id,
                "sender_id": e.sender_id,
                "chat_id": e.chat_id,
                "action": e.action,
                "confidence": e.confidence,
                "reasoning": e.reasoning,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            }
            for e in entries
        ]

    async def get_sender_stats(
        self, db: AsyncSession, user_id: str, sender_id: str
    ) -> dict[str, int]:
        """Get aggregated stats for a sender.

        Aggregates total messages, mute count, notify count, and digest count
        for messages from the specified sender received by this user.

        Args:
            db: Async database session.
            user_id: Unique identifier for the user.
            sender_id: Identifier of the sender.

        Returns:
            Dictionary containing aggregated counts.
        """
        stmt = select(DBInteractionHistory.action).where(
            DBInteractionHistory.user_id == user_id,
            DBInteractionHistory.sender_id == sender_id,
        )
        result = await db.execute(stmt)
        actions = result.scalars().all()

        notify_count = 0
        digest_count = 0
        mute_count = 0
        total_messages = len(actions)

        for action in actions:
            if action == "notify":
                notify_count += 1
            elif action == "digest":
                digest_count += 1
            elif action == "mute":
                mute_count += 1

        return {
            "total_messages": total_messages,
            "notify_count": notify_count,
            "digest_count": digest_count,
            "mute_count": mute_count,
            "total": total_messages,
            "notify": notify_count,
            "digest": digest_count,
            "mute": mute_count,
        }

    async def clear(self, db: AsyncSession, user_id: str | None = None) -> None:
        """Clear recorded history.

        Args:
            db: Async database session.
            user_id: Optional user ID. If provided, clears only that user's history.
                     If None, clears all history for all users.
        """
        if user_id is not None:
            stmt = delete(DBInteractionHistory).where(DBInteractionHistory.user_id == user_id)
        else:
            stmt = delete(DBInteractionHistory)

        await db.execute(stmt)
        await db.commit()
