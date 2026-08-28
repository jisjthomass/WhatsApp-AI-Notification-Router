"""PostgreSQL-backed sender and group context registry."""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from router.config import DEFAULT_TRUST_SCORE
from router.db_models import DBGroupContext, DBSenderContext
from router.models import GroupContext, SenderContext

logger = logging.getLogger(__name__)


class SenderGroupRegistry:
    """Database-backed registry tracking sender and group metadata.

    Provides metadata lookup and caching for WhatsApp senders (contacts, businesses,
    unknown numbers) and chats (DMs, groups, broadcast channels). Automatically
    provisions default contexts for unknown entities.
    """

    async def get_sender(
        self, db: AsyncSession, sender_id: str, default_name: str = "Unknown"
    ) -> SenderContext:
        """Get sender context, auto-creating a default context for unknowns.

        Unknown senders receive DEFAULT_TRUST_SCORE (0.3) and sender_type 'unknown'.

        Args:
            db: Async database session.
            sender_id: Phone number or business ID of the sender.
            default_name: Fallback display name if the sender is unknown.

        Returns:
            SenderContext instance for the given sender.
        """
        stmt = select(DBSenderContext).where(DBSenderContext.sender_id == sender_id)
        result = await db.execute(stmt)
        db_sender = result.scalar_one_or_none()

        if db_sender is not None:
            return SenderContext(
                sender_id=db_sender.sender_id,
                display_name=db_sender.display_name,
                sender_type=db_sender.sender_type,
                is_in_contacts=db_sender.is_in_contacts,
                trust_score=db_sender.trust_score,
                relationship=db_sender.relationship,
                recent_message_count_24h=db_sender.recent_message_count_24h,
                spam_reports=db_sender.spam_reports,
            )

        return SenderContext(
            sender_id=sender_id,
            display_name=default_name,
            sender_type="unknown",
            is_in_contacts=False,
            trust_score=DEFAULT_TRUST_SCORE,
            relationship=None,
            recent_message_count_24h=0,
            spam_reports=0,
        )

    async def register_sender(self, db: AsyncSession, ctx: SenderContext) -> None:
        """Register or update a sender context.

        Args:
            db: Async database session.
            ctx: SenderContext to register.
        """
        db_sender = DBSenderContext(
            sender_id=ctx.sender_id,
            display_name=ctx.display_name,
            sender_type=ctx.sender_type,
            is_in_contacts=ctx.is_in_contacts,
            trust_score=ctx.trust_score,
            relationship=ctx.relationship,
            recent_message_count_24h=ctx.recent_message_count_24h,
            spam_reports=ctx.spam_reports,
        )
        await db.merge(db_sender)
        await db.commit()

    async def get_group(
        self, db: AsyncSession, chat_id: str, default_name: str = "Unknown Group"
    ) -> GroupContext:
        """Get group or chat context, auto-creating a default context for unknowns.

        Args:
            db: Async database session.
            chat_id: Group or chat identifier.
            default_name: Fallback chat name if the group is unknown.

        Returns:
            GroupContext instance for the given chat ID.
        """
        stmt = select(DBGroupContext).where(DBGroupContext.chat_id == chat_id)
        result = await db.execute(stmt)
        db_group = result.scalar_one_or_none()

        if db_group is not None:
            return GroupContext(
                chat_id=db_group.chat_id,
                chat_name=db_group.chat_name,
                chat_type=db_group.chat_type,
                member_count=db_group.member_count,
                category=db_group.category,
                user_engagement_rate=db_group.user_engagement_rate,
                is_muted_by_user=db_group.is_muted_by_user,
            )

        return GroupContext(
            chat_id=chat_id,
            chat_name=default_name,
            chat_type="group",
            member_count=None,
            category=None,
            user_engagement_rate=0.5,
            is_muted_by_user=False,
        )

    async def register_group(self, db: AsyncSession, ctx: GroupContext) -> None:
        """Register or update a group context.

        Args:
            db: Async database session.
            ctx: GroupContext to register.
        """
        db_group = DBGroupContext(
            chat_id=ctx.chat_id,
            chat_name=ctx.chat_name,
            chat_type=ctx.chat_type,
            member_count=ctx.member_count,
            category=ctx.category,
            user_engagement_rate=ctx.user_engagement_rate,
            is_muted_by_user=ctx.is_muted_by_user,
        )
        await db.merge(db_group)
        await db.commit()

    async def increment_message_count(self, db: AsyncSession, sender_id: str) -> None:
        """Increment the 24h message count for a sender.

        Args:
            db: Async database session.
            sender_id: The sender ID whose message count should be incremented.
        """
        sender = await self.get_sender(db, sender_id)
        sender.recent_message_count_24h += 1
        await self.register_sender(db, sender)

    async def report_spam(self, db: AsyncSession, sender_id: str) -> None:
        """Increment spam reports for a sender and decrease trust score.

        Trust score is decreased by 0.2 down to a minimum of 0.0.

        Args:
            db: Async database session.
            sender_id: The sender ID flagged for spam.
        """
        sender = await self.get_sender(db, sender_id)
        sender.spam_reports += 1
        sender.trust_score = max(0.0, round(sender.trust_score - 0.2, 2))
        await self.register_sender(db, sender)

    async def list_senders(self, db: AsyncSession) -> list[SenderContext]:
        """List all registered senders.

        Args:
            db: Async database session.

        Returns:
            List of all SenderContext instances.
        """
        stmt = select(DBSenderContext)
        result = await db.execute(stmt)
        senders = result.scalars().all()
        return [
            SenderContext(
                sender_id=s.sender_id,
                display_name=s.display_name,
                sender_type=s.sender_type,
                is_in_contacts=s.is_in_contacts,
                trust_score=s.trust_score,
                relationship=s.relationship,
                recent_message_count_24h=s.recent_message_count_24h,
                spam_reports=s.spam_reports,
            )
            for s in senders
        ]

    async def list_groups(self, db: AsyncSession) -> list[GroupContext]:
        """List all registered groups.

        Args:
            db: Async database session.

        Returns:
            List of all GroupContext instances.
        """
        stmt = select(DBGroupContext)
        result = await db.execute(stmt)
        groups = result.scalars().all()
        return [
            GroupContext(
                chat_id=g.chat_id,
                chat_name=g.chat_name,
                chat_type=g.chat_type,
                member_count=g.member_count,
                category=g.category,
                user_engagement_rate=g.user_engagement_rate,
                is_muted_by_user=g.is_muted_by_user,
            )
            for g in groups
        ]

    async def count(self, db: AsyncSession) -> int:
        """Return total number of registered senders and groups.
        
        Args:
            db: Async database session.
        """
        stmt_senders = select(func.count(DBSenderContext.sender_id))
        res_senders = await db.execute(stmt_senders)
        count_senders = res_senders.scalar_one() or 0

        stmt_groups = select(func.count(DBGroupContext.chat_id))
        res_groups = await db.execute(stmt_groups)
        count_groups = res_groups.scalar_one() or 0

        return count_senders + count_groups
