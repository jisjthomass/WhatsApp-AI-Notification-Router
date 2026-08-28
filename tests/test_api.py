"""Unit tests for FastAPI application in router.api."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
import pytest

from router.api import app
from router.config import GEMINI_MODEL

from sqlalchemy.ext.asyncio import AsyncSession
from router.engine import NotificationRouter

@pytest.fixture
async def populated_db(db_session: AsyncSession):
    profile = UserProfile(
        user_id="user_priya",
        name="Priya Sharma",
        priority_contacts=[],
        muted_chats=[],
        interests=["school fees"],
        blocked_categories=[],
        work_hours=None,
        sensitivity="balanced"
    )
    router = NotificationRouter()
    await router.profiles.upsert(db_session, profile)
from router.models import (
    IncomingMessage,
    RoutingDecision,
    UserProfile,
)


@pytest.fixture
def client() -> TestClient:
    """TestClient fixture with active lifespan."""
    with TestClient(app) as test_client:
        yield test_client


def test_health_check(client: TestClient) -> None:
    """Test health check endpoint returns 200 and model name."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["model"] == GEMINI_MODEL


@pytest.mark.anyio
async def test_get_user_profile_existing(client: TestClient, populated_db) -> None:
    """Test retrieving an existing user profile loaded from fixtures."""
    response = client.get("/users/user_priya/profile")
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "user_priya"
    assert data["name"] == "Priya Sharma"
    assert "school fees" in data["interests"]


def test_get_user_profile_default(client: TestClient) -> None:
    """Test retrieving a non-existent user returns a default balanced profile."""
    response = client.get("/users/unknown_user_123/profile")
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "unknown_user_123"
    assert data["sensitivity"] == "balanced"


def test_update_user_profile_success(client: TestClient) -> None:
    """Test updating a user profile with matching user_id."""
    profile_payload = {
        "user_id": "test_user_update",
        "name": "Test Update Name",
        "priority_contacts": ["+1234567890"],
        "muted_chats": [],
        "interests": ["tech", "ai"],
        "blocked_categories": ["spam"],
        "work_hours": {"start": "10:00", "end": "19:00"},
        "sensitivity": "aggressive_filter",
    }
    response = client.put("/users/test_user_update/profile", json=profile_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "test_user_update"
    assert data["name"] == "Test Update Name"
    assert data["sensitivity"] == "aggressive_filter"

    # Verify retrieval
    get_res = client.get("/users/test_user_update/profile")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Test Update Name"


def test_update_user_profile_mismatched_id(client: TestClient) -> None:
    """Test that mismatch between path user_id and body user_id returns 400."""
    profile_payload = {
        "user_id": "body_user_id",
        "name": "Mismatched User",
        "priority_contacts": [],
        "muted_chats": [],
        "interests": [],
        "blocked_categories": [],
        "work_hours": None,
        "sensitivity": "balanced",
    }
    response = client.put("/users/path_user_id/profile", json=profile_payload)
    assert response.status_code == 400
    assert "does not match body user_id" in response.json()["detail"]


def test_get_user_history(client: TestClient) -> None:
    """Test getting user history."""
    # History for a fresh user should be empty
    response = client.get("/users/user_priya/history?limit=10")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_route_message_mock(client: TestClient) -> None:
    """Test /route endpoint with mocked router engine."""
    mock_decision = RoutingDecision(
        action="notify",
        confidence=0.95,
        reasoning="Urgent family message from spouse.",
        category="urgent_personal",
        risk_flags=[],
    )

    app.state.router.route = AsyncMock(return_value=mock_decision)

    payload = {
        "user_id": "user_priya",
        "message": {
            "message_id": "msg_test_001",
            "timestamp": "2026-08-28T12:00:00Z",
            "sender_id": "sender_husband_amit",
            "sender_name": "Amit",
            "chat_id": "chat_dm_amit",
            "chat_name": "Amit",
            "chat_type": "dm",
            "content_type": "text",
            "text": "Please pick up the groceries",
            "media_path": None,
            "is_forwarded": False,
            "forward_count": None,
            "mentions": [],
            "reply_to_message_id": None,
        },
    }

    response = client.post("/route", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "notify"
    assert data["confidence"] == 0.95
    assert data["category"] == "urgent_personal"


def test_route_batch_mock(client: TestClient) -> None:
    """Test /route/batch endpoint with mocked router engine."""
    mock_decisions = [
        RoutingDecision(
            action="notify",
            confidence=0.9,
            reasoning="Important update.",
            category="work",
        ),
        RoutingDecision(
            action="mute",
            confidence=0.85,
            reasoning="Good morning greeting forward.",
            category="chain_forwards",
        ),
    ]

    app.state.router.route_batch = AsyncMock(return_value=mock_decisions)

    payload = {
        "user_id": "user_priya",
        "messages": [
            {
                "message_id": "msg_001",
                "timestamp": "2026-08-28T12:00:00Z",
                "sender_id": "sender_boss",
                "sender_name": "Manager",
                "chat_id": "chat_work",
                "chat_name": "Work",
                "chat_type": "dm",
                "content_type": "text",
                "text": "Project deadline update",
                "media_path": None,
                "is_forwarded": False,
            },
            {
                "message_id": "msg_002",
                "timestamp": "2026-08-28T12:01:00Z",
                "sender_id": "sender_relative",
                "sender_name": "Uncle",
                "chat_id": "chat_family",
                "chat_name": "Family",
                "chat_type": "group",
                "content_type": "text",
                "text": "Good morning!",
                "is_forwarded": True,
            },
        ],
    }

    response = client.post("/route/batch", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["action"] == "notify"
    assert data[1]["action"] == "mute"
