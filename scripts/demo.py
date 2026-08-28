#!/usr/bin/env python3
"""Interactive CLI demo for the WhatsApp AI Notification Router.

Demonstrates intelligent multimodal notification routing for two distinct
user profiles (Priya and Rahul) across 10 diverse message scenarios.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any, Optional

# Configure base paths and import src
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from router.config import (
    DEFAULT_TRUST_SCORE,
    EMERGENCY_KEYWORDS,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    HISTORY_CONTEXT_WINDOW,
    MIN_CONFIDENCE_THRESHOLD,
    PHISHING_DOMAIN_KEYWORDS,
    SCAM_TEXT_PATTERNS,
)
from router.history import InteractionHistory
from router.models import (
    GroupContext,
    IncomingMessage,
    RoutingDecision,
    SenderContext,
    UserProfile,
)
from router.profiles import ProfileStore
from router.prompt import SYSTEM_PROMPT, compose_input
from router.registry import SenderGroupRegistry

# ---------------------------------------------------------------------------
# ANSI Terminal Styling
# ---------------------------------------------------------------------------
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
UNDERLINE = "\033[4m"

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"
GRAY = "\033[90m"

BG_DARK = "\033[48;5;236m"
BG_BLUE = "\033[44m"
BG_MAGENTA = "\033[45m"


def format_action_badge(action: str) -> str:
    """Format routing action with color-coded ANSI badge."""
    match action.lower():
        case "notify":
            return f"{BOLD}{RED}🔴 NOTIFY{RESET}"
        case "digest":
            return f"{BOLD}{YELLOW}🟡 DIGEST{RESET}"
        case "mute":
            return f"{DIM}{GRAY}⚫ MUTE  {RESET}"
        case _:
            return f"{WHITE}{action.upper()}{RESET}"


def format_confidence_bar(conf: float) -> str:
    """Format a 10-char colored confidence meter."""
    pct = int(round(conf * 100))
    filled = int(round(conf * 10))
    empty = 10 - filled
    if conf >= 0.85:
        color = GREEN
    elif conf >= 0.5:
        color = YELLOW
    else:
        color = RED
    return f"{color}{'█' * filled}{'░' * empty}{RESET} {pct}%"


# ---------------------------------------------------------------------------
# NotificationRouter Engine
# ---------------------------------------------------------------------------
class NotificationRouter:
    """Intelligent WhatsApp Notification Router coordinating context and Gemini evaluation."""

    def __init__(
        self,
        fixtures_dir: Path | str | None = None,
        api_key: str | None = None,
        model: str = GEMINI_MODEL,
    ) -> None:
        """Initialize router with profile store, context registry, and history tracker."""
        self.fixtures_dir = Path(fixtures_dir) if fixtures_dir else PROJECT_ROOT / "fixtures"
        users_dir = self.fixtures_dir / "users"
        self.profiles = ProfileStore(directory=users_dir if users_dir.is_dir() else None)
        self.registry = SenderGroupRegistry()
        self.history = InteractionHistory()
        self.api_key = api_key or GEMINI_API_KEY
        self.model = model
        self._client: Any = None

    def _get_client(self) -> Any:
        """Retrieve or initialize the google-genai Client."""
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "GEMINI_API_KEY environment variable is not set.\n"
                    "Please set your key: export GEMINI_API_KEY='your-key-here'\n"
                    "Or run with `--dry-run` to test the demonstration without an API key."
                )
            try:
                from google import genai

                self._client = genai.Client(api_key=self.api_key)
            except ImportError as err:
                raise ImportError(
                    "The `google-genai` SDK is required for live evaluation.\n"
                    "Install with: pip install google-genai"
                ) from err
        return self._client

    def register_default_contexts(self) -> None:
        """Pre-register all sender and chat metadata contexts for demonstration fixtures."""
        # 1. Senders
        senders = [
            SenderContext(
                sender_id="sender_husband_amit",
                display_name="Amit",
                sender_type="person",
                is_in_contacts=True,
                trust_score=0.95,
                relationship="spouse",
            ),
            SenderContext(
                sender_id="sender_mother",
                display_name="Mummy",
                sender_type="person",
                is_in_contacts=True,
                trust_score=0.95,
                relationship="family",
            ),
            SenderContext(
                sender_id="sender_school_admin",
                display_name="Mrs. Kapoor (DPS Admin)",
                sender_type="person",
                is_in_contacts=True,
                trust_score=0.85,
                relationship="school_admin",
            ),
            SenderContext(
                sender_id="sender_society_admin",
                display_name="RWA Admin",
                sender_type="person",
                is_in_contacts=True,
                trust_score=0.70,
                relationship="community",
            ),
            SenderContext(
                sender_id="sender_unknown_9876",
                display_name="+91 98765 43210",
                sender_type="unknown",
                is_in_contacts=False,
                trust_score=0.10,
                relationship=None,
            ),
            SenderContext(
                sender_id="sender_uncle_raj",
                display_name="Raj Uncle",
                sender_type="person",
                is_in_contacts=True,
                trust_score=0.60,
                relationship="family",
            ),
            SenderContext(
                sender_id="sender_coworker_neha",
                display_name="Neha",
                sender_type="person",
                is_in_contacts=True,
                trust_score=0.75,
                relationship="coworker",
            ),
            SenderContext(
                sender_id="sender_reliance_digital",
                display_name="Reliance Digital",
                sender_type="business",
                is_in_contacts=False,
                trust_score=0.50,
                relationship=None,
            ),
            SenderContext(
                sender_id="sender_unknown_5432",
                display_name="+91 54321 09876",
                sender_type="unknown",
                is_in_contacts=False,
                trust_score=0.10,
                relationship=None,
            ),
            SenderContext(
                sender_id="sender_business_partner",
                display_name="Sanjay (Business Partner)",
                sender_type="person",
                is_in_contacts=True,
                trust_score=0.90,
                relationship="business_partner",
            ),
            SenderContext(
                sender_id="sender_client_mehra",
                display_name="Mr. Mehra (Client)",
                sender_type="person",
                is_in_contacts=True,
                trust_score=0.80,
                relationship="client",
            ),
            SenderContext(
                sender_id="sender_accountant",
                display_name="CA Sharma (Accountant)",
                sender_type="person",
                is_in_contacts=True,
                trust_score=0.85,
                relationship="accountant",
            ),
        ]
        for sender in senders:
            self.registry.register_sender(sender)

        # 2. Groups and DM Chats
        groups = [
            GroupContext(
                chat_id="chat_dm_amit",
                chat_name="Amit",
                chat_type="dm",
                member_count=None,
                category="family",
                user_engagement_rate=0.95,
                is_muted_by_user=False,
            ),
            GroupContext(
                chat_id="chat_greenpark_society",
                chat_name="Green Park Society",
                chat_type="group",
                member_count=120,
                category="society",
                user_engagement_rate=0.40,
                is_muted_by_user=False,
            ),
            GroupContext(
                chat_id="chat_dm_unknown",
                chat_name="+91 98765 43210",
                chat_type="dm",
                member_count=None,
                category=None,
                user_engagement_rate=0.0,
                is_muted_by_user=False,
            ),
            GroupContext(
                chat_id="chat_dps_parents",
                chat_name="DPS Parents Group",
                chat_type="group",
                member_count=45,
                category="school",
                user_engagement_rate=0.70,
                is_muted_by_user=False,
            ),
            GroupContext(
                chat_id="chat_sharma_family",
                chat_name="Sharma Family 🏠",
                chat_type="group",
                member_count=15,
                category="family",
                user_engagement_rate=0.50,
                is_muted_by_user=False,
            ),
            GroupContext(
                chat_id="chat_office_memes",
                chat_name="Office Memes & Fun",
                chat_type="group",
                member_count=30,
                category="work",
                user_engagement_rate=0.20,
                is_muted_by_user=True,
            ),
            GroupContext(
                chat_id="chat_dm_reliance",
                chat_name="Reliance Digital",
                chat_type="business",
                member_count=None,
                category="business",
                user_engagement_rate=0.10,
                is_muted_by_user=False,
            ),
            GroupContext(
                chat_id="chat_dm_unknown2",
                chat_name="+91 54321 09876",
                chat_type="dm",
                member_count=None,
                category=None,
                user_engagement_rate=0.0,
                is_muted_by_user=False,
            ),
            GroupContext(
                chat_id="chat_dm_mother",
                chat_name="Mummy",
                chat_type="dm",
                member_count=None,
                category="family",
                user_engagement_rate=0.85,
                is_muted_by_user=False,
            ),
            GroupContext(
                chat_id="chat_school_parents",
                chat_name="School Parents Group",
                chat_type="group",
                member_count=50,
                category="school",
                user_engagement_rate=0.30,
                is_muted_by_user=True,
            ),
        ]
        for group in groups:
            self.registry.register_group(group)

    def _get_mock_decision(self, message: IncomingMessage, user_id: str) -> RoutingDecision:
        """Generate high-fidelity deterministic mock routing decision for dry-run mode."""
        msg_id = message.message_id

        # Mock routing catalog tailored to Priya vs Rahul preferences
        mock_data: dict[str, dict[str, dict[str, Any]]] = {
            "msg_001": {
                "user_priya": {
                    "action": "notify",
                    "confidence": 0.98,
                    "category": "urgent_personal",
                    "reasoning": "Urgent family coordination request from spouse (priority contact) with a 4 PM deadline.",
                    "risk_flags": [],
                    "digest_priority": None,
                    "media_summary": None,
                },
                "user_rahul": {
                    "action": "notify",
                    "confidence": 0.92,
                    "category": "urgent_personal",
                    "reasoning": "Direct message with time-sensitive logistics request from trusted contact.",
                    "risk_flags": [],
                    "digest_priority": None,
                    "media_summary": None,
                },
            },
            "msg_002": {
                "user_priya": {
                    "action": "digest",
                    "confidence": 0.90,
                    "category": "community_announcement",
                    "reasoning": "Society maintenance notice matching user's interests; batched with high priority due to Sept 5 deadline.",
                    "risk_flags": [],
                    "digest_priority": "high",
                    "media_summary": "Green Park RWA Maintenance Notice: ₹5,000 due Sept 5 via UPI/Portal",
                },
                "user_rahul": {
                    "action": "digest",
                    "confidence": 0.82,
                    "category": "community_announcement",
                    "reasoning": "General society maintenance circular batched into digest; not in user's priority interests.",
                    "risk_flags": [],
                    "digest_priority": "low",
                    "media_summary": "Green Park RWA Maintenance Notice: ₹5,000 due Sept 5 via UPI/Portal",
                },
            },
            "msg_003": {
                "user_priya": {
                    "action": "mute",
                    "confidence": 0.99,
                    "category": "scam",
                    "reasoning": "Blatant lottery scam with fake prize claim, suspicious link, and OTP phishing from unknown sender.",
                    "risk_flags": [
                        "scam_pattern",
                        "suspicious_link",
                        "phishing_domain",
                        "unsolicited_financial_request",
                        "high_forward_count",
                    ],
                    "digest_priority": None,
                    "media_summary": None,
                },
                "user_rahul": {
                    "action": "mute",
                    "confidence": 0.99,
                    "category": "scam",
                    "reasoning": "Detected lottery scam with malicious link and OTP request from untrusted number; suppressed immediately.",
                    "risk_flags": [
                        "scam_pattern",
                        "suspicious_link",
                        "phishing_domain",
                        "unsolicited_financial_request",
                        "high_forward_count",
                    ],
                    "digest_priority": None,
                    "media_summary": None,
                },
            },
            "msg_004": {
                "user_priya": {
                    "action": "notify",
                    "confidence": 0.96,
                    "category": "school_update",
                    "reasoning": "Urgent school closure voice note from priority contact (school admin) matching user's school interests.",
                    "risk_flags": [],
                    "digest_priority": None,
                    "media_summary": "Audio announcement from school admin notifying parents of emergency school closure",
                },
                "user_rahul": {
                    "action": "digest",
                    "confidence": 0.84,
                    "category": "school_update",
                    "reasoning": "School closure announcement voice note routed to digest as school is not a priority contact for user.",
                    "risk_flags": [],
                    "digest_priority": "medium",
                    "media_summary": "Audio announcement from school admin notifying parents of emergency school closure",
                },
            },
            "msg_005": {
                "user_priya": {
                    "action": "mute",
                    "confidence": 0.97,
                    "category": "good_morning_forward",
                    "reasoning": "Generic Good Morning graphic forward matching user's blocked categories list and forwarded 12 times.",
                    "risk_flags": ["high_forward_count", "generic_greeting"],
                    "digest_priority": None,
                    "media_summary": "Good Morning graphic with sunrise illustration and blessing text",
                },
                "user_rahul": {
                    "action": "mute",
                    "confidence": 0.95,
                    "category": "good_morning_forward",
                    "reasoning": "Chain forward morning greeting matching user's blocked categories.",
                    "risk_flags": ["high_forward_count", "generic_greeting"],
                    "digest_priority": None,
                    "media_summary": "Good Morning graphic with sunrise illustration and blessing text",
                },
            },
            "msg_006": {
                "user_priya": {
                    "action": "notify",
                    "confidence": 0.95,
                    "category": "work_urgent",
                    "reasoning": "Direct @mention with urgent Q3 budget approval request overrides muted chat setting.",
                    "risk_flags": [],
                    "digest_priority": None,
                    "media_summary": None,
                },
                "user_rahul": {
                    "action": "mute",
                    "confidence": 0.88,
                    "category": "work_discussion",
                    "reasoning": "Chat message in muted group mentioning another user (@Priya) with no relevance to recipient.",
                    "risk_flags": [],
                    "digest_priority": None,
                    "media_summary": None,
                },
            },
            "msg_007": {
                "user_priya": {
                    "action": "mute",
                    "confidence": 0.94,
                    "category": "promotion",
                    "reasoning": "Commercial sale flyer matching user's blocked promotions category.",
                    "risk_flags": ["promotional_broadcast"],
                    "digest_priority": None,
                    "media_summary": "Reliance Digital Mega Sale flyer: Up to 60% off on laptops, phones & TVs this weekend",
                },
                "user_rahul": {
                    "action": "digest",
                    "confidence": 0.91,
                    "category": "promotion",
                    "reasoning": "Electronics mega sale poster matching user's stated interest in electronics deals.",
                    "risk_flags": [],
                    "digest_priority": "medium",
                    "media_summary": "Reliance Digital Mega Sale flyer: Up to 60% off on laptops, phones & TVs this weekend",
                },
            },
            "msg_008": {
                "user_priya": {
                    "action": "mute",
                    "confidence": 0.99,
                    "category": "phishing",
                    "reasoning": "Fake bank/EMI overdue notice with fraudulent verification domain from unknown sender.",
                    "risk_flags": ["phishing_domain", "fake_urgency", "banking_fraud", "unknown_sender"],
                    "digest_priority": None,
                    "media_summary": None,
                },
                "user_rahul": {
                    "action": "mute",
                    "confidence": 0.99,
                    "category": "phishing",
                    "reasoning": "Phishing attempt using fake overdue EMI threat and credential harvesting link from unknown number.",
                    "risk_flags": ["phishing_domain", "fake_urgency", "banking_fraud", "unknown_sender"],
                    "digest_priority": None,
                    "media_summary": None,
                },
            },
            "msg_009": {
                "user_priya": {
                    "action": "notify",
                    "confidence": 0.96,
                    "category": "family_personal",
                    "reasoning": "Direct personal voice note from mother (priority contact) in 1:1 family chat.",
                    "risk_flags": [],
                    "digest_priority": None,
                    "media_summary": "Voice note from Mummy discussing weekend family visit plans",
                },
                "user_rahul": {
                    "action": "notify",
                    "confidence": 0.92,
                    "category": "family_personal",
                    "reasoning": "1:1 direct voice note from close family member with high trust score.",
                    "risk_flags": [],
                    "digest_priority": None,
                    "media_summary": "Voice note from Mummy discussing weekend family visit plans",
                },
            },
            "msg_010": {
                "user_priya": {
                    "action": "digest",
                    "confidence": 0.92,
                    "category": "school_fees_reminder",
                    "reasoning": "School fee deadline reminder matching user's school fees interest; scheduled in digest with high priority.",
                    "risk_flags": [],
                    "digest_priority": "high",
                    "media_summary": None,
                },
                "user_rahul": {
                    "action": "mute",
                    "confidence": 0.86,
                    "category": "school_fees_reminder",
                    "reasoning": "School fee reminder in non-priority group with no matching user interest.",
                    "risk_flags": [],
                    "digest_priority": None,
                    "media_summary": None,
                },
            },
        }

        user_mock = mock_data.get(msg_id, {}).get(user_id)
        if user_mock:
            return RoutingDecision.model_validate(user_mock)

        # Fallback default
        return RoutingDecision(
            action="digest",
            confidence=0.75,
            category="general",
            reasoning="Processed via default balanced heuristic.",
            risk_flags=[],
            digest_priority="medium",
            media_summary=None,
        )

    async def route(
        self,
        message: IncomingMessage,
        user_id: str,
        dry_run: bool = False,
    ) -> RoutingDecision:
        """Route a single incoming message for the given user profile."""
        user = self.profiles.get(user_id)
        sender = self.registry.get_sender(message.sender_id, default_name=message.sender_name)
        group = self.registry.get_group(message.chat_id, default_name=message.chat_name)
        recent_history = self.history.get_recent(user_id, limit=HISTORY_CONTEXT_WINDOW)

        # Handle Dry-Run Mode
        if dry_run:
            decision = self._get_mock_decision(message, user_id)
            self.history.record(user_id, message, decision)
            self.registry.increment_message_count(message.sender_id)
            if decision.action == "mute" and decision.category in ("scam", "phishing"):
                self.registry.report_spam(message.sender_id)
            return decision

        # Live Gemini Evaluation
        msg_eval = message.model_copy()
        if msg_eval.media_path and not Path(msg_eval.media_path).is_absolute():
            msg_eval.media_path = str(PROJECT_ROOT / msg_eval.media_path)

        parts = compose_input(
            message=msg_eval,
            user=user,
            sender=sender,
            group=group,
            recent_history=recent_history,
        )

        client = self._get_client()

        try:
            # Interactions API call with structured output schema
            response = await asyncio.to_thread(
                client.interactions.create,
                model=self.model,
                input=parts,
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": RoutingDecision.model_json_schema(),
                },
            )

            raw_text = ""
            if hasattr(response, "outputs") and response.outputs:
                raw_text = response.outputs[-1].text
            elif hasattr(response, "text"):
                raw_text = response.text
            elif hasattr(response, "output"):
                raw_text = str(response.output)
            else:
                raw_text = str(response)

            data = json.loads(raw_text)
            decision = RoutingDecision.model_validate(data)

        except Exception as e:
            # Log error and fallback gracefully
            logging.error("Gemini API call failed for message %s: %s", message.message_id, e)
            decision = RoutingDecision(
                action="digest",
                confidence=0.40,
                category="evaluation_fallback",
                reasoning=f"Automated fallback to digest due to evaluation error: {e}",
                risk_flags=["api_evaluation_error"],
                digest_priority="medium",
                media_summary=None,
            )

        # Safety Fallback: if confidence is below minimum threshold, fall back to digest
        if decision.confidence < MIN_CONFIDENCE_THRESHOLD and decision.action != "digest":
            decision = RoutingDecision(
                action="digest",
                confidence=decision.confidence,
                category=decision.category,
                reasoning=f"Low confidence ({decision.confidence:.2f}) fallback to digest: {decision.reasoning}",
                risk_flags=decision.risk_flags + ["low_confidence_fallback"],
                digest_priority=decision.digest_priority or "medium",
                media_summary=decision.media_summary,
            )

        # Record interaction in history ring-buffer
        self.history.record(user_id, message, decision)
        self.registry.increment_message_count(message.sender_id)
        if decision.action == "mute" and decision.category in ("scam", "phishing"):
            self.registry.report_spam(message.sender_id)

        return decision


# ---------------------------------------------------------------------------
# CLI Display Formatters
# ---------------------------------------------------------------------------
def print_banner() -> None:
    """Print project ASCII banner."""
    print()
    print(f"{BOLD}{CYAN}╔════════════════════════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{CYAN}║             📱 WhatsApp AI Notification Router — Live Demo CLI                ║{RESET}")
    print(f"{BOLD}{CYAN}║             Powered by Gemini (gemini-3.7-flash) Multimodal API                ║{RESET}")
    print(f"{BOLD}{CYAN}╚════════════════════════════════════════════════════════════════════════════════╝{RESET}")
    print()


def print_user_header(user: UserProfile) -> None:
    """Print styled header for current user profile."""
    print(f"{BOLD}{BG_BLUE}{WHITE}  👤 USER PROFILE: {user.name} ({user.user_id})  {RESET}")
    priority = ", ".join(user.priority_contacts) if user.priority_contacts else "None"
    muted = ", ".join(user.muted_chats) if user.muted_chats else "None"
    interests = ", ".join(user.interests) if user.interests else "None"
    blocked = ", ".join(user.blocked_categories) if user.blocked_categories else "None"

    print(f"  {CYAN}Sensitivity:{RESET} {BOLD}{user.sensitivity}{RESET}  │  {CYAN}Work Hours:{RESET} {user.work_hours or 'N/A'}")
    print(f"  {CYAN}Priority Contacts:{RESET} {priority}")
    print(f"  {CYAN}Muted Chats:{RESET}       {muted}")
    print(f"  {CYAN}Stated Interests:{RESET}  {interests}")
    print(f"  {CYAN}Blocked Categories:{RESET}{blocked}")
    print(f"{DIM}{'─' * 82}{RESET}")


def print_message_card(
    idx: int,
    message: IncomingMessage,
    decision: RoutingDecision,
) -> None:
    """Print formatted message card with routing decision details."""
    badge = format_action_badge(decision.action)
    conf_bar = format_confidence_bar(decision.confidence)

    # Content snippet formatting
    raw_text = message.text or f"<{message.content_type.upper()} CONTENT>"
    snippet = raw_text[:50] + ("..." if len(raw_text) > 50 else "")

    type_icon = {
        "text": "💬",
        "image": "🖼️",
        "image_with_caption": "📸",
        "voice_note": "🎙️",
    }.get(message.content_type, "📄")

    print(f"┌─ {BOLD}[#{idx:02d}] {message.message_id}{RESET} │ {type_icon} {CYAN}{message.sender_name}{RESET} in {MAGENTA}{message.chat_name}{RESET} ({message.chat_type})")
    print(f"│  {DIM}Snippet:{RESET}    \"{snippet}\"")
    if message.is_forwarded:
        fwd_badge = f"{YELLOW}[Forwarded" + (f" ×{message.forward_count}" if message.forward_count else "") + f"]{RESET}"
        print(f"│  {DIM}Flags:{RESET}      {fwd_badge}")
    if message.mentions:
        print(f"│  {DIM}Mentions:{RESET}   {BOLD}{CYAN}@{', @'.join(message.mentions)}{RESET}")

    # Routing Outcome
    print(f"│  {BOLD}Decision:{RESET}   {badge}  │  Category: {BOLD}{decision.category}{RESET}")
    print(f"│  {DIM}Confidence:{RESET} {conf_bar}")
    if decision.digest_priority:
        print(f"│  {DIM}Digest Pri:{RESET} {YELLOW}{decision.digest_priority.upper()}{RESET}")
    if decision.risk_flags:
        flags_str = ", ".join(f"{RED}{f}{RESET}" for f in decision.risk_flags)
        print(f"│  {DIM}Risk Flags:{RESET} {flags_str}")
    if decision.media_summary:
        print(f"│  {DIM}Media OCR/Audio Summary:{RESET} {ITALIC}{decision.media_summary}{RESET}")
    print(f"│  {DIM}Reasoning:{RESET}  {decision.reasoning}")
    print(f"└{'─' * 80}\n")


def print_summary_box(user_name: str, counts: dict[str, int]) -> None:
    """Print aggregated summary statistics box."""
    notify = counts.get("notify", 0)
    digest = counts.get("digest", 0)
    mute = counts.get("mute", 0)
    total = notify + digest + mute

    p_notify = (notify / total * 100) if total > 0 else 0
    p_digest = (digest / total * 100) if total > 0 else 0
    p_mute = (mute / total * 100) if total > 0 else 0

    print(f"╔════════════════════════════════════════════════════════════════════════════════╗")
    print(f"║ 📊 {BOLD}ROUTING SUMMARY FOR {user_name:<47}{RESET} ║")
    print(f"╠════════════════════════════════════════════════════════════════════════════════╣")
    print(f"║  🔴 {BOLD}{RED}NOTIFY:{RESET} {notify:>2d} messages ({p_notify:>5.1f}%) — Immediate interruptions                     ║")
    print(f"║  🟡 {BOLD}{YELLOW}DIGEST:{RESET} {digest:>2d} messages ({p_digest:>5.1f}%) — Batched into summary updates             ║")
    print(f"║  ⚫ {BOLD}{GRAY}MUTE:  {RESET} {mute:>2d} messages ({p_mute:>5.1f}%) — Suppressed spam, chatter & ads        ║")
    print(f"║  Total Processed: {total:>2d} messages                                                 ║")
    print(f"╚════════════════════════════════════════════════════════════════════════════════╝\n")


def print_comparison_table(
    messages: list[IncomingMessage],
    results_priya: list[RoutingDecision],
    results_rahul: list[RoutingDecision],
) -> None:
    """Print comparative matrix showing personalization differences between users."""
    print(f"{BOLD}{CYAN}═" * 82 + f"{RESET}")
    print(f"{BOLD}{WHITE} 🔍 PERSONA COMPARISON MATRIX: Priya vs Rahul{RESET}")
    print(f"{DIM} Demonstrates how identical messages route differently based on user context{RESET}")
    print(f"{BOLD}{CYAN}═" * 82 + f"{RESET}")
    print(f"{BOLD}{'Msg ID':<9} {'Sender & Type':<26} {'Priya Action':<16} {'Rahul Action':<16} {'Difference Rationale':<22}{RESET}")
    print(f"{DIM}{'─' * 82}{RESET}")

    for msg, dec_p, dec_r in zip(messages, results_priya, results_rahul):
        sender_label = f"{msg.sender_name[:15]} ({msg.content_type[:5]})"
        badge_p = format_action_badge(dec_p.action)
        badge_r = format_action_badge(dec_r.action)

        diff = "Personalized" if dec_p.action != dec_r.action else "Matched Policy"
        diff_colored = f"{CYAN}{diff}{RESET}" if dec_p.action != dec_r.action else f"{DIM}{diff}{RESET}"

        print(f"{msg.message_id:<9} {sender_label:<26} {badge_p:<24} {badge_r:<24} {diff_colored}")

    print(f"{BOLD}{CYAN}═" * 82 + f"{RESET}\n")


# ---------------------------------------------------------------------------
# Main Execution Flow
# ---------------------------------------------------------------------------
async def run_demo(dry_run: bool = False) -> None:
    """Execute the interactive CLI demo."""
    print_banner()

    fixtures_dir = PROJECT_ROOT / "fixtures"
    messages_file = fixtures_dir / "messages" / "sample_messages.json"

    if not messages_file.exists():
        print(f"{RED}Error: Messages fixture not found at {messages_file}{RESET}")
        sys.exit(1)

    # 1. Initialize Router & Pre-register contexts
    router = NotificationRouter(fixtures_dir=fixtures_dir)
    router.register_default_contexts()

    # 2. Check API Key availability if not in dry-run
    if not dry_run and not os.environ.get("GEMINI_API_KEY"):
        print(f"{BOLD}{YELLOW}⚠️  WARNING: GEMINI_API_KEY environment variable is not set.{RESET}")
        print("To run with live Gemini 3.7 Flash API:")
        print("  export GEMINI_API_KEY='your-api-key'")
        print("  python scripts/demo.py")
        print()
        print(f"{CYAN}Switching automatically to --dry-run mode for mock evaluation display...{RESET}\n")
        dry_run = True

    mode_label = f"{YELLOW}[DRY-RUN MODE (Mock Decisions)]{RESET}" if dry_run else f"{GREEN}[LIVE GEMINI 3.7 FLASH API]{RESET}"
    print(f"Execution Mode: {mode_label}\n")

    # 3. Load Sample Messages
    with open(messages_file, encoding="utf-8") as f:
        raw_msgs = json.load(f)
    messages = [IncomingMessage.model_validate(m) for m in raw_msgs]

    users = ["user_priya", "user_rahul"]
    all_results: dict[str, list[RoutingDecision]] = {}

    for user_id in users:
        user_profile = router.profiles.get(user_id)
        print_user_header(user_profile)

        counts = {"notify": 0, "digest": 0, "mute": 0}
        user_decisions: list[RoutingDecision] = []

        for idx, msg in enumerate(messages, 1):
            decision = await router.route(msg, user_id=user_id, dry_run=dry_run)
            user_decisions.append(decision)
            counts[decision.action] = counts.get(decision.action, 0) + 1
            print_message_card(idx, msg, decision)

        all_results[user_id] = user_decisions
        print_summary_box(user_profile.name, counts)

    # 4. Print Comparison Matrix
    if "user_priya" in all_results and "user_rahul" in all_results:
        print_comparison_table(messages, all_results["user_priya"], all_results["user_rahul"])

    print(f"{BOLD}{GREEN}✅ Demo execution complete!{RESET}\n")


def main() -> None:
    """Parse CLI arguments and launch demo."""
    parser = argparse.ArgumentParser(
        description="WhatsApp AI Notification Router — Interactive CLI Demo",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run demo using simulated mock decisions without calling Gemini API",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run_demo(dry_run=args.dry_run))
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Demo interrupted by user.{RESET}")
    except Exception as err:
        print(f"\n{RED}Execution failed: {err}{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
