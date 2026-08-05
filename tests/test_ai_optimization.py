import os
from pathlib import Path
import pytest

from conversation.catalogue_matcher import (
    detect_try_on_intent,
    match_category,
    match_haircut,
    normalize_arabic_text,
)
from ai.openrouter_llm import build_system_prompt, generate_llm_response
from ai.face_analyzer import analyze_face_shape, _detect_face_shape_geometric
from ai.face_validator import validate_selfie
from ai.hair_mask import create_hair_mask

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_FACE = PROJECT_ROOT / "test_real_face.jpg"


def test_arabic_text_normalization():
    assert normalize_arabic_text("١٢٣") == "123"
    assert normalize_arabic_text("أُندركَت") == "اندركت"
    assert normalize_arabic_text("قصة جميلة") == "قصه جميله"


def test_category_matching_enhanced():
    cat1 = match_category("١")
    assert cat1 is not None and cat1["id"] == "fades"

    cat2 = match_category("قسم 2")
    assert cat2 is not None and cat2["id"] == "classic"

    cat_ord = match_category("القسم الثالث")
    assert cat_ord is not None and cat_ord["id"] == "modern"

    cat_kw = match_category("قصات قصيرة")
    assert cat_kw is not None and cat_kw["id"] == "short"


def test_haircut_matching_enhanced():
    h1 = match_haircut("بومبادور")
    assert h1 is not None and h1["id"] == "pompadour"

    h2 = match_haircut("قصة البومبادور الكلاسيكية")
    assert h2 is not None and h2["id"] == "pompadour"

    h3 = match_haircut("buzz cut")
    assert h3 is not None and h3["id"] == "buzz_cut"


def test_try_on_intent_enhanced():
    assert detect_try_on_intent("عايز اجرب قصة عليا") is True
    assert detect_try_on_intent("ai") is True
    assert detect_try_on_intent("ذكاء اصطناعي") is True
    assert detect_try_on_intent("ركبلي القصة دي") is True
    assert detect_try_on_intent("بكام القصة دي؟") is False


def test_openrouter_prompt_and_fallbacks():
    prompt = build_system_prompt()
    assert "أسطى حلاق" in prompt
    assert "30 قصة" in prompt or "30" in prompt


@pytest.mark.asyncio
async def test_openrouter_llm_response_without_key(monkeypatch):
    monkeypatch.setattr("ai.openrouter_llm.OPENROUTER_API_KEY", "")
    reply = await generate_llm_response("مرحبا", [])
    assert reply is None


def test_face_shape_geometric_fallback():
    if TEST_FACE.exists():
        img_bytes = TEST_FACE.read_bytes()
        shape = _detect_face_shape_geometric(img_bytes)
        assert shape in {"oval", "round", "square", "heart", "oblong", "diamond"}


def test_analyze_face_shape_integration():
    if TEST_FACE.exists():
        img_bytes = TEST_FACE.read_bytes()
        shape = analyze_face_shape(img_bytes)
        assert shape in {"oval", "round", "square", "heart", "oblong", "diamond"}


def test_selfie_validation_with_real_face():
    if TEST_FACE.exists():
        img_bytes = TEST_FACE.read_bytes()
        valid, msg = validate_selfie(img_bytes)
        assert valid is True
        assert msg == "done"


def test_hair_mask_generation_with_real_face():
    if TEST_FACE.exists():
        img_bytes = TEST_FACE.read_bytes()
        mask_bytes = create_hair_mask(img_bytes, haircut_id="buzz_cut")
        assert mask_bytes is not None
        assert len(mask_bytes) > 100
