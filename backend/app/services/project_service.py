"""
Project service — handles directory creation, file storage,
metadata, and ZIP export.
"""

import json
import uuid
import shutil
from pathlib import Path
from datetime import datetime, timezone

import aiofiles

from app.core.config import settings
from app.schemas.project import ProjectMetadata


class ProjectService:

    def __init__(self) -> None:
        self._output_dir = settings.BASE_OUTPUT_DIR
        self._uploads_dir = settings.UPLOADS_DIR

    def create_project_id(self) -> str:
        return uuid.uuid4().hex[:12]

    def get_project_dir(self, project_id: str) -> Path:
        return self._output_dir / project_id

    async def create_project(
        self,
        project_id: str,
        total_images: int,
        character_image_filename: str,
    ) -> ProjectMetadata:
        """Create project folder structure and save initial metadata."""
        project_dir = self.get_project_dir(project_id)
        (project_dir / "images").mkdir(parents=True, exist_ok=True)
        (project_dir / "metadata").mkdir(parents=True, exist_ok=True)

        metadata = ProjectMetadata(
            project_id=project_id,
            status="created",
            total_images=total_images,
            completed_images=0,
            character_image_filename=character_image_filename,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        await self._save_metadata(project_dir, metadata)
        return metadata

    async def save_upload(self, project_id: str, filename: str, content: bytes) -> Path:
        upload_dir = self._uploads_dir / project_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / filename
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)
        return file_path

    async def save_transcript_text(self, project_id: str, text: str) -> Path:
        """Save the raw transcript text to the project uploads."""
        upload_dir = self._uploads_dir / project_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        path = upload_dir / "transcript.txt"
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            await f.write(text)
        return path

    def get_upload_path(self, project_id: str, filename: str) -> Path:
        return self._uploads_dir / project_id / filename

    async def _save_metadata(self, project_dir: Path, metadata: ProjectMetadata) -> None:
        meta_path = project_dir / "metadata" / "project.json"
        async with aiofiles.open(meta_path, "w", encoding="utf-8") as f:
            await f.write(metadata.model_dump_json(indent=2))

    async def update_metadata(self, project_id: str, **updates: object) -> ProjectMetadata:
        project_dir = self.get_project_dir(project_id)
        meta_path = project_dir / "metadata" / "project.json"
        async with aiofiles.open(meta_path, "r", encoding="utf-8") as f:
            raw = await f.read()
        metadata = ProjectMetadata.model_validate_json(raw)
        for key, value in updates.items():
            if hasattr(metadata, key):
                setattr(metadata, key, value)
        await self._save_metadata(project_dir, metadata)
        return metadata

    async def get_metadata(self, project_id: str) -> ProjectMetadata | None:
        meta_path = self.get_project_dir(project_id) / "metadata" / "project.json"
        if not meta_path.exists():
            return None
        async with aiofiles.open(meta_path, "r", encoding="utf-8") as f:
            raw = await f.read()
        return ProjectMetadata.model_validate_json(raw)

    async def save_script(self, project_id: str, script_data: dict) -> Path:
        script_path = self.get_project_dir(project_id) / "metadata" / "scenes.json"
        async with aiofiles.open(script_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(script_data, indent=2, ensure_ascii=False))
        return script_path

    def create_zip(self, project_id: str) -> Path:
        project_dir = self.get_project_dir(project_id)
        zip_path = self._output_dir / f"{project_id}"
        return Path(shutil.make_archive(str(zip_path), "zip", str(project_dir)))

    def get_zip_path(self, project_id: str) -> Path | None:
        zip_path = self._output_dir / f"{project_id}.zip"
        return zip_path if zip_path.exists() else None


project_service = ProjectService()
