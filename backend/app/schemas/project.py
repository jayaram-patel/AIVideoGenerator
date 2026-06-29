"""
Pydantic schemas for the transcript-to-images pipeline.
"""

from pydantic import BaseModel, Field


class Scene(BaseModel):
    """One scene extracted from the transcript."""
    scene: int = Field(..., description="Scene number (1-indexed)")
    caption: str = Field(..., description="Short caption / subtitle for this scene")
    visual_prompt: str = Field(..., description="Cinematic image generation prompt")


class ScriptResponse(BaseModel):
    """Output from OpenAI: transcript split into scenes."""
    total_scenes: int
    scenes: list[Scene]


class ProjectMetadata(BaseModel):
    """Stored on disk as project.json."""
    project_id: str
    status: str = "created"
    total_images: int
    completed_images: int = 0
    character_image_filename: str
    created_at: str


class ProjectCreateResponse(BaseModel):
    """Returned after project creation."""
    project_id: str
    message: str
    status: str
