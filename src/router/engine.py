"""Core WhatsApp notification routing engine using Gemini."""

from __future__ import annotations

import logging
from pathlib import Path
import re
from typing import Any, Optional

from sqlalchemy import select
from router.db_models import DBInteractionHistory

from router.config import (
    EMERGENCY_KEYWORDS,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    HISTORY_CONTEXT_WINDOW,
    MIN_CONFIDENCE_THRESHOLD,
    PHISHING_DOMAIN_KEYWORDS,
    SCAM_TEXT_PATTERNS,
)
from router.history import InteractionHistory
from router.models import IncomingMessage, RoutingDecision, UserProfile
from router.profiles import ProfileStore
from router.prompt import build_system_prompt, compose_input
from router.registry import SenderGroupRegistry

logger = logging.getLogger(__name__)


class NotificationRouter:
    """AI-powered WhatsApp notification routing engine.

    Evaluates incoming WhatsApp messages against user preferences, sender trust,
    chat dynamics, and historical interactions using rule-based fast paths and
    multimodal Gemini evaluations.
    """

    def __init__(
        self,
        api_key: str | None = None,
        client: Any = None,
    ) -> None:
        """Initialize the router with Gemini client and data stores.

        Args:
            api_key: Optional Gemini API key. Falls back to GEMINI_API_KEY env var.
            client: Optional pre-configured genai.Client instance (useful for testing).
        """
        if client is not None:
            self.client = client
        else:
            try:
                from google import genai

                resolved_key = api_key or GEMINI_API_KEY
                self.client = genai.Client(api_key=resolved_key)
            except Exception as err:
                logger.warning("Could not initialize google-genai Client: %s", err)
                self.client = None

        self.profiles = ProfileStore()
        self.registry = SenderGroupRegistry()
        self.history = InteractionHistory()

    def _check_hard_rules(
        self,
        message: IncomingMessage,
        user: UserProfile,
    ) -> RoutingDecision | None:
        """Apply hard-coded rules BEFORE calling the LLM.

        Returns a RoutingDecision if a hard rule matches, None if the LLM should decide.

        Hard rules:
        1. If sender_id is in user.priority_contacts and the message is NOT a chain forward → notify
           (but DON'T skip LLM for media messages from priority contacts — let LLM analyze the media)
        2. If message text matches SCAM_TEXT_PATTERNS → mute with risk_flags=["scam_pattern"]
        3. If message text contains PHISHING_DOMAIN_KEYWORDS → mute with risk_flags=["phishing_domain"]
        4. If message contains EMERGENCY_KEYWORDS → notify with category="emergency"
        5. If user is mentioned in a muted chat → DO NOT apply mute-chat rule (let LLM decide, likely notify)
        6. If chat_id is in user.muted_chats and user is NOT mentioned → mute
        7. If is_forwarded and forward_count >= 5 and "chain_forwards" in blocked_categories → mute

        Rules are checked in priority order. Note: some rules only apply to text messages.

        Args:
            message: Incoming WhatsApp message to inspect.
            user: Receiving user profile and preferences.

        Returns:
            RoutingDecision if a deterministic rule matched, otherwise None.
        """
        text = message.text
        text_lower = text.lower() if text is not None else ""
        has_media = bool(message.media_path) or message.content_type in (
            "image",
            "image_with_caption",
            "voice_note",
        )
        is_chain_forward = message.is_forwarded and (
            message.forward_count is not None and message.forward_count >= 5
        )

        # 1. Priority contacts: text messages from priority contacts not forwarded as chain
        if message.sender_id in user.priority_contacts:
            if not has_media and not is_chain_forward:
                return RoutingDecision(
                    action="notify",
                    confidence=1.0,
                    reasoning=f"Sender '{message.sender_name}' is in priority contacts list.",
                    category="priority_contact",
                    risk_flags=[],
                )
            # If it has media, do not fast-path notify here — let the multimodal LLM analyze the media.

        # 2. Scam text pattern matches
        if text_lower:
            for pattern in SCAM_TEXT_PATTERNS:
                if pattern.lower() in text_lower:
                    return RoutingDecision(
                        action="mute",
                        confidence=0.98,
                        reasoning=f"Message matched known scam pattern: '{pattern}'.",
                        category="scam",
                        risk_flags=["scam_pattern"],
                    )

        # 3. Phishing domain keyword matches
        if text_lower:
            for keyword in PHISHING_DOMAIN_KEYWORDS:
                if keyword.lower() in text_lower:
                    return RoutingDecision(
                        action="mute",
                        confidence=0.98,
                        reasoning=f"Message contained suspicious phishing domain/link: '{keyword}'.",
                        category="phishing",
                        risk_flags=["phishing_domain"],
                    )

        # 4. Emergency keywords
        if text_lower:
            for keyword in EMERGENCY_KEYWORDS:
                pattern = rf"\b{re.escape(keyword.lower())}\b"
                if re.search(pattern, text_lower):
                    return RoutingDecision(
                        action="notify",
                        confidence=0.99,
                        reasoning=f"Emergency keyword detected: '{keyword}'. Immediate notification triggered.",
                        category="emergency",
                        risk_flags=[],
                    )

        # 5 & 6. Muted chat rules
        if message.chat_id in user.muted_chats:
            is_mentioned = (user.user_id in message.mentions) or bool(
                user.name and f"@{user.name.lower()}" in text_lower
            )
            if is_mentioned:
                # Rule 5: User is mentioned in a muted chat -> DO NOT apply mute-chat rule (let LLM decide)
                pass
            else:
                # Rule 6: Chat is muted and user is not mentioned -> mute
                return RoutingDecision(
                    action="mute",
                    confidence=0.95,
                    reasoning=f"Chat '{message.chat_name}' is in user's muted chats list and user is not mentioned.",
                    category="muted_chat",
                    risk_flags=[],
                )

        # 7. Chain forwards in blocked categories
        if is_chain_forward and "chain_forwards" in user.blocked_categories:
            return RoutingDecision(
                action="mute",
                confidence=0.95,
                reasoning="Frequently forwarded chain message is blocked by user preferences.",
                category="chain_forward",
                risk_flags=["high_forward_count"],
            )

        return None

    def _apply_safety_overrides(
        self,
        decision: RoutingDecision,
        message: IncomingMessage,
    ) -> RoutingDecision:
        """Post-LLM safety overrides.

        If the LLM says notify/digest but the message has scam/phishing indicators,
        override to mute.

        If confidence < MIN_CONFIDENCE_THRESHOLD, fall back to digest.

        Args:
            decision: Initial RoutingDecision from LLM or rule.
            message: The original IncomingMessage.

        Returns:
            Final RoutingDecision after safety and confidence checks.
        """
        text_lower = (message.text or "").lower()
        has_scam_pattern = any(p.lower() in text_lower for p in SCAM_TEXT_PATTERNS)
        has_phishing_domain = any(kw.lower() in text_lower for kw in PHISHING_DOMAIN_KEYWORDS)
        has_risk_scam_flag = any(
            f in ("scam_pattern", "phishing_domain", "suspicious_link") for f in decision.risk_flags
        )
        is_scam_category = decision.category.lower() in ("scam", "phishing", "fraud")

        # Safety override for scams / phishing
        if (
            has_scam_pattern
            or has_phishing_domain
            or has_risk_scam_flag
            or is_scam_category
        ) and decision.action != "mute":
            flags = list(decision.risk_flags)
            if has_scam_pattern and "scam_pattern" not in flags:
                flags.append("scam_pattern")
            if has_phishing_domain and "phishing_domain" not in flags:
                flags.append("phishing_domain")

            category = "scam" if (has_scam_pattern or is_scam_category) else "phishing"
            return RoutingDecision(
                action="mute",
                confidence=max(decision.confidence, 0.95),
                reasoning=(
                    f"Safety override: Message contains scam or phishing indicators. "
                    f"Suppressing notification. (Original reasoning: {decision.reasoning})"
                ),
                category=category,
                risk_flags=flags,
                digest_priority=None,
                media_summary=decision.media_summary,
            )

        # Confidence fallback to digest
        if decision.confidence < MIN_CONFIDENCE_THRESHOLD:
            if decision.action != "digest":
                return RoutingDecision(
                    action="digest",
                    confidence=decision.confidence,
                    reasoning=(
                        f"Confidence {decision.confidence:.2f} below threshold "
                        f"({MIN_CONFIDENCE_THRESHOLD}), defaulting to digest. "
                        f"(Original reasoning: {decision.reasoning})"
                    ),
                    category=decision.category,
                    risk_flags=decision.risk_flags,
                    digest_priority=decision.digest_priority or "medium",
                    media_summary=decision.media_summary,
                )

        # Ensure digest decisions always have a valid digest_priority
        if decision.action == "digest" and not decision.digest_priority:
            return decision.model_copy(update={"digest_priority": "medium"})

        return decision

    async def route(self, db: Any, message: IncomingMessage, user_id: str) -> RoutingDecision:
        """Route a single message for a specific user.

        Pipeline:
        1. Load user profile, sender context, group context
        2. Check hard rules (fast path, no API call)
        3. If no hard rule matches: compose prompt, call Gemini with structured output
        4. Parse the RoutingDecision from structured output
        5. Apply safety overrides
        6. Record decision in history
        7. Return decision

        Args:
            db: Async database session.
            message: The incoming WhatsApp message to evaluate.
            user_id: Unique identifier of the receiving user.

        Returns:
            RoutingDecision instance with routing action, confidence, reasoning, and metadata.
        """
        # 1. Load contexts
        user = await self.profiles.get(db, user_id)
        sender = await self.registry.get_sender(db, message.sender_id, default_name=message.sender_name)
        group = await self.registry.get_group(db, message.chat_id, default_name=message.chat_name)

        if message.chat_id in user.muted_chats:
            group.is_muted_by_user = True

        # 2. Check hard rules (fast path)
        hard_decision = self._check_hard_rules(message, user)
        if hard_decision is not None:
            final_decision = self._apply_safety_overrides(hard_decision, message)
            await self.history.record(db, user_id, message, final_decision)
            await self.registry.increment_message_count(db, message.sender_id)
            logger.info(
                "Routed message %s for user %s via hard rule: action=%s, category=%s, confidence=%.2f",
                message.message_id,
                user_id,
                final_decision.action,
                final_decision.category,
                final_decision.confidence,
            )
            return final_decision

        # 3. Call Gemini with structured output
        recent_history = await self.history.get_recent(db, user_id, limit=HISTORY_CONTEXT_WINDOW)
        input_parts = compose_input(
            message=message,
            user=user,
            sender=sender,
            group=group,
            recent_history=recent_history,
        )
        system_prompt = build_system_prompt()

        from google.genai import types
        import base64

        gemini_contents = []
        for p in input_parts:
            if p.get("type") == "text":
                gemini_contents.append(p["text"])
            elif p.get("type") in ("image", "audio"):
                gemini_contents.append(
                    types.Part.from_bytes(
                        data=base64.b64decode(p["data"]),
                        mime_type=p["mime_type"]
                    )
                )

        decision: RoutingDecision
        if self.client is None:
            logger.warning("Gemini client is not initialized; falling back to digest.")
            decision = RoutingDecision(
                action="digest",
                confidence=0.1,
                reasoning="API call failed, defaulting to digest",
                category="unknown",
                risk_flags=[],
                digest_priority="medium",
            )
        else:
            try:
                response = self.client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=gemini_contents,
                    config={
                        "system_instruction": system_prompt,
                        "response_mime_type": "application/json",
                        "response_schema": RoutingDecision,
                    },
                )
                raw_text = response.text if response and response.text else "{}"
                decision = RoutingDecision.model_validate_json(raw_text)
            except Exception as err:
                logger.error("Gemini API call failed for message %s: %s", message.message_id, err)
                decision = RoutingDecision(
                    action="digest",
                    confidence=0.1,
                    reasoning=f"API call failed, defaulting to digest: {err}",
                    category="unknown",
                    risk_flags=[],
                    digest_priority="medium",
                )

        # 5. Apply safety overrides
        final_decision = self._apply_safety_overrides(decision, message)

        # 6. Record decision in history and update metadata
        await self.history.record(db, user_id, message, final_decision)
        await self.registry.increment_message_count(db, message.sender_id)
        if (
            final_decision.category in ("scam", "phishing")
            or "scam_pattern" in final_decision.risk_flags
            or "phishing_domain" in final_decision.risk_flags
        ):
            await self.registry.report_spam(db, message.sender_id)

        logger.info(
            "Routed message %s for user %s: action=%s, category=%s, confidence=%.2f",
            message.message_id,
            user_id,
            final_decision.action,
            final_decision.category,
            final_decision.confidence,
        )

        # 7. Execute Agentic Reply
        if final_decision.action == "reply" and final_decision.reply_text:
            from router.meta_api import send_whatsapp_message
            import asyncio
            # Fire and forget the reply
            asyncio.create_task(send_whatsapp_message(message.sender_id, final_decision.reply_text))
            
            # Also update the db record with the ai reply text
            stmt = select(DBInteractionHistory).where(DBInteractionHistory.message_id == message.message_id)
            result = await db.execute(stmt)
            history_record = result.scalar_one_or_none()
            if history_record:
                history_record.ai_reply_text = final_decision.reply_text
                await db.commit()

        # 8. Return decision
        return final_decision

    async def route_batch(
        self,
        db: Any,
        messages: list[IncomingMessage],
        user_id: str,
    ) -> list[RoutingDecision]:
        """Route multiple messages sequentially for a user.

        Args:
            db: Async database session.
            messages: List of incoming WhatsApp messages to route.
            user_id: Unique identifier for the user.

        Returns:
            List of RoutingDecision instances corresponding to each message.
        """
        decisions: list[RoutingDecision] = []
        for message in messages:
            decision = await self.route(db, message, user_id)
            decisions.append(decision)
        return decisions
