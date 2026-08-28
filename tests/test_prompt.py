"""Unit tests for router.prompt module."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import pytest

from router.models import (
    GroupContext,
    IncomingMessage,
    RoutingDecision,
    SenderContext,
    UserProfile,
)
from router.prompt import (
    SYSTEM_PROMPT,
    build_context_block,
    build_system_prompt,
    compose_input,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def sample_user() -> UserProfile:
    """Sample user profile fixture."""
    return UserProfile(
        user_id="user_priya",
        name="Priya Sharma",
        priority_contacts=["sender_husband_amit", "sender_mother"],
        muted_chats=["chat_office_memes"],
        interests=["school fees", "society maintenance"],
        blocked_categories=["promotions", "chain_forwards"],
        work_hours={"start": "09:00", "end": "18:00"},
        sensitivity="balanced",
    )


@pytest.fixture
def sample_sender() -> SenderContext:
    """Sample sender context fixture."""
    return SenderContext(
        sender_id="sender_husband_amit",
        display_name="Amit",
        sender_type="person",
        is_in_contacts=True,
        trust_score=0.95,
        relationship="spouse",
        recent_message_count_24h=5,
        spam_reports=0,
    )


@pytest.fixture
def sample_group() -> GroupContext:
    """Sample group context fixture."""
    return GroupContext(
        chat_id="chat_greenpark_society",
        chat_name="Green Park Society",
        chat_type="group",
        member_count=120,
        category="society",
        user_engagement_rate=0.75,
        is_muted_by_user=False,
    )


class TestSystemPrompt:
    """Tests for system prompt construction."""

    def test_build_system_prompt(self) -> None:
        """Verify system prompt returns expected content and critical rules."""
        prompt = build_system_prompt()
        assert prompt == SYSTEM_PROMPT
        assert "WhatsApp notification router" in prompt
        assert "notify" in prompt
        assert "digest" in prompt
        assert "mute" in prompt
        assert "CORE SAFETY-FIRST RULES" in prompt
        assert "PRIORITY ESCALATION RULES" in prompt
        assert "PERSONALIZATION & CONTEXT RUBRIC" in prompt
        assert "DIGEST HEURISTICS & PRIORITIZATION" in prompt
        assert "MUTE HEURISTICS" in prompt
        assert "MULTIMODAL ANALYSIS INSTRUCTIONS" in prompt
        assert "CONFIDENCE CALIBRATION" in prompt
        assert "RoutingDecision" in prompt


class TestBuildContextBlock:
    """Tests for build_context_block function."""

    def test_build_context_block_with_history(
        self,
        sample_user: UserProfile,
        sample_sender: SenderContext,
        sample_group: GroupContext,
    ) -> None:
        """Verify context block includes user, sender, group, and history details."""
        history = [
            {
                "message_id": "msg_001",
                "sender_id": "sender_husband_amit",
                "category": "personal",
                "action": "notify",
                "text": "Hello there",
            }
        ]
        context = build_context_block(
            user=sample_user,
            sender=sample_sender,
            group=sample_group,
            recent_history=history,
        )

        assert "Priya Sharma" in context
        assert "sender_husband_amit" in context
        assert "Green Park Society" in context
        assert "spouse" in context
        assert "0.95" in context
        assert "school fees" in context
        assert "promotions" in context
        assert "msg_001" in context

    def test_build_context_block_empty_history(
        self,
        sample_user: UserProfile,
        sample_sender: SenderContext,
        sample_group: GroupContext,
    ) -> None:
        """Verify context block handles empty history gracefully."""
        context = build_context_block(
            user=sample_user,
            sender=sample_sender,
            group=sample_group,
            recent_history=[],
        )
        assert "No recent routing history" in context

    def test_build_context_block_history_window_limit(
        self,
        sample_user: UserProfile,
        sample_sender: SenderContext,
        sample_group: GroupContext,
    ) -> None:
        """Verify history window is capped at HISTORY_CONTEXT_WINDOW."""
        history = [
            {
                "message_id": f"msg_{i:03d}",
                "sender_id": "sender_test",
                "category": "test",
                "action": "mute",
                "text": f"Test message {i}",
            }
            for i in range(25)
        ]
        context = build_context_block(
            user=sample_user,
            sender=sample_sender,
            group=sample_group,
            recent_history=history,
        )
        # Should contain the last 10 entries (msg_015 to msg_024)
        assert "last 10 decisions" in context
        assert "msg_024" in context
        assert "msg_001" not in context


class TestComposeInput:
    """Tests for compose_input multimodal prompt construction."""

    def test_compose_input_text_message(
        self,
        sample_user: UserProfile,
        sample_sender: SenderContext,
        sample_group: GroupContext,
    ) -> None:
        """Verify text message generates a single text content part."""
        msg = IncomingMessage(
            message_id="msg_text_01",
            timestamp=datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc),
            sender_id="sender_husband_amit",
            sender_name="Amit",
            chat_id="chat_dm_amit",
            chat_name="Amit",
            chat_type="dm",
            content_type="text",
            text="Can you pick up milk on your way home?",
            media_path=None,
        )

        parts = compose_input(
            message=msg,
            user=sample_user,
            sender=sample_sender,
            group=sample_group,
            recent_history=[],
        )

        assert len(parts) == 1
        assert parts[0]["type"] == "text"
        assert "Can you pick up milk" in parts[0]["text"]
        assert "msg_text_01" in parts[0]["text"]

    def test_compose_input_image_message(
        self,
        sample_user: UserProfile,
        sample_sender: SenderContext,
        sample_group: GroupContext,
    ) -> None:
        """Verify image message generates text and image parts."""
        img_path = str(FIXTURES_DIR / "media" / "maintenance_notice.png")
        msg = IncomingMessage(
            message_id="msg_img_01",
            timestamp=datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc),
            sender_id="sender_society_admin",
            sender_name="Society Admin",
            chat_id="chat_greenpark_society",
            chat_name="Green Park Society",
            chat_type="group",
            content_type="image_with_caption",
            text="Notice regarding lift maintenance",
            media_path=img_path,
        )

        parts = compose_input(
            message=msg,
            user=sample_user,
            sender=sample_sender,
            group=sample_group,
            recent_history=[],
        )

        assert len(parts) == 2
        assert parts[0]["type"] == "text"
        assert parts[1]["type"] == "image"
        assert parts[1]["mime_type"] == "image/png"
        assert len(parts[1]["data"]) > 0

    def test_compose_input_audio_message(
        self,
        sample_user: UserProfile,
        sample_sender: SenderContext,
        sample_group: GroupContext,
    ) -> None:
        """Verify audio voice note generates text and audio parts."""
        audio_path = str(FIXTURES_DIR / "media" / "school_closure.ogg")
        msg = IncomingMessage(
            message_id="msg_audio_01",
            timestamp=datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc),
            sender_id="sender_mother",
            sender_name="Mummy",
            chat_id="chat_dm_mother",
            chat_name="Mummy",
            chat_type="dm",
            content_type="voice_note",
            text=None,
            media_path=audio_path,
        )

        parts = compose_input(
            message=msg,
            user=sample_user,
            sender=sample_sender,
            group=sample_group,
            recent_history=[],
        )

        assert len(parts) == 2
        assert parts[0]["type"] == "text"
        assert parts[1]["type"] == "audio"
        assert parts[1]["mime_type"] == "audio/ogg"
        assert len(parts[1]["data"]) > 0

    def test_compose_input_missing_media_handled_gracefully(
        self,
        sample_user: UserProfile,
        sample_sender: SenderContext,
        sample_group: GroupContext,
    ) -> None:
        """Verify missing media file does not crash compose_input."""
        msg = IncomingMessage(
            message_id="msg_missing_01",
            timestamp=datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc),
            sender_id="sender_test",
            sender_name="Tester",
            chat_id="chat_dm_test",
            chat_name="Tester",
            chat_type="dm",
            content_type="image",
            text="Broken image message",
            media_path="/nonexistent/missing_file.png",
        )

        parts = compose_input(
            message=msg,
            user=sample_user,
            sender=sample_sender,
            group=sample_group,
            recent_history=[],
        )

        # Should only have the text part without crashing
        assert len(parts) == 1
        assert parts[0]["type"] == "text"
