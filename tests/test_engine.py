"""Unit tests for router.engine module."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from router.config import MIN_CONFIDENCE_THRESHOLD
from router.engine import NotificationRouter
from router.models import IncomingMessage, RoutingDecision, UserProfile

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def mock_genai_client() -> MagicMock:
    """Create a mock genai.Client."""
    client = MagicMock()
    return client


@pytest.fixture
def sample_user() -> UserProfile:
    """Sample user profile for testing."""
    return UserProfile(
        user_id="user_priya",
        name="Priya Sharma",
        priority_contacts=["sender_husband_amit", "sender_mother"],
        muted_chats=["chat_office_memes", "chat_colony_general"],
        interests=["school fees", "society maintenance"],
        blocked_categories=["promotions", "chain_forwards"],
        work_hours={"start": "09:00", "end": "18:00"},
        sensitivity="balanced",
    )


class TestNotificationRouterInit:
    """Tests for NotificationRouter initialization."""

    def test_init_without_fixtures(self, mock_genai_client: MagicMock) -> None:
        """Test initialization with client and empty stores."""
        router = NotificationRouter(client=mock_genai_client)
        assert router.client == mock_genai_client


class TestHardRules:
    """Tests for NotificationRouter._check_hard_rules."""

    def test_priority_contact_text_message(
        self,
        mock_genai_client: MagicMock,
        sample_user: UserProfile,
    ) -> None:
        """Test rule 1: Text message from priority contact triggers immediate notify."""
        router = NotificationRouter(client=mock_genai_client)
        msg = IncomingMessage(
            message_id="msg_01",
            timestamp=datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc),
            sender_id="sender_husband_amit",
            sender_name="Amit",
            chat_id="chat_dm_amit",
            chat_name="Amit",
            chat_type="dm",
            content_type="text",
            text="Please pick up milk",
            media_path=None,
            is_forwarded=False,
        )
        decision = router._check_hard_rules(msg, sample_user)
        assert decision is not None
        assert decision.action == "notify"
        assert decision.confidence == 1.0
        assert decision.category == "priority_contact"

    def test_priority_contact_media_message_not_skipped(
        self,
        mock_genai_client: MagicMock,
        sample_user: UserProfile,
    ) -> None:
        """Test rule 1: Media message from priority contact does NOT skip LLM."""
        router = NotificationRouter(client=mock_genai_client)
        msg = IncomingMessage(
            message_id="msg_02",
            timestamp=datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc),
            sender_id="sender_mother",
            sender_name="Mummy",
            chat_id="chat_dm_mother",
            chat_name="Mummy",
            chat_type="dm",
            content_type="voice_note",
            text=None,
            media_path="fixtures/media/weekend_plans.ogg",
            is_forwarded=False,
        )
        decision = router._check_hard_rules(msg, sample_user)
        assert decision is None  # Should proceed to LLM

    def test_priority_contact_chain_forward_not_skipped(
        self,
        mock_genai_client: MagicMock,
        sample_user: UserProfile,
    ) -> None:
        """Test rule 1: Chain forward from priority contact does NOT match rule 1."""
        router = NotificationRouter(client=mock_genai_client)
        msg = IncomingMessage(
            message_id="msg_03",
            timestamp=datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc),
            sender_id="sender_husband_amit",
            sender_name="Amit",
            chat_id="chat_dm_amit",
            chat_name="Amit",
            chat_type="dm",
            content_type="text",
            text="Forward this message to 10 friends!",
            media_path=None,
            is_forwarded=True,
            forward_count=10,
        )
        decision = router._check_hard_rules(msg, sample_user)
        # Should be caught by rule 7 (chain forward in blocked categories) -> mute
        assert decision is not None
        assert decision.action == "mute"
        assert decision.category == "chain_forward"

    @pytest.mark.parametrize(
        "scam_text",
        [
            "Congratulations! You have won a lottery!",
            "Click here to claim your reward now",
            "Please send your OTP to authenticate",
            "Please share your PIN immediately",
            "KYC update urgently required for your wallet",
            "Your bank account will be blocked today",
            "Verify your bank details immediately",
        ],
    )
    def test_scam_pattern_matching(
        self,
        mock_genai_client: MagicMock,
        sample_user: UserProfile,
        scam_text: str,
    ) -> None:
        """Test rule 2: Scam patterns trigger mute with risk flag."""
        router = NotificationRouter(client=mock_genai_client)
        msg = IncomingMessage(
            message_id="msg_scam",
            timestamp=datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc),
            sender_id="sender_unknown",
            sender_name="Unknown",
            chat_id="chat_dm",
            chat_name="Unknown",
            chat_type="dm",
            content_type="text",
            text=scam_text,
            media_path=None,
        )
        decision = router._check_hard_rules(msg, sample_user)
        assert decision is not None
        assert decision.action == "mute"
        assert decision.category == "scam"
        assert "scam_pattern" in decision.risk_flags

    @pytest.mark.parametrize(
        "phishing_url",
        [
            "Visit http://bit.ly/win to get cash",
            "Check http://tinyurl.com/prize right now",
            "Go to https://definitely-not-a-scam.com",
            "Get free-recharge at this portal",
            "Click claim-now for bonus",
            "Are you the lottery-winner?",
        ],
    )
    def test_phishing_domain_matching(
        self,
        mock_genai_client: MagicMock,
        sample_user: UserProfile,
        phishing_url: str,
    ) -> None:
        """Test rule 3: Phishing domains trigger mute with risk flag."""
        router = NotificationRouter(client=mock_genai_client)
        msg = IncomingMessage(
            message_id="msg_phishing",
            timestamp=datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc),
            sender_id="sender_unknown",
            sender_name="Unknown",
            chat_id="chat_dm",
            chat_name="Unknown",
            chat_type="dm",
            content_type="text",
            text=phishing_url,
            media_path=None,
        )
        decision = router._check_hard_rules(msg, sample_user)
        assert decision is not None
        assert decision.action == "mute"
        assert decision.category == "phishing"
        assert "phishing_domain" in decision.risk_flags

    @pytest.mark.parametrize(
        "emergency_text",
        [
            "Please come to the hospital now",
            "There has been a severe accident on the highway",
            "This is a medical emergency",
            "Call an ambulance immediately",
            "Help me please I am trapped",
            "Building caught fire, evacuate",
            "Police are arriving at the scene",
            "Earthquake tremors felt nearby",
            "Heavy flood in the basement area",
            "The balcony structure collapsed",
        ],
    )
    def test_emergency_keyword_matching(
        self,
        mock_genai_client: MagicMock,
        sample_user: UserProfile,
        emergency_text: str,
    ) -> None:
        """Test rule 4: Emergency keywords trigger immediate notify."""
        router = NotificationRouter(client=mock_genai_client)
        msg = IncomingMessage(
            message_id="msg_emergency",
            timestamp=datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc),
            sender_id="sender_neighbor",
            sender_name="Neighbor",
            chat_id="chat_building",
            chat_name="Building Chat",
            chat_type="group",
            content_type="text",
            text=emergency_text,
            media_path=None,
        )
        decision = router._check_hard_rules(msg, sample_user)
        assert decision is not None
        assert decision.action == "notify"
        assert decision.category == "emergency"
        assert decision.confidence >= 0.95

    def test_muted_chat_without_mention(
        self,
        mock_genai_client: MagicMock,
        sample_user: UserProfile,
    ) -> None:
        """Test rule 6: Messages in muted chats without mention trigger mute."""
        router = NotificationRouter(client=mock_genai_client)
        msg = IncomingMessage(
            message_id="msg_muted",
            timestamp=datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc),
            sender_id="sender_colleague",
            sender_name="Colleague",
            chat_id="chat_office_memes",
            chat_name="Office Memes",
            chat_type="group",
            content_type="text",
            text="Look at this hilarious cat meme",
            media_path=None,
            mentions=[],
        )
        decision = router._check_hard_rules(msg, sample_user)
        assert decision is not None
        assert decision.action == "mute"
        assert decision.category == "muted_chat"

    def test_muted_chat_with_mention_not_muted(
        self,
        mock_genai_client: MagicMock,
        sample_user: UserProfile,
    ) -> None:
        """Test rule 5: Messages in muted chats WITH mention do NOT trigger mute."""
        router = NotificationRouter(client=mock_genai_client)
        msg = IncomingMessage(
            message_id="msg_mention",
            timestamp=datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc),
            sender_id="sender_colleague",
            sender_name="Colleague",
            chat_id="chat_office_memes",
            chat_name="Office Memes",
            chat_type="group",
            content_type="text",
            text="@Priya can you review this document?",
            media_path=None,
            mentions=["user_priya"],
        )
        decision = router._check_hard_rules(msg, sample_user)
        assert decision is None  # Should proceed to LLM

    def test_chain_forward_blocked_category(
        self,
        mock_genai_client: MagicMock,
        sample_user: UserProfile,
    ) -> None:
        """Test rule 7: Chain forwards in blocked categories are muted."""
        router = NotificationRouter(client=mock_genai_client)
        msg = IncomingMessage(
            message_id="msg_chain",
            timestamp=datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc),
            sender_id="sender_acquaintance",
            sender_name="Acquaintance",
            chat_id="chat_random",
            chat_name="Random Chat",
            chat_type="dm",
            content_type="text",
            text="Forward this to all your contacts for good luck",
            media_path=None,
            is_forwarded=True,
            forward_count=7,
        )
        decision = router._check_hard_rules(msg, sample_user)
        assert decision is not None
        assert decision.action == "mute"
        assert decision.category == "chain_forward"
        assert "high_forward_count" in decision.risk_flags

    def test_none_text_handled_gracefully(
        self,
        mock_genai_client: MagicMock,
        sample_user: UserProfile,
    ) -> None:
        """Test that None text does not raise exceptions."""
        router = NotificationRouter(client=mock_genai_client)
        msg = IncomingMessage(
            message_id="msg_none_text",
            timestamp=datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc),
            sender_id="sender_random",
            sender_name="Random",
            chat_id="chat_active_group",
            chat_name="Active Group",
            chat_type="group",
            content_type="image",
            text=None,
            media_path="fixtures/media/sale_poster.png",
            is_forwarded=False,
        )
        decision = router._check_hard_rules(msg, sample_user)
        assert decision is None


class TestSafetyOverrides:
    """Tests for NotificationRouter._apply_safety_overrides."""

    def test_override_notify_on_scam_message(self, mock_genai_client: MagicMock) -> None:
        """Test that an LLM notify decision on scam text is overridden to mute."""
        router = NotificationRouter(client=mock_genai_client)
        msg = IncomingMessage(
            message_id="msg_scam_override",
            timestamp=datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc),
            sender_id="sender_test",
            sender_name="Tester",
            chat_id="chat_test",
            chat_name="Test Chat",
            chat_type="dm",
            content_type="text",
            text="You have won a free iPhone! Click here to claim.",
        )
        flawed_decision = RoutingDecision(
            action="notify",
            confidence=0.8,
            reasoning="Important winning announcement",
            category="promotion",
            risk_flags=[],
        )
        safe_decision = router._apply_safety_overrides(flawed_decision, msg)
        assert safe_decision.action == "mute"
        assert safe_decision.category == "scam"
        assert "scam_pattern" in safe_decision.risk_flags

    def test_low_confidence_fallback_to_digest(self, mock_genai_client: MagicMock) -> None:
        """Test that confidence < MIN_CONFIDENCE_THRESHOLD falls back to digest."""
        router = NotificationRouter(client=mock_genai_client)
        msg = IncomingMessage(
            message_id="msg_low_conf",
            timestamp=datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc),
            sender_id="sender_test",
            sender_name="Tester",
            chat_id="chat_test",
            chat_name="Test Chat",
            chat_type="dm",
            content_type="text",
            text="Normal discussion about hobbies",
        )
        low_conf_decision = RoutingDecision(
            action="notify",
            confidence=0.3,
            reasoning="Uncertain about urgency",
            category="general",
            risk_flags=[],
        )
        final_decision = router._apply_safety_overrides(low_conf_decision, msg)
        assert final_decision.action == "digest"
        assert final_decision.digest_priority is not None


class TestRoutePipeline:
    """Tests for route and route_batch asynchronous execution."""

    @pytest.mark.anyio
    async def test_route_hard_rule_fast_path(
        self,
        mock_genai_client: MagicMock,
        sample_user: UserProfile,
        db_session
    ) -> None:
        """Test that hard rule matches bypass Gemini API call."""
        router = NotificationRouter(client=mock_genai_client)
        await router.profiles.upsert(db_session, sample_user)

        msg = IncomingMessage(
            message_id="msg_priority",
            timestamp=datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc),
            sender_id="sender_husband_amit",
            sender_name="Amit",
            chat_id="chat_dm_amit",
            chat_name="Amit",
            chat_type="dm",
            content_type="text",
            text="Running late, see you at 6",
            media_path=None,
        )

        decision = await router.route(db_session, msg, sample_user.user_id)
        assert decision.action == "notify"
        # Verify generate_content was NOT called
        mock_genai_client.models.generate_content.assert_not_called()
        # Verify history recorded
        history = await router.history.get_recent(db_session, sample_user.user_id)
        assert len(history) == 1
        assert history[0]["message_id"] == "msg_priority"

    @pytest.mark.anyio
    async def test_route_llm_invocation_success(
        self,
        mock_genai_client: MagicMock,
        sample_user: UserProfile,
        db_session
    ) -> None:

        llm_response = MagicMock()
        llm_response.text = (
            '{"action": "digest", "confidence": 0.85, "reasoning": "Society circular with upcoming deadline", '
            '"category": "society_update", "risk_flags": [], "digest_priority": "high", "media_summary": "Maintenance notice"}'
        )
        mock_genai_client.models.generate_content.return_value = llm_response

        router = NotificationRouter(client=mock_genai_client)
        await router.profiles.upsert(db_session, sample_user)

        msg = IncomingMessage(
            message_id="msg_llm_01",
            timestamp=datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc),
            sender_id="sender_society_admin",
            sender_name="RWA Admin",
            chat_id="chat_greenpark_society",
            chat_name="Green Park Society",
            chat_type="group",
            content_type="image_with_caption",
            text="Maintenance charges due Sept 5",
            media_path="fixtures/media/maintenance_notice.png",
        )

        decision = await router.route(db_session, msg, sample_user.user_id)
        assert decision.action == "digest"
        assert decision.category == "society_update"
        assert decision.digest_priority == "high"
        assert decision.confidence == 0.85
        mock_genai_client.models.generate_content.assert_called_once()

    @pytest.mark.anyio
    async def test_route_llm_failure_fallback(
        self,
        mock_genai_client: MagicMock,
        sample_user: UserProfile,
        db_session
    ) -> None:

        mock_genai_client.models.generate_content.side_effect = RuntimeError("API Rate Limit Exceeded")

        router = NotificationRouter(client=mock_genai_client)
        await router.profiles.upsert(db_session, sample_user)

        msg = IncomingMessage(
            message_id="msg_llm_fail",
            timestamp=datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc),
            sender_id="sender_someone",
            sender_name="Someone",
            chat_id="chat_general",
            chat_name="General Chat",
            chat_type="group",
            content_type="text",
            text="Hey everyone, let's catch up sometime next week.",
        )

        decision = await router.route(db_session, msg, sample_user.user_id)
        assert decision.action == "digest"
        assert decision.confidence == 0.1
        assert "API call failed" in decision.reasoning

    @pytest.mark.anyio
    async def test_route_batch(
        self,
        mock_genai_client: MagicMock,
        sample_user: UserProfile,
        db_session
    ) -> None:

        router = NotificationRouter(client=mock_genai_client)
        await router.profiles.upsert(db_session, sample_user)

        messages = [
            IncomingMessage(
                message_id="msg_b1",
                timestamp=datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc),
                sender_id="sender_husband_amit",
                sender_name="Amit",
                chat_id="chat_dm_amit",
                chat_name="Amit",
                chat_type="dm",
                content_type="text",
                text="Don't forget the keys",
            ),
            IncomingMessage(
                message_id="msg_b2",
                timestamp=datetime(2026, 8, 28, 12, 1, 0, tzinfo=timezone.utc),
                sender_id="sender_scam",
                sender_name="Scammer",
                chat_id="chat_scam",
                chat_name="Scammer",
                chat_type="dm",
                content_type="text",
                text="You have won 100,000 cash!",
            ),
        ]

        decisions = await router.route_batch(db_session, messages, sample_user.user_id)
        assert len(decisions) == 2
        assert decisions[0].action == "notify"
        assert decisions[1].action == "mute"
