"""Pydantic data models for the WhatsApp notification router."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Incoming message
# ---------------------------------------------------------------------------

class IncomingMessage(BaseModel):
    """A single incoming WhatsApp message to be routed."""

    message_id: str = Field(description="Unique message identifier.")
    timestamp: datetime = Field(description="When the message was sent.")
    sender_id: str = Field(description="Phone number or business account ID of the sender.")
    sender_name: str = Field(description="Display name of the sender.")
    chat_id: str = Field(description="Group ID or DM thread identifier.")
    chat_name: str = Field(description="Display name of the chat / group.")
    chat_type: Literal["dm", "group", "broadcast", "business"] = Field(
        description="Type of the chat."
    )
    content_type: Literal["text", "image", "voice_note", "image_with_caption"] = Field(
        description="Primary content type of the message."
    )
    text: Optional[str] = Field(default=None, description="Text body or image caption.")
    media_path: Optional[str] = Field(
        default=None, description="Local path to image or audio file."
    )
    is_forwarded: bool = Field(default=False, description="Whether the message is forwarded.")
    forward_count: Optional[int] = Field(
        default=None,
        description="How many times this message has been forwarded (WhatsApp shows >5).",
    )
    mentions: list[str] = Field(
        default_factory=list,
        description="List of user IDs @-mentioned in the message.",
    )
    reply_to_message_id: Optional[str] = Field(
        default=None, description="ID of the message this is replying to."
    )


# ---------------------------------------------------------------------------
# User profile & preferences
# ---------------------------------------------------------------------------

class UserProfile(BaseModel):
    """The receiving user's preferences for notification routing."""

    user_id: str
    name: str
    priority_contacts: list[str] = Field(
        default_factory=list,
        description="Sender IDs that should always trigger a notification.",
    )
    muted_chats: list[str] = Field(
        default_factory=list,
        description="Chat IDs the user has muted.",
    )
    interests: list[str] = Field(
        default_factory=list,
        description="Topics the user cares about, e.g. 'school fees', 'cricket'.",
    )
    blocked_categories: list[str] = Field(
        default_factory=list,
        description="Message categories to always mute, e.g. 'promotions', 'chain_forwards'.",
    )
    work_hours: Optional[dict] = Field(
        default=None,
        description="When work-related messages should be prioritized, e.g. {'start': '09:00', 'end': '18:00'}.",
    )
    sensitivity: Literal["aggressive_filter", "balanced", "miss_nothing"] = Field(
        default="balanced",
        description="How aggressively the router should filter messages.",
    )


# ---------------------------------------------------------------------------
# Sender context
# ---------------------------------------------------------------------------

class SenderContext(BaseModel):
    """Contextual metadata about a message sender."""

    sender_id: str
    display_name: str
    sender_type: Literal["person", "business", "bot", "unknown"] = Field(default="unknown")
    is_in_contacts: bool = Field(default=False)
    trust_score: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Trust score from 0 (untrusted) to 1 (fully trusted).",
    )
    relationship: Optional[str] = Field(
        default=None,
        description="Relationship to user, e.g. 'family', 'coworker', 'school_admin'.",
    )
    recent_message_count_24h: int = Field(
        default=0,
        description="Number of messages sent in the last 24 hours.",
    )
    spam_reports: int = Field(
        default=0,
        description="Number of times this sender's messages have been flagged.",
    )


# ---------------------------------------------------------------------------
# Group / chat context
# ---------------------------------------------------------------------------

class GroupContext(BaseModel):
    """Contextual metadata about a chat or group."""

    chat_id: str
    chat_name: str
    chat_type: Literal["dm", "group", "broadcast", "business"] = Field(default="group")
    member_count: Optional[int] = Field(default=None)
    category: Optional[str] = Field(
        default=None,
        description="Category of the chat, e.g. 'family', 'society', 'work', 'school'.",
    )
    user_engagement_rate: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="How often the user reads/replies in this chat (0=never, 1=always).",
    )
    is_muted_by_user: bool = Field(default=False)


# ---------------------------------------------------------------------------
# Routing decision (Gemini structured output)
# ---------------------------------------------------------------------------

Action = Literal["notify", "digest", "mute", "reply"]

class RoutingDecision(BaseModel):
    """The AI-generated routing decision for a single message."""

    action: Action = Field(
        description="The final routing decision: notify, mute, digest, or reply"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0",
    )
    reasoning: str = Field(
        description="Explanation for why this decision was made",
    )
    reply_text: Optional[str] = Field(
        default=None,
        description="If action is 'reply', the conversational text to send back to the user via WhatsApp",
    )
    category: str = Field(
        description="Detected message category, e.g. 'urgent_personal', 'promotion', 'scam', 'school_update'.",
    )
    risk_flags: list[str] = Field(
        default_factory=list,
        description="Risk indicators, e.g. 'suspicious_link', 'high_forward_count', 'unknown_sender'.",
    )
    digest_priority: Optional[Literal["high", "medium", "low"]] = Field(
        default=None,
        description="Within digest, how soon to surface this message.",
    )
    media_summary: Optional[str] = Field(
        default=None,
        description="Brief summary of what the attached image or audio contained.",
    )


# ---------------------------------------------------------------------------
# Routing request (API payload)
# ---------------------------------------------------------------------------

class RouteRequest(BaseModel):
    """API request body for routing a single message."""

    message: IncomingMessage
    user_id: str


class BatchRouteRequest(BaseModel):
    """API request body for routing multiple messages."""

    messages: list[IncomingMessage]
    user_id: str
