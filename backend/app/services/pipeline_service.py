"""
Pipeline service — orchestrates the full generation workflow.

Steps:
  1. Split transcript into scenes via Gemini (text model)
  2. Generate images for each scene — tries Gemini image models,
     falls back to local Pillow renderer so images always get produced
  3. Update project metadata at each step

OpenAI is NOT used — all AI calls go through the Gemini client.
"""

import asyncio
import logging
from pathlib import Path

from app.services.project_service import project_service
from app.services.script_service import generate_script
from app.services.gemini_service import generate_scene_image

logger = logging.getLogger(__name__)

# Shared dict for real-time progress tracking, keyed by project_id
_active_jobs: dict[str, dict] = {}


def get_job_state(project_id: str) -> dict | None:
    return _active_jobs.get(project_id)


async def _generate_single_image(
    visual_prompt: str,
    caption: str,
    scene_num: int,
    char_image_path: Path,
    output_path: Path,
) -> Path:
    """
    Generate one image. The gemini_service already has a local fallback
    so this always returns a valid path — no retry wrapper needed.
    """
    return await generate_scene_image(
        visual_prompt=visual_prompt,
        caption=caption,
        scene_num=scene_num,
        character_image_path=char_image_path,
        output_path=output_path,
    )


async def run_pipeline(project_id: str) -> None:
    """
    Full generation pipeline. Runs as a FastAPI background task.

    Always completes — images are produced via local renderer if
    API image generation is unavailable.
    """
    _active_jobs[project_id] = {
        "status": "generating_script",
        "message": "Splitting transcript into scenes...",
        "completed": 0,
        "total": 0,
        "error": None,
    }

    try:
        # ── 1. Load project metadata ────────────────────────────────────────
        metadata = await project_service.get_metadata(project_id)
        if not metadata:
            raise ValueError(f"Project {project_id} not found")

        total_images = metadata.total_images
        _active_jobs[project_id]["total"] = total_images

        await project_service.update_metadata(project_id, status="generating_script")

        # ── 2. Load transcript ───────────────────────────────────────────────
        transcript_path = project_service.get_upload_path(project_id, "transcript.txt")
        transcript = transcript_path.read_text(encoding="utf-8")

        # ── 3. Split into scenes (Gemini text model) ─────────────────────────
        _active_jobs[project_id]["message"] = "AI is splitting transcript into scenes..."
        script = await generate_script(project_id, transcript, total_images)

        await project_service.update_metadata(project_id, status="generating_images")
        _active_jobs[project_id]["status"] = "generating_images"
        _active_jobs[project_id]["message"] = "Generating images..."

        # ── 4. Generate images ────────────────────────────────────────────────
        char_image_path = project_service.get_upload_path(
            project_id, metadata.character_image_filename
        )
        project_dir = project_service.get_project_dir(project_id)

        for i, scene in enumerate(script.scenes):
            scene_num = scene.scene
            output_path = project_dir / "images" / f"scene_{scene_num:03d}.png"

            _active_jobs[project_id]["message"] = (
                f"Generating image {i + 1} of {total_images}..."
            )

            try:
                await _generate_single_image(
                    visual_prompt=scene.visual_prompt,
                    caption=scene.caption,
                    scene_num=scene_num,
                    char_image_path=char_image_path,
                    output_path=output_path,
                )
            except Exception as img_err:
                # Should never reach here since gemini_service has a local fallback,
                # but handle defensively anyway
                logger.warning(
                    "Image %d completely failed for project %s: %s",
                    scene_num, project_id, str(img_err),
                )

            # Update progress even if this image failed
            completed = i + 1
            _active_jobs[project_id]["completed"] = completed
            await project_service.update_metadata(
                project_id, completed_images=completed
            )

        # ── 5. Done ───────────────────────────────────────────────────────────
        final_count = len(list((project_dir / "images").glob("*.png")))
        await project_service.update_metadata(
            project_id, status="completed", completed_images=final_count
        )
        _active_jobs[project_id]["status"] = "completed"
        _active_jobs[project_id]["completed"] = final_count
        _active_jobs[project_id]["message"] = (
            f"Done! {final_count} of {total_images} images generated."
        )

        logger.info("Pipeline completed for project %s (%d images)", project_id, final_count)

    except Exception as e:
        logger.exception("Pipeline failed for project %s", project_id)
        _active_jobs[project_id]["status"] = "error"
        _active_jobs[project_id]["error"] = str(e)
        _active_jobs[project_id]["message"] = f"Error: {str(e)}"

        try:
            await project_service.update_metadata(project_id, status="error")
        except Exception:
            pass

    finally:
        # Keep the job state for 5 minutes so the frontend can read the final status
        await asyncio.sleep(300)
        _active_jobs.pop(project_id, None)
