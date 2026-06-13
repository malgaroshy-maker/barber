"""Unit tests for ai.face_validator."""
import os
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai.face_validator import validate_selfie, _get_yunet


def _png_bytes(width: int, height: int, color: tuple[int, int, int]) -> bytes:
    """Return a minimal solid-colour PNG as bytes."""
    import io
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_yunet_model_present():
    """The YuNet model should be present locally (or downloaded on demand)."""
    det = _get_yunet()
    assert det is not None, "YuNet model not loadable"


def test_solid_image_rejected_as_no_face():
    ok, msg = validate_selfie(_png_bytes(400, 400, (128, 128, 128)))
    assert ok is False
    assert "وش" in msg or "صورة" in msg


def test_tiny_image_rejected():
    ok, msg = validate_selfie(_png_bytes(20, 20, (200, 200, 200)))
    assert ok is False
    assert "صغيرة" in msg or "وش" in msg


@pytest.mark.skipif(not os.environ.get("RUN_LIVE_TESTS"),
                    reason="set RUN_LIVE_TESTS=1 to download a sample face image")
def test_real_face_passes():
    import urllib.request
    url = "https://thispersondoesnotexist.com/"
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = r.read()
    ok, msg = validate_selfie(data)
    assert ok is True, f"validator should accept a real face, got: {msg}"
