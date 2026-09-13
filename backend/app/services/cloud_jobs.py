"""One atomic, private Cloud Storage object per job; no container-local persistence."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from google.api_core.exceptions import NotFound, PreconditionFailed
from google.cloud import storage

from app.core.config import Settings
from app.db.models import FileJob
from app.services.jobs import JobNotFoundError, JobService


class JobConflictError(Exception):
    pass


class CloudJobService(JobService):
    def __init__(self, settings: Settings):
        self.settings = settings
        self.root = Path("/jobs")
        self.bucket = storage.Client().bucket(settings.storage_bucket)
        self.files: dict[str, str] = {}
        self.generation = 0

    def _key(self, file_id: str) -> str:
        try:
            if str(UUID(file_id)) != file_id:
                raise ValueError
        except ValueError as exc:
            raise JobNotFoundError("Subtitle job was not found.") from exc
        return f"jobs/{file_id}.json"

    def get(self, file_id: str) -> FileJob:
        blob = self.bucket.blob(self._key(file_id))
        try:
            # A single GET supplies both content and its generation.
            payload = json.loads(blob.download_as_bytes())
        except NotFound as exc:
            raise JobNotFoundError("Subtitle job was not found.") from exc
        self.generation = int(blob.generation)
        self.files = payload["files"]
        values = payload["job"]
        values["created_at"] = datetime.fromisoformat(values["created_at"])
        job = FileJob(**values)
        if job.created_at < datetime.now(UTC) - timedelta(hours=self.settings.retention_hours):
            raise JobNotFoundError("Subtitle job has expired.")
        return job

    def save(self, job: FileJob) -> None:
        values = {
            name: getattr(job, name)
            for name in (
                "id",
                "original_name",
                "source_format",
                "source_path",
                "generated_path",
                "output_format",
                "changes_json",
            )
        }
        values["created_at"] = job.created_at.isoformat()
        blob = self.bucket.blob(self._key(job.id))
        # Preserve the original creation time even when a transform replaces the object.
        blob.custom_time = job.created_at
        try:
            blob.upload_from_string(
                json.dumps({"job": values, "files": self.files}),
                content_type="application/json",
                if_generation_match=self.generation,
            )
        except PreconditionFailed as exc:
            raise JobConflictError("This job changed; reload it before trying again.") from exc
        self.generation = int(blob.generation)

    def read_text(self, raw_path: str) -> str:
        key = self._contained(raw_path).name
        if key not in self.files:
            raise FileNotFoundError(key)
        return self.files[key]

    def write_text(self, raw_path: str, text: str) -> None:
        self.files[self._contained(raw_path).name] = text

    def remove_file(self, raw_path: str) -> None:
        self.files.pop(self._contained(raw_path).name, None)

    def delete(self, job: FileJob) -> None:
        try:
            self.bucket.blob(self._key(job.id)).delete(if_generation_match=self.generation)
        except NotFound:
            pass
        except PreconditionFailed as exc:
            raise JobConflictError("This job changed; reload it before trying again.") from exc

    def cleanup_expired(self) -> int:
        # GCS lifecycle removes objects; get() enforces the precise access deadline.
        return 0
