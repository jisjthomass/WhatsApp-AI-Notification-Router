"""Pydantic data models for Meta WhatsApp Cloud API Webhook payloads."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class Profile(BaseModel):
    """WhatsApp user profile."""
    name: str | None = None


class Contact(BaseModel):
    """WhatsApp contact information."""
    profile: Profile | None = None
    wa_id: str


class Text(BaseModel):
    """Text message content."""
    body: str


class Media(BaseModel):
    """Media message content (image, audio, document, video, sticker)."""
    id: str
    mime_type: str | None = None
    sha256: str | None = None
    caption: str | None = None


class Context(BaseModel):
    """Context for a message (replies, forwards)."""
    forwarded: bool | None = False
    frequently_forwarded: bool | None = False
    from_: str | None = Field(default=None, alias="from")
    id: str | None = None
    mentions: list[str] | None = None


class Message(BaseModel):
    """A WhatsApp message within the webhook."""
    id: str
    from_: str = Field(alias="from")
    timestamp: str
    type: str
    text: Text | None = None
    image: Media | None = None
    audio: Media | None = None
    voice: Media | None = None
    document: Media | None = None
    video: Media | None = None
    sticker: Media | None = None
    context: Context | None = None


class Metadata(BaseModel):
    """Metadata about the receiving business account."""
    display_phone_number: str
    phone_number_id: str


class Value(BaseModel):
    """The value object containing messages and statuses."""
    messaging_product: str
    metadata: Metadata
    contacts: list[Contact] | None = None
    messages: list[Message] | None = None
    statuses: list[Any] | None = None


class Change(BaseModel):
    """A change event."""
    value: Value
    field: str


class Entry(BaseModel):
    """An entry in the webhook payload."""
    id: str
    changes: list[Change]


class WebhookPayload(BaseModel):
    """The top-level Meta WhatsApp Cloud API webhook payload."""
    object: str
    entry: list[Entry]
