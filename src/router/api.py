"""FastAPI application for WhatsApp AI Notification Router."""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from router.config import GEMINI_MODEL
from router.database import get_db, init_db
from router.history import InteractionHistory
from router.models import (
    BatchRouteRequest,
    IncomingMessage,
    RouteRequest,
    RoutingDecision,
    UserProfile,
)
from router.profiles import ProfileStore
from router.registry import SenderGroupRegistry
from router.webhook import parse_whatsapp_webhook

logger = logging.getLogger(__name__)

# Global module-level reference to the router instance
_router_instance: Optional[Any] = None


try:
    from router.engine import NotificationRouter
except ImportError:
    # Graceful fallback stub if router.engine is not yet created
    class NotificationRouter:  # type: ignore[no-redef]
        """Fallback NotificationRouter interface when engine module is loading."""

        def __init__(
            self,
            profiles: Optional[ProfileStore] = None,
            registry: Optional[SenderGroupRegistry] = None,
            history: Optional[InteractionHistory] = None,
        ) -> None:
            self.profiles = profiles if profiles is not None else ProfileStore()
            self.registry = registry if registry is not None else SenderGroupRegistry()
            self.history = history if history is not None else InteractionHistory()

        async def route(
            self, db: AsyncSession, message: IncomingMessage, user_id: str
        ) -> RoutingDecision:
            raise NotImplementedError("NotificationRouter engine is not yet available.")

        async def route_batch(
            self, db: AsyncSession, messages: list[IncomingMessage], user_id: str
        ) -> list[RoutingDecision]:
            raise NotImplementedError("NotificationRouter engine is not yet available.")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context manager for FastAPI application.

    Initializes the database tables and the NotificationRouter.
    """
    global _router_instance

    logger.info("Initializing NotificationRouter database...")
    await init_db()

    router = NotificationRouter()

    app.state.router = router
    _router_instance = router

    logger.info("NotificationRouter initialized successfully.")

    yield

    # Clean up state on shutdown
    app.state.router = None
    _router_instance = None
    logger.info("NotificationRouter shut down successfully.")


app = FastAPI(
    title="WhatsApp Notification Router",
    description="AI-powered message routing for WhatsApp",
    version="0.1.0",
    lifespan=lifespan,
)


def get_router(request: Optional[Request] = None) -> NotificationRouter:
    """Retrieve the active NotificationRouter instance.

    Checks the request app state, application state, or module-level variable.

    Args:
        request: Optional incoming HTTP Request.

    Returns:
        The active NotificationRouter instance.

    Raises:
        HTTPException: If router initialization fails.
    """
    if request is not None and hasattr(request, "app") and hasattr(request.app.state, "router"):
        if request.app.state.router is not None:
            return request.app.state.router
    if hasattr(app.state, "router") and app.state.router is not None:
        return app.state.router
    if _router_instance is not None:
        return _router_instance

    # Lazy fallback initialization
    try:
        router = NotificationRouter()
        app.state.router = router
        return router
    except Exception as err:
        logger.error("Failed to lazily initialize NotificationRouter: %s", err)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NotificationRouter is not initialized.",
        ) from err


@app.post(
    "/route",
    response_model=RoutingDecision,
    summary="Route a single message",
    status_code=status.HTTP_200_OK,
)
async def route_message(
    request: RouteRequest, db: AsyncSession = Depends(get_db)
) -> RoutingDecision:
    """Route a single incoming message.

    Args:
        request: RouteRequest containing message payload and user_id.
        db: Async database session.

    Returns:
        RoutingDecision with action, confidence, reasoning, and metadata.
    """
    router = get_router()
    try:
        return await router.route(db=db, message=request.message, user_id=request.user_id)
    except Exception as exc:
        logger.exception("Failed to route message ID %s: %s", request.message.message_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Message routing failed: {exc}",
        ) from exc


@app.post(
    "/route/batch",
    response_model=list[RoutingDecision],
    summary="Route multiple messages",
    status_code=status.HTTP_200_OK,
)
async def route_batch(
    request: BatchRouteRequest, db: AsyncSession = Depends(get_db)
) -> list[RoutingDecision]:
    """Route multiple messages. Returns list of RoutingDecision.

    Args:
        request: BatchRouteRequest containing message list and user_id.
        db: Async database session.

    Returns:
        List of RoutingDecision instances.
    """
    router = get_router()
    try:
        return await router.route_batch(db=db, messages=request.messages, user_id=request.user_id)
    except Exception as exc:
        logger.exception(
            "Failed to route batch of %d messages for user %s: %s",
            len(request.messages),
            request.user_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch routing failed: {exc}",
        ) from exc


@app.get(
    "/users",
    response_model=list[UserProfile],
    summary="List all users",
    status_code=status.HTTP_200_OK,
)
async def list_users(db: AsyncSession = Depends(get_db)) -> list[UserProfile]:
    """List all user profiles in the database."""
    router = get_router()
    return await router.profiles.list_all(db)


@app.get(
    "/users/{user_id}/profile",
    response_model=UserProfile,
    summary="Get user profile",
    status_code=status.HTTP_200_OK,
)
async def get_user_profile(
    user_id: str, db: AsyncSession = Depends(get_db)
) -> UserProfile:
    """Get a user profile.

    Args:
        user_id: Unique identifier for the user.
        db: Async database session.

    Returns:
        UserProfile instance.
    """
    router = get_router()
    return await router.profiles.get(db, user_id)


@app.put(
    "/users/{user_id}/profile",
    response_model=UserProfile,
    summary="Update user profile",
    status_code=status.HTTP_200_OK,
)
async def update_user_profile(
    user_id: str, profile: UserProfile, db: AsyncSession = Depends(get_db)
) -> UserProfile:
    """Update a user profile. The user_id in path must match profile.user_id.

    Args:
        user_id: User identifier in path.
        profile: Updated UserProfile in request body.
        db: Async database session.

    Returns:
        The saved UserProfile.

    Raises:
        HTTPException: If path user_id does not match profile.user_id (HTTP 400).
    """
    if user_id != profile.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path user_id '{user_id}' does not match body user_id '{profile.user_id}'.",
        )
    router = get_router()
    await router.profiles.upsert(db, profile)
    return profile


@app.get(
    "/users/{user_id}/history",
    response_model=list[dict[str, Any]],
    summary="Get user history",
    status_code=status.HTTP_200_OK,
)
async def get_user_history(
    user_id: str,
    limit: int = Query(default=20, ge=1, description="Maximum number of history records to return"),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get recent routing history for a user.

    Args:
        user_id: Unique identifier for the user.
        limit: Maximum number of recent history items to return (default 20).
        db: Async database session.

    Returns:
        List of recent routing decision records.
    """
    router = get_router()
    return await router.history.get_recent(db=db, user_id=user_id, limit=limit)


@app.get(
    "/webhook",
    summary="Webhook verification",
    status_code=status.HTTP_200_OK,
)
async def verify_webhook(
    mode: str = Query(..., alias="hub.mode"),
    challenge: int = Query(..., alias="hub.challenge"),
    verify_token: str = Query(..., alias="hub.verify_token"),
) -> int:
    """Verify webhook.
    
    Args:
        mode: hub.mode
        challenge: hub.challenge
        verify_token: hub.verify_token
        
    Returns:
        The challenge integer.
    """
    if mode == "subscribe":
        return challenge
    raise HTTPException(status_code=400, detail="Invalid mode")


@app.post(
    "/webhook",
    summary="Receive WhatsApp webhook",
    status_code=status.HTTP_200_OK,
)
async def handle_webhook(
    request: Request, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    """Process incoming WhatsApp webhooks.
    
    Args:
        request: The FastAPI request object.
        db: Async database session.
    """
    payload = await request.json()
    messages = parse_whatsapp_webhook(payload)
    
    router = get_router()
    for msg in messages:
        # Assuming the recipient is the user of the system and sender is msg.sender_id
        # Wait, the prompt says "msg.sender_id as the recipient" -> "call await router.route(db, msg, msg.sender_id) for each one (as the recipient)"
        # Actually wait, the user instructions: "call `await router.route(db, msg, msg.sender_id)` for each one (as the recipient)."
        # In a real app, recipient might be derived from `payload`, but we follow instructions strictly.
        try:
            await router.route(db=db, message=msg, user_id=msg.sender_id)
        except Exception as err:
            logger.error("Failed to route webhook message %s: %s", msg.message_id, err)
            
    return {"status": "success"}


@app.get(
    "/health",
    summary="Health check",
    status_code=status.HTTP_200_OK,
)
async def health_check() -> dict[str, str]:
    """Health check endpoint.

    Returns:
        Status dictionary with 'status' and configured Gemini model name.
    """
    return {"status": "ok", "model": GEMINI_MODEL}

from fastapi.responses import FileResponse
from sqlalchemy import select, func
from router.db_models import DBInteractionHistory

@app.get(
    "/analytics/stats",
    summary="Get routing analytics",
    status_code=status.HTTP_200_OK,
)
async def get_analytics_stats(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Get high-level analytics for the dashboard."""
    # Action counts
    action_stmt = select(DBInteractionHistory.action, func.count(DBInteractionHistory.id)).group_by(DBInteractionHistory.action)
    action_res = await db.execute(action_stmt)
    action_counts = {row[0]: row[1] for row in action_res.all()}
    
    # Average confidence
    conf_stmt = select(func.avg(DBInteractionHistory.confidence))
    conf_res = await db.execute(conf_stmt)
    avg_conf = conf_res.scalar_one_or_none() or 0.0
    
    # Total messages
    total = sum(action_counts.values())
    
    return {
        "total_routed": total,
        "action_distribution": action_counts,
        "average_confidence": round(avg_conf * 100, 1),
        "spam_blocked": action_counts.get("mute", 0)
    }

@app.get(
    "/analytics/recent",
    summary="Get global recent history",
    status_code=status.HTTP_200_OK,
)
async def get_analytics_recent(limit: int = 50, db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    """Get the most recent routing decisions globally."""
    stmt = select(DBInteractionHistory).order_by(DBInteractionHistory.timestamp.desc()).limit(limit)
    result = await db.execute(stmt)
    records = result.scalars().all()
    
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "message_id": r.message_id,
            "timestamp": r.timestamp.isoformat(),
            "action": r.action,
            "confidence": r.confidence,
            "reasoning": r.reasoning,
        }
        for r in records
    ]

from sqlalchemy import delete

@app.delete(
    "/analytics/history",
    summary="Purge all routing history",
    status_code=status.HTTP_200_OK,
)
async def purge_history(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Permanently delete all routing logs and system history."""
    stmt = delete(DBInteractionHistory)
    await db.execute(stmt)
    await db.commit()
    return {"status": "success", "message": "All history logs have been purged."}

@app.get(
    "/",
    summary="Dashboard",
    status_code=status.HTTP_200_OK,
)
async def root() -> FileResponse:
    """Serve the dashboard UI on the root endpoint."""
    dashboard_path = Path(__file__).parent / "dashboard.html"
    return FileResponse(dashboard_path)
