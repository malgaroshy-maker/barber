from pathlib import Path

import pytest

from ai.hair_mask import create_hair_mask

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REAL_FACE = PROJECT_ROOT / "test_real_face.jpg"


def test_create_hair_mask_with_real_face():
    if not REAL_FACE.exists():
        pytest.skip("test_real_face.jpg not found")

    mask_bytes = create_hair_mask(REAL_FACE.read_bytes())
    assert isinstance(mask_bytes, bytes)
    assert len(mask_bytes) > 0


def test_create_hair_mask_fallback_no_face():
    # A 100x100 blue image contains no face.
    image = (PROJECT_ROOT / "test_infu_input.png").read_bytes()
    mask_bytes = create_hair_mask(image)
    assert isinstance(mask_bytes, bytes)
    assert len(mask_bytes) > 0
