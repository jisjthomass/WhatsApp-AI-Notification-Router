"""PostgreSQL-backed user profile store."""

from __future__ import annotations

import logging

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from router.db_models import DBUserProfile
from router.models import UserProfile

logger = logging.getLogger(__name__)


class ProfileStore:
    """Database-backed store for user profiles.

    Manages user notification preferences, interest topics, priority contacts,
    and sensitivity settings. Provides graceful fallback to default profiles
    when a user ID is not explicitly configured.
    """

    async def get(self, db: AsyncSession, user_id: str) -> UserProfile:
        """Get a user profile, returning a default balanced profile if not found.

        Args:
            db: Async database session.
            user_id: Unique identifier for the user.

        Returns:
            The stored UserProfile or a newly instantiated default balanced profile.
        """
        stmt = select(DBUserProfile).where(DBUserProfile.user_id == user_id)
        result = await db.execute(stmt)
        db_profile = result.scalar_one_or_none()

        if db_profile is not None:
            return UserProfile(
                user_id=db_profile.user_id,
                name=db_profile.name,
                priority_contacts=db_profile.priority_contacts,
                muted_chats=db_profile.muted_chats,
                interests=db_profile.interests,
                blocked_categories=db_profile.blocked_categories,
                work_hours=db_profile.work_hours,
                sensitivity=db_profile.sensitivity,
            )

        return UserProfile(
            user_id=user_id,
            name=f"User_{user_id}",
            priority_contacts=[],
            muted_chats=[],
            interests=[],
            blocked_categories=[],
            work_hours=None,
            sensitivity="balanced",
        )

    async def upsert(self, db: AsyncSession, profile: UserProfile) -> None:
        """Insert or update a user profile.

        Args:
            db: Async database session.
            profile: The UserProfile instance to store.
        """
        db_profile = DBUserProfile(
            user_id=profile.user_id,
            name=profile.name,
            priority_contacts=profile.priority_contacts,
            muted_chats=profile.muted_chats,
            interests=profile.interests,
            blocked_categories=profile.blocked_categories,
            work_hours=profile.work_hours,
            sensitivity=profile.sensitivity,
        )
        await db.merge(db_profile)
        await db.commit()

    async def list_all(self, db: AsyncSession) -> list[UserProfile]:
        """List all profiles currently stored in the database.

        Args:
            db: Async database session.

        Returns:
            List of all UserProfile instances.
        """
        stmt = select(DBUserProfile)
        result = await db.execute(stmt)
        db_profiles = result.scalars().all()

        return [
            UserProfile(
                user_id=p.user_id,
                name=p.name,
                priority_contacts=p.priority_contacts,
                muted_chats=p.muted_chats,
                interests=p.interests,
                blocked_categories=p.blocked_categories,
                work_hours=p.work_hours,
                sensitivity=p.sensitivity,
            )
            for p in db_profiles
        ]

    async def delete(self, db: AsyncSession, user_id: str) -> bool:
        """Delete a profile by user ID.

        Args:
            db: Async database session.
            user_id: The ID of the profile to remove.

        Returns:
            True if the profile was deleted, False if it was not found.
        """
        stmt = delete(DBUserProfile).where(DBUserProfile.user_id == user_id)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0

    async def exists(self, db: AsyncSession, user_id: str) -> bool:
        """Check if a user profile exists in the store.
        
        Args:
            db: Async database session.
            user_id: The user ID to check.
            
        Returns:
            True if exists, False otherwise.
        """
        stmt = select(DBUserProfile.user_id).where(DBUserProfile.user_id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def count(self, db: AsyncSession) -> int:
        """Return the number of stored profiles.
        
        Args:
            db: Async database session.
            
        Returns:
            Total number of profiles.
        """
        stmt = select(func.count(DBUserProfile.user_id))
        result = await db.execute(stmt)
        return result.scalar_one() or 0
