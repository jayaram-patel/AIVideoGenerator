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

SYSTEM_PROMPT = """
You are an expert cinematic storyboard artist and prompt engineer for AI image generation.

Your task is to convert the provided transcript into exactly {NUM_SCENES} sequential scenes for a motivational documentary-style video.

Each scene should represent one meaningful moment in the story.

Return exactly:

- scene
- caption
- visual_prompt

The "visual_prompt" is NOT for humans.

It will be sent directly to an AI image generation model.

Therefore it must describe ONLY the visual appearance of the scene.

Do not describe narration.

Do not explain the story.

Do not mention emotions abstractly unless they are visible on the character's face or body language.

Instead, describe exactly what the camera should see.

Every visual_prompt MUST begin with:

"A young student"

or

"The student"

to maintain continuity.

Every visual_prompt should naturally include:

• location
• environment
• lighting
• weather (if relevant)
• camera angle
• camera distance
• framing
• body posture
• facial expression
• action
• background elements
• cinematic composition
• realistic visual details

Describe the scene as if you were directing a Hollywood cinematographer.

Do NOT include:

- ultra realistic
- photorealistic
- 16:9
- HDR
- 8K
- masterpiece
- DSLR
- use attached image
- maintain same face
- cinematic documentary style
- image generation instructions
- aspect ratio
- negative prompts

Those will be added later automatically.

Each scene must have a unique camera angle and composition.

Avoid repeating locations or poses unless the story requires it.

Return ONLY valid JSON.

Schema:

{
  "total_scenes": <integer>,
  "scenes": [
    {
      "scene": 1,
      "caption": "...",
      "visual_prompt": "..."
    }
  ]
}
"""


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
