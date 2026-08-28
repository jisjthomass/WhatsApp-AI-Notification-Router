"""Script to generate media fixtures and validate dataset fixtures for the WhatsApp Notification Router."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Base project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = PROJECT_ROOT / "fixtures"
MEDIA_DIR = FIXTURES_DIR / "media"
USERS_DIR = FIXTURES_DIR / "users"
MESSAGES_DIR = FIXTURES_DIR / "messages"


def _get_font(size: int = 20, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Retrieve an available TrueType font or fallback to the PIL default font.

    Args:
        size: Desired font size in points.
        bold: Whether to prefer a bold font variant.

    Returns:
        Loaded ImageFont instance.
    """
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ]
    for path_str in candidates:
        candidate_path = Path(path_str)
        if candidate_path.exists():
            try:
                return ImageFont.truetype(str(candidate_path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def generate_maintenance_notice(output_path: Path) -> Path:
    """Generate sample society maintenance notice poster image.

    Image properties:
        Dimensions: 400x300
        Background: Light Blue (#4A90E2)
        Text: White 'MAINTENANCE NOTICE\\nDue: Sept 5\\nAmount: ₹5,000'

    Args:
        output_path: Destination path for the generated PNG image.

    Returns:
        The resolved output Path.
    """
    width, height = 400, 300
    # Light blue background
    img = Image.new("RGB", (width, height), color=(74, 144, 226))
    draw = ImageDraw.Draw(img)

    # Header border decorative box
    draw.rectangle([(20, 20), (380, 280)], outline=(255, 255, 255), width=3)
    draw.rectangle([(25, 25), (375, 75)], fill=(50, 115, 195))

    title_font = _get_font(size=18, bold=True)
    body_font = _get_font(size=16, bold=False)

    # Draw Title
    draw.text(
        (200, 50),
        "MAINTENANCE NOTICE",
        fill=(255, 255, 255),
        anchor="mm",
        font=title_font,
    )

    # Draw Body Content
    details_text = "Green Park RWA\n\nDue Date: Sept 5\nAmount: ₹5,000\n\nPlease pay via UPI / Portal"
    draw.multiline_text(
        (200, 175),
        details_text,
        fill=(255, 255, 255),
        anchor="mm",
        align="center",
        font=body_font,
        spacing=8,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG")
    logger.info("Generated maintenance notice image at %s", output_path)
    return output_path


def generate_good_morning(output_path: Path) -> Path:
    """Generate sample Good Morning family forward image with gradient background.

    Image properties:
        Dimensions: 400x300
        Background: Orange to yellow vertical gradient
        Text: 'Good Morning!\\nHave a blessed day 🌅'

    Args:
        output_path: Destination path for the generated PNG image.

    Returns:
        The resolved output Path.
    """
    width, height = 400, 300
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    # Vertical gradient from orange (255, 127, 36) to warm gold/yellow (255, 215, 0)
    top_color = (255, 127, 36)
    bottom_color = (255, 215, 0)
    for y in range(height):
        factor = y / height
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * factor)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * factor)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * factor)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Decorative inner border
    draw.rectangle([(20, 20), (380, 280)], outline=(255, 255, 255), width=2)

    # Sun / Glow decoration circle
    draw.ellipse([(170, 45), (230, 105)], fill=(255, 245, 180), outline=(255, 255, 255))

    title_font = _get_font(size=24, bold=True)
    subtitle_font = _get_font(size=18, bold=False)

    # Title text
    draw.text(
        (200, 150),
        "Good Morning!",
        fill=(100, 35, 0),
        anchor="mm",
        font=title_font,
    )

    # Subtitle text
    draw.text(
        (200, 200),
        "Have a blessed day 🌅",
        fill=(110, 40, 0),
        anchor="mm",
        font=subtitle_font,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG")
    logger.info("Generated Good Morning image at %s", output_path)
    return output_path


def generate_sale_poster(output_path: Path) -> Path:
    """Generate sample electronics mega sale poster image.

    Image properties:
        Dimensions: 400x300
        Background: Red (#D32F2F)
        Text: 'MEGA SALE!\\n60% OFF\\nThis Weekend Only' in white and yellow

    Args:
        output_path: Destination path for the generated PNG image.

    Returns:
        The resolved output Path.
    """
    width, height = 400, 300
    # Bold red background
    img = Image.new("RGB", (width, height), color=(211, 47, 47))
    draw = ImageDraw.Draw(img)

    # Yellow dashed/solid decorative border
    draw.rectangle([(15, 15), (385, 285)], outline=(255, 215, 0), width=4)

    header_font = _get_font(size=26, bold=True)
    discount_font = _get_font(size=32, bold=True)
    footer_font = _get_font(size=18, bold=True)

    # Draw Banner Header
    draw.text(
        (200, 70),
        "MEGA SALE!",
        fill=(255, 215, 0),
        anchor="mm",
        font=header_font,
    )

    # Draw Discount Badge
    draw.rectangle([(80, 115), (320, 185)], fill=(255, 255, 255))
    draw.text(
        (200, 150),
        "UP TO 60% OFF",
        fill=(211, 47, 47),
        anchor="mm",
        font=discount_font,
    )

    # Draw Footer
    draw.text(
        (200, 230),
        "This Weekend Only!",
        fill=(255, 255, 255),
        anchor="mm",
        font=footer_font,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG")
    logger.info("Generated sale poster image at %s", output_path)
    return output_path


def generate_audio_placeholder(output_path: Path, description: str = "voice note") -> Path:
    """Generate a placeholder Ogg Vorbis audio file.

    Writes a standard Ogg stream header with minimal payload so the file is recognized
    as a non-empty audio container placeholder.

    Args:
        output_path: Destination path for the .ogg audio file.
        description: Description of the audio clip for logging.

    Returns:
        The resolved output Path.
    """
    # Standard Ogg container header signature (capture pattern 'OggS') + basic header fields
    ogg_header = (
        b"OggS"  # Capture pattern
        b"\x00"  # Stream structure version
        b"\x02"  # Header type flag (BOS - beginning of stream)
        b"\x00\x00\x00\x00\x00\x00\x00\x00"  # Granule position (0)
        b"\x01\x00\x00\x00"  # Bitstream serial number
        b"\x00\x00\x00\x00"  # Page sequence number
        b"\x12\x34\x56\x78"  # Page checksum placeholder
        b"\x01"  # Page segments (1 segment)
        b"\x1e"  # Segment length table (30 bytes)
        b"WhatsApp Voice Note Placeholder"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(ogg_header)
    logger.info("Generated placeholder audio file (%s) at %s (%d bytes)", description, output_path, len(ogg_header))
    return output_path


def validate_fixtures() -> bool:
    """Validate all user profiles and sample messages against Pydantic models.

    Returns:
        True if all fixtures are valid, False otherwise.
    """
    import sys

    # Add src to sys.path if not present
    src_dir = str(PROJECT_ROOT / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    from router.models import IncomingMessage, UserProfile

    all_valid = True

    # Validate User Profiles
    for user_file in USERS_DIR.glob("*.json"):
        try:
            with open(user_file, encoding="utf-8") as f:
                data = json.load(f)
            profile = UserProfile.model_validate(data)
            logger.info("✓ Validated user profile: %s (ID: %s)", user_file.name, profile.user_id)
        except Exception as err:
            logger.error("✗ Failed validating user profile %s: %s", user_file.name, err)
            all_valid = False

    # Validate Message Fixtures
    messages_file = MESSAGES_DIR / "sample_messages.json"
    if messages_file.exists():
        try:
            with open(messages_file, encoding="utf-8") as f:
                messages_data = json.load(f)
            if not isinstance(messages_data, list):
                raise ValueError("sample_messages.json must contain a list of messages")
            for idx, msg_raw in enumerate(messages_data, start=1):
                msg = IncomingMessage.model_validate(msg_raw)
                # Check media file existence if media_path is specified
                if msg.media_path:
                    media_file = PROJECT_ROOT / msg.media_path
                    if not media_file.exists():
                        logger.warning("Media path referenced in %s not found: %s", msg.message_id, media_file)
            logger.info("✓ Validated %d incoming messages in %s", len(messages_data), messages_file.name)
        except Exception as err:
            logger.error("✗ Failed validating messages in %s: %s", messages_file.name, err)
            all_valid = False
    else:
        logger.error("✗ Missing %s", messages_file)
        all_valid = False

    return all_valid


def main() -> None:
    """Generate all media fixtures and run verification."""
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Generate Images
    generate_maintenance_notice(MEDIA_DIR / "maintenance_notice.png")
    generate_good_morning(MEDIA_DIR / "good_morning.png")
    generate_sale_poster(MEDIA_DIR / "sale_poster.png")

    # 2. Generate Placeholder Audio Files
    generate_audio_placeholder(MEDIA_DIR / "school_closure.ogg", description="School closure voice note")
    generate_audio_placeholder(MEDIA_DIR / "weekend_plans.ogg", description="Weekend plans voice note")

    # 3. Validate Everything
    logger.info("Validating all fixture JSON files...")
    if validate_fixtures():
        logger.info("All fixtures generated and validated successfully! 🎉")
    else:
        raise RuntimeError("Fixture validation failed!")


if __name__ == "__main__":
    main()
