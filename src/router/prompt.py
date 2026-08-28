"""Prompt construction and composition for the Gemini routing engine.

Assembles system routing policies, contextual metadata blocks (user profile,
sender trust, group settings, historical decisions), and multimodal content parts
(text, images, voice notes) for structured evaluation.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from router.config import HISTORY_CONTEXT_WINDOW
from router.media import build_audio_content_part, build_image_content_part
from router.models import GroupContext, IncomingMessage, RoutingDecision, SenderContext, UserProfile

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an intelligent WhatsApp notification router. Your role is to analyze incoming WhatsApp messages (including text, images, and voice notes) along with user preferences, sender trust metadata, chat/group context, and recent routing history to determine how the user should be notified.

### ACTIONS
You must choose exactly one of three routing actions:
1. `notify`: Immediately alert and interrupt the user. Use this for urgent personal messages, real-time family or work coordination, direct questions/mentions from trusted individuals, active delivery arrivals, and emergencies.
2. `digest`: Batch the message into the user's periodic summary without interrupting immediately. Use this for relevant newsletters, community/school circulars, transaction receipts, interest-matched promotions from opted-in businesses, and non-urgent informational discussions.
3. `mute`: Completely suppress notifications for this message. Use this for unsolicited spam, scams, phishing, chain forwards, viral spam, irrelevant broadcast chatter in muted or low-engagement groups, and cold outreach.

---

### CORE SAFETY-FIRST RULES (ABSOLUTE PRECEDENCE)
- MUTE ALL SCAMS, PHISHING, AND MALWARE: If a message contains fraudulent investment pitches, lottery/prize claims ("you have won", "click here to claim"), fake bank/KYC verifications, OTP/PIN requests, suspicious shortened links (e.g., bit.ly/win, tinyurl.com/prize), or unauthorized APK download links, you MUST classify it as `action: "mute"`, `category: "scam"` or `category: "phishing"`, assign `confidence: >= 0.95`, and include appropriate flags in `risk_flags` (e.g., ["scam_pattern", "suspicious_link", "phishing_domain", "unsolicited_financial_request"]).
- Safety overrides apply unconditionally to all senders, even if the sender is in contacts or marked with high trust (accounts can be compromised or hacked).

---

### PRIORITY ESCALATION RULES
1. Emergency Signals:
   - Keywords or clear context indicating life safety, accidents, medical emergencies, hospital visits, fires, police, disasters, or urgent cries for help ("help me", "accident", "hospital", "collapsed", "emergency") MUST trigger `action: "notify"`, `category: "emergency"` or `category: "urgent_personal"`, with `confidence: >= 0.95`.
2. Priority Contacts:
   - Messages from senders listed in `user.priority_contacts` or with close relationships (family, spouse, parent, boss) default to `action: "notify"`, unless the message is an obvious chain forward or mass promotional broadcast.
3. Direct Mentions:
   - If the receiving user is explicitly @-mentioned (`user_id` in `message.mentions`), escalate to `action: "notify"`, even if the group is muted by the user, unless the message is a mass bot/spam tag.
4. Direct Replies:
   - Direct replies to the user's previous messages (`reply_to_message_id` matches user's thread) should generally be routed to `notify` or high-priority `digest`.

---

### PERSONALIZATION & CONTEXT RUBRIC
1. User Interests:
   - Cross-reference message content and extracted media text with `user.interests` (e.g., "school fees", "cricket", "housing society", "tax", "flight deals").
   - Matches in relevant groups or from verified businesses -> `digest` (with `digest_priority: "high"` or `"medium"`) or `notify` (if time-sensitive / actionable deadline).
2. Blocked Categories:
   - If the message matches any category in `user.blocked_categories` (e.g., "promotions", "chain_forwards", "political_debates", "festive_greetings"), route to `action: "mute"`.
3. Sender Trust & Relationship:
   - High trust (>= 0.8) + In contacts: Lean towards `notify` for 1:1 chats, `digest` for informational group posts.
   - Low trust (< 0.4) / Unknown sender: Route unprompted outreach, cold marketing, and unknown links to `mute`.
   - Sender with spam reports (`spam_reports > 0`): Treat with heightened suspicion; lean towards `mute`.
4. Chat Context & Engagement:
   - Muted Chat (`is_muted_by_user: true`): Default to `action: "mute"` UNLESS user is directly mentioned or emergency keywords are present.
   - Low engagement (`user_engagement_rate < 0.3`): Bias towards `mute` or low-priority `digest`.
   - High engagement (`user_engagement_rate >= 0.7`): Relevant content should be `notify` or `digest`.
5. Work Hours & Time Sensitivity:
   - If `user.work_hours` is specified and the message is work-related:
     - Within work hours -> `notify` or `digest` (high priority).
     - Outside work hours -> `digest` (unless marked emergency or from priority contact).
6. Filtering Sensitivity:
   - `aggressive_filter`: Bias heavily toward `digest` and `mute`. Only critical emergencies, direct mentions, and priority contacts get `notify`.
   - `balanced`: Standard balanced behavior as described.
   - `miss_nothing`: Bias toward `notify` and `digest`. Only obvious spam and explicit noise get `mute`.

---

### DIGEST HEURISTICS & PRIORITIZATION
Assign `action: "digest"` for content that is valuable but does not require immediate interruption.
When `action` is "digest", you MUST specify `digest_priority`:
- `high`: Time-sensitive within 24h (e.g., payment due today/tomorrow, school circular with upcoming deadline, active parcel delivery arriving today).
- `medium`: Useful informational updates, weekly school updates, utility maintenance schedules, transaction receipts, interesting group discussions matching user interests.
- `low`: Casual community chatter matching interests, general newsletters, promotional discount codes from opted-in merchants.
(For `notify` and `mute`, set `digest_priority: null`.)

---

### MUTE HEURISTICS
Assign `action: "mute"` for:
- Frequently forwarded messages (`is_forwarded: true` with `forward_count >= 5`).
- Chain messages ("Send this to 10 groups to receive good luck").
- Generic "Good morning" / "Good night" image forwards without personal text.
- Unknown senders sharing unsolicited web links.
- Noisy chatter in muted groups without mentions.
- Senders with multiple spam reports.

---

### MULTIMODAL ANALYSIS INSTRUCTIONS
1. Images:
   - Read visual text via OCR (coupons, circulars, bills, announcements, dates, warnings).
   - Classify visual type: promotional flyer/poster, official school/society circular, payment receipt/screenshot, personal photo, meme, greeting card, document scan.
   - Summarize findings in `media_summary` (e.g., "Invoice receipt from Amazon for $42.50", "School notice: sports day rescheduled to Friday").
   - Route accordingly: official circular -> digest; receipt -> digest/notify; meme -> mute; promo flyer -> digest (if interest matches) or mute.
2. Voice Notes / Audio:
   - Transcribe and evaluate the spoken content, speaker tone, emotional distress, and urgency.
   - Summarize the audio in `media_summary` (e.g., "Urgent voice note from Mom asking to pick up medicine", "Casual 30s voice message discussing weekend lunch plans").
   - Route urgent voice notes from contacts to `notify`; casual voice messages to `digest` or `notify` depending on relationship.

---

### CONFIDENCE CALIBRATION
- `confidence >= 0.85`: High certainty (clear emergency, verified priority contact direct message, blatant scam/phishing, exact blocked category match, explicit direct mention).
- `0.50 <= confidence < 0.85`: Moderate certainty (mixed signals, contextual inference, new sender with neutral content, group circular matching interest).
- `confidence < 0.50`: Low certainty / high ambiguity (insufficient data, contradictory signals). Note that system will fall back to digest if confidence is too low.

### TWO-WAY REPLIES (ACTION = "reply")
If the incoming message is a direct question or request to the AI assistant from a known user, you can choose `action: "reply"`.
When you choose "reply", you MUST populate the `reply_text` field with a helpful, conversational response.
Examples of when to use `reply`:
- User asks "What were the messages about the school trip?"
- Customer texts "Where is my order?" and you have the context to answer.
- The user is conversing with you directly.
Do NOT use `reply` for group chatter, spam, or promotional forwards.

---

### OUTPUT FORMAT
Your output MUST be a valid JSON object matching the RoutingDecision schema:
{
  "action": "notify" | "digest" | "mute" | "reply",
  "confidence": <float between 0.0 and 1.0>,
  "reasoning": "<1-2 sentence clear explanation of the routing rationale>",
  "reply_text": "<if action is reply, what to say back> or null",
  "category": "<detected category, e.g. urgent_personal, school_update, scam, promotion, delivery, finance_receipt, family_chat, community_announcement, work, spam>",
  "risk_flags": ["<risk_tag1>", "<risk_tag2>"],
  "digest_priority": "high" | "medium" | "low" | null,
  "media_summary": "<brief summary of image/audio content or null>"
}
"""


def build_system_prompt() -> str:
    """Return the system prompt that encodes the routing policy.

    Returns:
        The comprehensive system prompt string.
    """
    return SYSTEM_PROMPT


def build_context_block(
    user: UserProfile,
    sender: SenderContext,
    group: GroupContext,
    recent_history: list[dict[str, Any]],
) -> str:
    """Build the per-request context block injected into the prompt.

    Args:
        user: The receiving user profile and notification preferences.
        sender: Metadata and trust score of the message sender.
        group: Metadata and engagement metrics of the chat/group.
        recent_history: List of recent routing decision dicts for context.

    Returns:
        Formatted multi-line text block describing user, sender, group, and history.
    """
    priority_contacts_str = ", ".join(user.priority_contacts) if user.priority_contacts else "None"
    muted_chats_str = ", ".join(user.muted_chats) if user.muted_chats else "None"
    interests_str = ", ".join(user.interests) if user.interests else "None"
    blocked_categories_str = (
        ", ".join(user.blocked_categories) if user.blocked_categories else "None"
    )
    work_hours_str = json.dumps(user.work_hours) if user.work_hours else "None"

    member_count_str = str(group.member_count) if group.member_count is not None else "N/A"
    group_category_str = group.category or "N/A"
    relationship_str = sender.relationship or "None"

    # Slice the most recent history entries up to HISTORY_CONTEXT_WINDOW
    history_window = recent_history[-HISTORY_CONTEXT_WINDOW:] if recent_history else []
    if history_window:
        history_lines: list[str] = []
        for idx, item in enumerate(history_window, 1):
            msg_id = item.get("message_id", "N/A")
            s_id = item.get("sender_id", "unknown")
            action = item.get("action", "unknown")
            cat = item.get("category", "unknown")
            text_snippet = item.get("text") or item.get("text_snippet") or ""
            if len(text_snippet) > 60:
                text_snippet = text_snippet[:57] + "..."
            history_lines.append(
                f"  {idx}. [Msg {msg_id}] Sender: {s_id} | Cat: {cat} | Action: {action} | Text: \"{text_snippet}\""
            )
        history_str = "\n".join(history_lines)
    else:
        history_str = "  No recent routing history."

    return f"""### USER PROFILE & PREFERENCES
- User ID: {user.user_id}
- Name: {user.name}
- Priority Contacts: {priority_contacts_str}
- Muted Chat IDs: {muted_chats_str}
- Stated Interests: {interests_str}
- Blocked Categories: {blocked_categories_str}
- Work Hours: {work_hours_str}
- Notification Sensitivity: {user.sensitivity}

### SENDER CONTEXT
- Sender ID: {sender.sender_id}
- Display Name: {sender.display_name}
- Sender Type: {sender.sender_type}
- In User Contacts: {'Yes' if sender.is_in_contacts else 'No'}
- Trust Score: {sender.trust_score:.2f} (scale 0.0 - 1.0)
- Relationship: {relationship_str}
- Messages in last 24h: {sender.recent_message_count_24h}
- Spam Reports: {sender.spam_reports}

### CHAT / GROUP CONTEXT
- Chat ID: {group.chat_id}
- Chat Name: {group.chat_name}
- Chat Type: {group.chat_type}
- Member Count: {member_count_str}
- Chat Category: {group_category_str}
- User Engagement Rate: {group.user_engagement_rate:.2f} (scale 0.0 - 1.0)
- Is Muted by User: {'Yes' if group.is_muted_by_user else 'No'}

### RECENT ROUTING HISTORY (last {len(history_window)} decisions)
{history_str}"""


def compose_input(
    message: IncomingMessage,
    user: UserProfile,
    sender: SenderContext,
    group: GroupContext,
    recent_history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compose the full multimodal input list for Gemini.

    Returns a list of content parts: text context + message body + optional
    image/audio parts. Missing or invalid media files are logged as warnings and
    handled gracefully without raising exceptions.

    Args:
        message: The incoming WhatsApp message to evaluate.
        user: The receiving user profile.
        sender: Sender context metadata.
        group: Group/chat context metadata.
        recent_history: Recent decision history list.

    Returns:
        List of content part dictionaries for Gemini API.
    """
    context_block = build_context_block(
        user=user,
        sender=sender,
        group=group,
        recent_history=recent_history,
    )

    forward_str = f"Yes (forward_count={message.forward_count})" if message.is_forwarded else "No"
    mentions_str = ", ".join(message.mentions) if message.mentions else "None"
    reply_str = message.reply_to_message_id or "None"
    text_content = message.text if message.text is not None else "<No text / caption provided>"

    message_block = f"""### INCOMING MESSAGE TO EVALUATE
- Message ID: {message.message_id}
- Timestamp: {message.timestamp.isoformat()}
- Chat: {message.chat_name} (ID: {message.chat_id}, Type: {message.chat_type})
- Sender: {message.sender_name} (ID: {message.sender_id})
- Content Type: {message.content_type}
- Is Forwarded: {forward_str}
- Mentions: {mentions_str}
- Replying to Message ID: {reply_str}
- Text / Caption: {text_content}"""

    instruction = (
        "Analyze this incoming WhatsApp message against the user preferences and context above. "
        "Return your routing decision as structured JSON matching RoutingDecision schema."
    )

    prompt_text = f"{context_block}\n\n{message_block}\n\n{instruction}"

    parts: list[dict[str, Any]] = [{"type": "text", "text": prompt_text}]

    # Handle image media (both standalone image and image with caption)
    if message.content_type in ("image", "image_with_caption") and message.media_path:
        try:
            image_part = build_image_content_part(message.media_path)
            parts.append(image_part)
        except Exception as err:
            logger.warning(
                "Failed to load image from '%s' for message '%s': %s",
                message.media_path,
                message.message_id,
                err,
            )

    # Handle voice note / audio media
    elif message.content_type == "voice_note" and message.media_path:
        try:
            audio_part = build_audio_content_part(message.media_path)
            parts.append(audio_part)
        except Exception as err:
            logger.warning(
                "Failed to load audio from '%s' for message '%s': %s",
                message.media_path,
                message.message_id,
                err,
            )

    return parts
