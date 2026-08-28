"""Parser for Meta WhatsApp Cloud API webhooks."""

from __future__ import annotations

from datetime import datetime, timezone
import logging

from router.models import IncomingMessage
from router.webhook_models import WebhookPayload

logger = logging.getLogger(__name__)


def parse_whatsapp_webhook(payload: dict) -> list[IncomingMessage]:
    """
    Parse a raw Meta WhatsApp webhook payload into internal IncomingMessage objects.

    Args:
        payload (dict): The raw JSON payload from the Meta webhook.

    Returns:
        list[IncomingMessage]: A list of validated IncomingMessage objects.
    """
    try:
        webhook_data = WebhookPayload.model_validate(payload)
    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        return []

    if webhook_data.object != "whatsapp_business_account":
        return []

    incoming_messages = []

    for entry in webhook_data.entry:
        for change in entry.changes:
            # We only care about message updates
            if change.field != "messages":
                continue

            value = change.value

            # Skip if there are no messages (e.g., this is just a status update)
            if not value.messages:
                continue

            # Parse contacts to build a sender_id -> sender_name mapping
            sender_name_map = {}
            if value.contacts:
                for contact in value.contacts:
                    if contact.profile and contact.profile.name:
                        sender_name_map[contact.wa_id] = contact.profile.name

            for msg in value.messages:
                message_id = msg.id
                sender_id = msg.from_
                sender_name = sender_name_map.get(sender_id, "Unknown")

                try:
                    ts = datetime.fromtimestamp(int(msg.timestamp), tz=timezone.utc)
                except ValueError:
                    ts = datetime.now(timezone.utc)

                # For standard WhatsApp Cloud API, most are DMs where sender_id is the user.
                # In group setups, this might differ, but we fallback to DM behavior here.
                chat_id = sender_id
                chat_name = sender_name
                chat_type = "dm"

                text = None
                media_path = None
                content_type = "text"

                if msg.type == "text" and msg.text:
                    content_type = "text"
                    text = msg.text.body
                elif msg.type == "image" and msg.image:
                    content_type = "image_with_caption" if msg.image.caption else "image"
                    text = msg.image.caption
                    # We store media_id in media_path to fetch later
                    media_path = msg.image.id
                elif msg.type == "audio" and msg.audio:
                    content_type = "voice_note"
                    media_path = msg.audio.id
                elif msg.type == "voice" and msg.voice:
                    content_type = "voice_note"
                    media_path = msg.voice.id
                else:
                    # Fallback for unsupported types
                    content_type = "text"
                    text = f"[Unsupported message type: {msg.type}]"

                is_forwarded = False
                forward_count = None
                mentions = []
                reply_to_message_id = None

                if msg.context:
                    is_forwarded = bool(msg.context.forwarded or msg.context.frequently_forwarded)
                    if msg.context.frequently_forwarded:
                        forward_count = 5  # WhatsApp indicates frequently forwarded (5+ times)

                    if msg.context.mentions:
                        mentions = msg.context.mentions

                    reply_to_message_id = msg.context.id

                try:
                    incoming_msg = IncomingMessage(
                        message_id=message_id,
                        timestamp=ts,
                        sender_id=sender_id,
                        sender_name=sender_name,
                        chat_id=chat_id,
                        chat_name=chat_name,
                        chat_type=chat_type,
                        content_type=content_type,
                        text=text,
                        media_path=media_path,
                        is_forwarded=is_forwarded,
                        forward_count=forward_count,
                        mentions=mentions,
                        reply_to_message_id=reply_to_message_id,
                    )
                    incoming_messages.append(incoming_msg)
                except Exception as e:
                    logger.error(f"Failed to create IncomingMessage for {message_id}: {e}")

    return incoming_messages
