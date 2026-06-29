"""
Scene splitting service — splits a transcript into cinematic scenes.

Uses Gemini Flash (text) instead of OpenAI so no quota issues arise.
Falls back gracefully if the JSON structure is incomplete.
"""

import json
import logging

from google import genai
from google.genai import types

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: genai.Client | None = None

SYSTEM_PROMPT = """You are a cinematic scene planner for motivational video content.
Given a transcript and a desired number of scenes, split the transcript into exactly
that many sequential scenes.

For each scene return:
- "scene": the 1-indexed scene number
- "caption": a short, punchy subtitle (max 12 words) that captures the emotional beat
- "visual_prompt": a detailed cinematic image-generation prompt describing what the scene
  should look like. Include setting, lighting, mood, camera angle, and the main character's
  action or expression. Always start with "Cinematic photograph of".

Return ONLY valid JSON matching this schema (no markdown, no code fences):
{
  "total_scenes": <int>,
  "scenes": [
    { "scene": 1, "caption": "...", "visual_prompt": "..." },
    ...
  ]
}"""


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


async def split_transcript(transcript: str, num_scenes: int) -> dict:
    """
    Call Gemini Flash to split a transcript into scenes.

    Returns the parsed JSON dict with keys: total_scenes, scenes.
    """
    client = _get_client()

    user_message = (
        f"Split the following transcript into exactly {num_scenes} scenes.\n\n"
        f"--- TRANSCRIPT ---\n{transcript}\n--- END ---"
    )

    logger.info("Calling Gemini Flash to split transcript into %d scenes", num_scenes)

    response = client.models.generate_content(
        model=settings.GEMINI_TEXT_MODEL,
        contents=[
            types.Content(parts=[types.Part.from_text(text=SYSTEM_PROMPT)], role="user"),
            types.Content(parts=[types.Part.from_text(text=user_message)], role="user"),
        ],
        config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=8192,
        ),
    )

    raw = response.text or "{}"
    logger.info("Gemini response received (%d chars)", len(raw))

    # Strip markdown code fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        # Remove first line (```json or ```) and last line (```)
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    data = json.loads(raw)

    # Validate basic structure
    if "scenes" not in data:
        raise ValueError("Gemini response missing 'scenes' key")

    return data
