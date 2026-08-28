"""Configuration constants for the notification router."""

import os

# ---------------------------------------------------------------------------
# Gemini API
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

# Meta Webhook & API settings
META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "default_insecure_token")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
META_PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID", "")

# ---------------------------------------------------------------------------
# Routing thresholds
# ---------------------------------------------------------------------------
# Minimum confidence below which the engine falls back to "digest"
MIN_CONFIDENCE_THRESHOLD: float = 0.4

# Trust score assigned to unknown senders (0.0–1.0)
DEFAULT_TRUST_SCORE: float = 0.3

# Maximum number of history entries to keep per user
HISTORY_RING_SIZE: int = 200

# Number of recent decisions to inject into the prompt context
HISTORY_CONTEXT_WINDOW: int = 10

# ---------------------------------------------------------------------------
# Safety overrides — always-mute patterns (post-LLM guard)
# ---------------------------------------------------------------------------
PHISHING_DOMAIN_KEYWORDS: list[str] = [
    "bit.ly/win",
    "tinyurl.com/prize",
    "definitely-not-a-scam",
    "free-recharge",
    "claim-now",
    "lottery-winner",
]

SCAM_TEXT_PATTERNS: list[str] = [
    "you have won",
    "click here to claim",
    "send your otp",
    "share your pin",
    "kyc update urgently",
    "account will be blocked",
    "verify your bank",
]

# ---------------------------------------------------------------------------
# Emergency keywords — force notify regardless of other signals
# ---------------------------------------------------------------------------
EMERGENCY_KEYWORDS: list[str] = [
    "hospital",
    "accident",
    "emergency",
    "ambulance",
    "help me",
    "fire",
    "police",
    "earthquake",
    "flood",
    "collapsed",
]

# ---------------------------------------------------------------------------
# Media constraints
# ---------------------------------------------------------------------------
MAX_IMAGE_SIZE_BYTES: int = 15 * 1024 * 1024  # 15 MB
MAX_AUDIO_SIZE_BYTES: int = 20 * 1024 * 1024  # 20 MB
SUPPORTED_IMAGE_MIMES: set[str] = {"image/jpeg", "image/png", "image/webp", "image/gif"}
SUPPORTED_AUDIO_MIMES: set[str] = {"audio/ogg", "audio/mpeg", "audio/wav", "audio/mp4"}
