"""
Project API routes — create project, trigger generation, check status, download ZIP.
"""

import asyncio

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

from app.schemas.project import ProjectCreateResponse, ProjectMetadata
from app.services.project_service import project_service
from app.services.pipeline_service import run_pipeline, get_job_state

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("/create", response_model=ProjectCreateResponse)
async def create_project(
    background_tasks: BackgroundTasks,
    transcript: str = Form(...),
    number_of_images: int = Form(10),
    character_image: UploadFile = File(...),
):
    """
    Create a new project and immediately start the generation pipeline.

    Accepts transcript text, desired image count, and a character reference image.
    The AI pipeline runs in the background — poll /status for progress.
    """
    if len(transcript.strip()) < 20:
        raise HTTPException(status_code=400, detail="Transcript must be at least 20 characters")

    if number_of_images < 5 or number_of_images > 25:
        raise HTTPException(status_code=400, detail="Number of images must be between 5 and 25")

    valid_ext = (".png", ".jpg", ".jpeg")
    if not character_image.filename or not character_image.filename.lower().endswith(valid_ext):
        raise HTTPException(status_code=400, detail="Character image must be .png or .jpg")

    project_id = project_service.create_project_id()

    # Save character image
    image_content = await character_image.read()
    await project_service.save_upload(project_id, character_image.filename, image_content)

    # Save transcript text
    await project_service.save_transcript_text(project_id, transcript)

    # Create project structure
    await project_service.create_project(
        project_id=project_id,
        total_images=number_of_images,
        character_image_filename=character_image.filename,
    )

    # Start background pipeline
    background_tasks.add_task(run_pipeline, project_id)

    return ProjectCreateResponse(
        project_id=project_id,
        message="Project created — generation started",
        status="created",
    )


@router.get("/{project_id}/status", response_model=ProjectMetadata)
async def get_project_status(project_id: str):
    """Return the project metadata with live progress from the pipeline."""
    metadata = await project_service.get_metadata(project_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Project not found")

    # Overlay live job state if pipeline is running
    job = get_job_state(project_id)
    if job:
        metadata.status = job["status"]
        metadata.completed_images = job["completed"]

    return metadata


@router.get("/{project_id}/progress")
async def get_progress(project_id: str):
    """
    Lightweight endpoint returning live pipeline progress.
    Used for polling from the frontend.
    """
    job = get_job_state(project_id)
    if job:
        return {
            "project_id": project_id,
            "status": job["status"],
            "message": job["message"],
            "completed": job["completed"],
            "total": job["total"],
            "error": job["error"],
        }

    # Fall back to disk metadata
    metadata = await project_service.get_metadata(project_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Project not found")

    return {
        "project_id": project_id,
        "status": metadata.status,
        "message": f"Status: {metadata.status}",
        "completed": metadata.completed_images,
        "total": metadata.total_images,
        "error": None,
    }


@router.get("/{project_id}/download")
async def download_project(project_id: str):
    metadata = await project_service.get_metadata(project_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Project not found")

    zip_path = project_service.get_zip_path(project_id)
    if not zip_path:
        zip_path = project_service.create_zip(project_id)

    return FileResponse(
        path=str(zip_path),
        media_type="application/zip",
        filename=f"images_{project_id}.zip",
    )
