"""
Local transcript splitter — no API required.

Splits the transcript into N scenes by dividing sentences evenly.
Used as a fallback when Gemini/OpenAI quota is exhausted, so the
pipeline can still run end-to-end for testing.
"""

import re
import logging

logger = logging.getLogger(__name__)


def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentences using punctuation boundaries."""
    # Split on sentence-ending punctuation followed by whitespace
    raw = re.split(r'(?<=[.!?])\s+', text.strip())
    # Filter out empty strings
    return [s.strip() for s in raw if s.strip()]


def split_transcript_locally(transcript: str, num_scenes: int) -> dict:
    """
    Split a transcript into num_scenes scenes without any API call.

    Groups sentences evenly across scenes and generates simple prompts.
    Returns a dict compatible with ScriptResponse schema.
    """
    sentences = _split_into_sentences(transcript)
    if not sentences:
        sentences = [transcript.strip()]

    # Distribute sentences evenly across scenes
    total = len(sentences)
    scenes = []

    for i in range(num_scenes):
        # Slice a proportional chunk of sentences
        start = round(i * total / num_scenes)
        end = round((i + 1) * total / num_scenes)
        chunk = sentences[start:end]
        text = " ".join(chunk) if chunk else sentences[i % total]

        # Generate a simple caption (first 10 words of the chunk)
        words = text.split()
        caption = " ".join(words[:10])
        if len(words) > 10:
            caption += "..."

        # Simple visual prompt
        visual_prompt = (
            f"Cinematic photograph of a person in a dramatic moment of inspiration. "
            f"Scene: {text[:120]}. "
            f"Warm cinematic lighting, shallow depth of field, motivational atmosphere."
        )

        scenes.append({
            "scene": i + 1,
            "caption": caption,
            "visual_prompt": visual_prompt,
        })

    logger.info("Local splitter generated %d scenes (no API call)", len(scenes))
    return {
        "total_scenes": num_scenes,
        "scenes": scenes,
    }
