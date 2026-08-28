"""Media loading and validation helpers for WhatsApp multimodal content.

Provides utilities for reading, validating, and encoding images and audio
files into base64 content parts suitable for the Gemini API.
"""

from __future__ import annotations

import base64
import logging
import mimetypes
from pathlib import Path

from router.config import (
    MAX_AUDIO_SIZE_BYTES,
    MAX_IMAGE_SIZE_BYTES,
    SUPPORTED_AUDIO_MIMES,
    SUPPORTED_IMAGE_MIMES,
)

logger = logging.getLogger(__name__)

# Map common extensions to canonical MIME types supported by Gemini
_EXTENSION_MIME_MAP: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".ogg": "audio/ogg",
    ".opus": "audio/ogg",
    ".oga": "audio/ogg",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".mp4": "audio/mp4",
    ".m4a": "audio/mp4",
    ".aac": "audio/mp4",
}


def detect_mime_type(path: str | Path) -> str:
    """Detect MIME type from file extension.

    First checks explicit mappings for WhatsApp media formats, then falls back
    to standard mimetypes library.

    Args:
        path: Path to the file.

    Returns:
        The detected MIME type string.

    Raises:
        ValueError: If the MIME type cannot be determined.
    """
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    if suffix in _EXTENSION_MIME_MAP:
        return _EXTENSION_MIME_MAP[suffix]

    guessed_type, _ = mimetypes.guess_type(str(file_path))
    if guessed_type:
        return guessed_type

    raise ValueError(f"Could not determine MIME type for file: {path}")


def load_image_as_base64(path: str | Path) -> tuple[str, str]:
    """Load an image file and return (base64_data, mime_type).

    Validates file existence, non-empty size, size <= MAX_IMAGE_SIZE_BYTES,
    and MIME type compatibility with Gemini.

    Args:
        path: Path to the image file.

    Returns:
        A tuple of (base64_encoded_data, mime_type).

    Raises:
        ValueError: If the file does not exist, exceeds maximum size, is empty,
            or has an unsupported MIME type.
    """
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        raise ValueError(f"Image file does not exist or is not a regular file: {path}")

    size = file_path.stat().st_size
    if size == 0:
        raise ValueError(f"Image file is empty (0 bytes): {path}")
    if size > MAX_IMAGE_SIZE_BYTES:
        raise ValueError(
            f"Image file size ({size} bytes) exceeds maximum allowed size "
            f"({MAX_IMAGE_SIZE_BYTES} bytes): {path}"
        )

    mime_type = detect_mime_type(file_path)
    if mime_type not in SUPPORTED_IMAGE_MIMES:
        raise ValueError(
            f"Unsupported image MIME type '{mime_type}' for {path}. "
            f"Supported: {sorted(SUPPORTED_IMAGE_MIMES)}"
        )

    data = file_path.read_bytes()
    b64_str = base64.b64encode(data).decode("utf-8")
    return b64_str, mime_type


def load_audio_as_base64(path: str | Path) -> tuple[str, str]:
    """Load an audio file and return (base64_data, mime_type).

    Validates file existence, non-empty size, size <= MAX_AUDIO_SIZE_BYTES,
    and MIME type compatibility with Gemini.

    Args:
        path: Path to the audio file.

    Returns:
        A tuple of (base64_encoded_data, mime_type).

    Raises:
        ValueError: If the file does not exist, exceeds maximum size, is empty,
            or has an unsupported MIME type.
    """
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        raise ValueError(f"Audio file does not exist or is not a regular file: {path}")

    size = file_path.stat().st_size
    if size == 0:
        raise ValueError(f"Audio file is empty (0 bytes): {path}")
    if size > MAX_AUDIO_SIZE_BYTES:
        raise ValueError(
            f"Audio file size ({size} bytes) exceeds maximum allowed size "
            f"({MAX_AUDIO_SIZE_BYTES} bytes): {path}"
        )

    mime_type = detect_mime_type(file_path)
    if mime_type not in SUPPORTED_AUDIO_MIMES:
        raise ValueError(
            f"Unsupported audio MIME type '{mime_type}' for {path}. "
            f"Supported: {sorted(SUPPORTED_AUDIO_MIMES)}"
        )

    data = file_path.read_bytes()
    b64_str = base64.b64encode(data).decode("utf-8")
    return b64_str, mime_type


def build_image_content_part(path: str | Path) -> dict[str, str]:
    """Build a Gemini API content part dict for an image file.

    Args:
        path: Path to the image file.

    Returns:
        Dict with keys 'type', 'data', and 'mime_type'.

    Raises:
        ValueError: If image loading or validation fails.
    """
    base64_data, mime_type = load_image_as_base64(path)
    return {
        "type": "image",
        "data": base64_data,
        "mime_type": mime_type,
    }


def build_audio_content_part(path: str | Path) -> dict[str, str]:
    """Build a Gemini API content part dict for an audio file.

    Args:
        path: Path to the audio file.

    Returns:
        Dict with keys 'type', 'data', and 'mime_type'.

    Raises:
        ValueError: If audio loading or validation fails.
    """
    base64_data, mime_type = load_audio_as_base64(path)
    return {
        "type": "audio",
        "data": base64_data,
        "mime_type": mime_type,
    }
