"""
Gemini service — generates scene images.

Strategy:
  1. Try Gemini image generation models in priority order.
  2. On any failure (quota, 404, 400), fall back to the local
     Pillow-based renderer which always succeeds.

This guarantees images are always produced even when API quotas
are exhausted.
"""

import logging
from pathlib import Path

from google import genai
from google.genai import types
from PIL import Image
import io

from app.core.config import settings
from app.services.image_renderer import render_scene_image

logger = logging.getLogger(__name__)

# Ordered list of image-generation models to try (most capable first)
_IMAGE_MODELS = [
    settings.GEMINI_IMAGE_MODEL,
    "gemini-2.5-flash-image",
    "gemini-3.1-flash-image",
    "gemini-3-pro-image",
]

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def _try_gemini_image(
    visual_prompt: str,
    caption: str,
    character_image_path: Path,
    output_path: Path,
) -> Path | None:
    """
    Attempt image generation via Gemini API.

    Returns output_path on success, None on any failure.
    """
    client = _get_client()
    char_image_bytes = character_image_path.read_bytes()
    char_ext = character_image_path.suffix.lower().lstrip(".")
    if char_ext == "jpg":
        char_ext = "jpeg"

    full_prompt = (
        f"{visual_prompt}\n\n"
        f"The main character should closely resemble the reference image provided. "
        f'Add a cinematic caption overlay at the bottom: "{caption}"\n'
        f"Style: high quality, cinematic, 16:9 aspect ratio, dramatic lighting."
    )

    for model in _IMAGE_MODELS:
        if not model:
            continue
        try:
            response = client.models.generate_content(
                model=model,
                contents=[
                    types.Content(
                        parts=[
                            types.Part.from_bytes(
                                data=char_image_bytes,
                                mime_type=f"image/{char_ext}",
                            ),
                            types.Part.from_text(text=full_prompt),
                        ]
                    )
                ],
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                ),
            )

            if response.candidates and response.candidates[0].content:
                for part in response.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                        img = Image.open(io.BytesIO(part.inline_data.data))
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        img.save(str(output_path), "PNG")
                        logger.info("Gemini image saved (%s): %s", model, output_path.name)
                        return output_path

            logger.warning("Model %s returned no image data", model)

        except Exception as e:
            logger.warning("Model %s failed: %s", model, str(e)[:120])
            continue  # try next model

    return None


async def generate_scene_image(
    visual_prompt: str,
    caption: str,
    character_image_path: Path,
    output_path: Path,
    scene_num: int = 1,
) -> Path:
    """
    Generate a scene image — always succeeds.

    Tries Gemini API models first; falls back to local Pillow renderer
    if all API attempts fail (quota exhausted, model unavailable, etc.).
    """
    # Try Gemini API
    result = _try_gemini_image(visual_prompt, caption, character_image_path, output_path)
    if result:
        return result

    # Fall back to local renderer
    logger.info("Using local renderer for scene (all Gemini models failed)")
    return render_scene_image(
        visual_prompt=visual_prompt,
        caption=caption,
        scene_num=scene_num,
        character_image_path=character_image_path,
        output_path=output_path,
    )
