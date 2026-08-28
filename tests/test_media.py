"""Unit tests for router.media module."""

from __future__ import annotations

import base64
from pathlib import Path
import pytest

from router.config import MAX_AUDIO_SIZE_BYTES, MAX_IMAGE_SIZE_BYTES
from router.media import (
    build_audio_content_part,
    build_image_content_part,
    detect_mime_type,
    load_audio_as_base64,
    load_image_as_base64,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "media"


class TestDetectMimeType:
    """Tests for detect_mime_type function."""

    @pytest.mark.parametrize(
        "filename,expected_mime",
        [
            ("photo.jpg", "image/jpeg"),
            ("photo.jpeg", "image/jpeg"),
            ("photo.png", "image/png"),
            ("photo.webp", "image/webp"),
            ("animation.gif", "image/gif"),
            ("voice.ogg", "audio/ogg"),
            ("voice.opus", "audio/ogg"),
            ("voice.oga", "audio/ogg"),
            ("audio.mp3", "audio/mpeg"),
            ("recording.wav", "audio/wav"),
            ("audio.mp4", "audio/mp4"),
            ("audio.m4a", "audio/mp4"),
            ("audio.aac", "audio/mp4"),
            ("PHOTO.PNG", "image/png"),
            ("VOICE.OGG", "audio/ogg"),
        ],
    )
    def test_known_extensions(self, filename: str, expected_mime: str) -> None:
        """Test detection for all supported media extensions."""
        assert detect_mime_type(filename) == expected_mime

    def test_unknown_extension_raises(self) -> None:
        """Test that unknown extensions raise ValueError."""
        with pytest.raises(ValueError, match="Could not determine MIME type"):
            detect_mime_type("file.unknown_extension_xyz123")


class TestLoadImageAsBase64:
    """Tests for load_image_as_base64 function."""

    def test_load_valid_image(self) -> None:
        """Test loading a valid fixture image."""
        img_path = FIXTURES_DIR / "good_morning.png"
        b64_data, mime_type = load_image_as_base64(img_path)

        assert mime_type == "image/png"
        assert isinstance(b64_data, str)
        # Verify it decodes back to original bytes
        decoded = base64.b64decode(b64_data)
        assert decoded == img_path.read_bytes()

    def test_nonexistent_image_raises(self) -> None:
        """Test that a nonexistent image path raises ValueError."""
        with pytest.raises(ValueError, match="does not exist"):
            load_image_as_base64("/nonexistent/path/image.png")

    def test_empty_image_raises(self, tmp_path: Path) -> None:
        """Test that an empty image file raises ValueError."""
        empty_file = tmp_path / "empty.png"
        empty_file.write_bytes(b"")
        with pytest.raises(ValueError, match="is empty"):
            load_image_as_base64(empty_file)

    def test_oversized_image_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that an image exceeding MAX_IMAGE_SIZE_BYTES raises ValueError."""
        img_file = tmp_path / "large.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 100)

        # Mock MAX_IMAGE_SIZE_BYTES to a small value for testing
        monkeypatch.setattr("router.media.MAX_IMAGE_SIZE_BYTES", 50)
        with pytest.raises(ValueError, match="exceeds maximum allowed size"):
            load_image_as_base64(img_file)

    def test_unsupported_image_mime_raises(self, tmp_path: Path) -> None:
        """Test that an unsupported image MIME type raises ValueError."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Hello world")
        with pytest.raises(ValueError, match="Unsupported image MIME type"):
            load_image_as_base64(txt_file)


class TestLoadAudioAsBase64:
    """Tests for load_audio_as_base64 function."""

    def test_load_valid_audio(self) -> None:
        """Test loading a valid fixture audio file."""
        audio_path = FIXTURES_DIR / "school_closure.ogg"
        b64_data, mime_type = load_audio_as_base64(audio_path)

        assert mime_type == "audio/ogg"
        assert isinstance(b64_data, str)
        decoded = base64.b64decode(b64_data)
        assert decoded == audio_path.read_bytes()

    def test_nonexistent_audio_raises(self) -> None:
        """Test that a nonexistent audio path raises ValueError."""
        with pytest.raises(ValueError, match="does not exist"):
            load_audio_as_base64("/nonexistent/path/voice.ogg")

    def test_empty_audio_raises(self, tmp_path: Path) -> None:
        """Test that an empty audio file raises ValueError."""
        empty_file = tmp_path / "empty.ogg"
        empty_file.write_bytes(b"")
        with pytest.raises(ValueError, match="is empty"):
            load_audio_as_base64(empty_file)

    def test_oversized_audio_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that an audio exceeding MAX_AUDIO_SIZE_BYTES raises ValueError."""
        audio_file = tmp_path / "large.ogg"
        audio_file.write_bytes(b"OggS" + b"x" * 100)

        # Mock MAX_AUDIO_SIZE_BYTES to a small value for testing
        monkeypatch.setattr("router.media.MAX_AUDIO_SIZE_BYTES", 50)
        with pytest.raises(ValueError, match="exceeds maximum allowed size"):
            load_audio_as_base64(audio_file)

    def test_unsupported_audio_mime_raises(self, tmp_path: Path) -> None:
        """Test that an unsupported audio MIME type raises ValueError."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Hello world")
        with pytest.raises(ValueError, match="Unsupported audio MIME type"):
            load_audio_as_base64(txt_file)


class TestBuildContentParts:
    """Tests for build_image_content_part and build_audio_content_part."""

    def test_build_image_content_part(self) -> None:
        """Test image content part dictionary structure."""
        img_path = FIXTURES_DIR / "sale_poster.png"
        part = build_image_content_part(img_path)

        assert part["type"] == "image"
        assert part["mime_type"] == "image/png"
        assert len(part["data"]) > 0

    def test_build_audio_content_part(self) -> None:
        """Test audio content part dictionary structure."""
        audio_path = FIXTURES_DIR / "weekend_plans.ogg"
        part = build_audio_content_part(audio_path)

        assert part["type"] == "audio"
        assert part["mime_type"] == "audio/ogg"
        assert len(part["data"]) > 0
