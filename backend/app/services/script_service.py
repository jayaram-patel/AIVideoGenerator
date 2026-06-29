"""
Script service — orchestrates the transcript-to-scenes pipeline.

Calls OpenAI to split the transcript, validates the result,
and persists the scene data.
"""

import logging

from app.schemas.project import ScriptResponse
from app.services.openai_service import split_transcript
from app.services.project_service import project_service

logger = logging.getLogger(__name__)


async def generate_script(
    project_id: str,
    transcript: str,
    num_scenes: int,
) -> ScriptResponse:
    """
    Split a transcript into scenes via OpenAI and persist the result.

    Returns a validated ScriptResponse.
    """
    raw = await split_transcript(transcript, num_scenes)

    script = ScriptResponse.model_validate(raw)
    logger.info(
        "Script generated for project %s — %d scenes",
        project_id,
        script.total_scenes,
    )

    # Persist to disk
    await project_service.save_script(project_id, script.model_dump())

    return script
