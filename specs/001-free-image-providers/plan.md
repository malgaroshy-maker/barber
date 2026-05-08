# Plan

## Files Modified
- `ai/hair_swap.py` — Add FreeTheAI provider, fix Pollinations, fix HuggingFace models, reorder cascade

## Steps
1. Add `generate_image_freetheai()` — POST to `https://api.freetheai.xyz/v1/images/generations` with `vhr/flux_dev` model
2. Fix `generate_image_pollinations()` — add retry (3 attempts with 2s backoff), remove seed param
3. Fix `swap_hair_huggingface()` — replace dead models with `black-forest-labs/FLUX.1-dev` and `stabilityai/stable-diffusion-3.5-medium`
4. Update `run_hair_swap()` cascade order: FreeTheAI → Pollinations → HuggingFace
5. Remove dead Gemini code (all 429)
