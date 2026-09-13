from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import FileJob
from app.schemas import Thresholds, TransformRequest
from sublynt_core import (
    AnalysisConfig,
    SubtitleDocument,
    SubtitleFormat,
    TransformConfig,
    analyze,
    parse_subtitle,
    serialize_subtitle,
    transform,
)
from sublynt_core.parsers import decode_subtitle


class JobNotFoundError(LookupError):
    pass


def safe_download_name(name: str, output_format: str) -> str:
    stem = Path(name.replace("\\", "/")).name.rsplit(".", 1)[0]
    stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", stem).strip(" ._")[:100] or "subtitles"
    return f"{stem}-corrected.{output_format}"


class JobService:
    def __init__(self, session: Session, settings: Settings):
        self.session = session
        self.settings = settings
        self.root = settings.data_dir.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self, filename: str, data: bytes) -> FileJob:
        suffix = Path(filename).suffix.lower()
        if suffix not in {".srt", ".vtt"}:
            raise ValueError("Only .srt and .vtt files are supported.")
        if len(data) > self.settings.max_upload_bytes:
            raise ValueError(
                f"File exceeds the {self.settings.max_upload_bytes // (1024 * 1024)} MB limit."
            )
        text = decode_subtitle(data)
        fmt = SubtitleFormat(suffix[1:])
        parse_subtitle(text, fmt)
        file_id = str(uuid4())
        path = self.root / f"{file_id}.source.{fmt.value}"
        self.write_text(str(path), text)
        job = FileJob(
            id=file_id,
            original_name=Path(filename.replace("\\", "/")).name[:255] or f"upload.{fmt.value}",
            source_format=fmt.value,
            source_path=str(path),
            created_at=datetime.now(UTC),
            changes_json="[]",
        )
        self.save(job)
        return job

    def save(self, job: FileJob) -> None:
        self.session.add(job)
        self.session.commit()

    def read_text(self, raw_path: str) -> str:
        return self._contained(raw_path).read_text(encoding="utf-8")

    def write_text(self, raw_path: str, text: str) -> None:
        self._contained(raw_path).write_text(text, encoding="utf-8", newline="\n")

    def remove_file(self, raw_path: str) -> None:
        self._contained(raw_path).unlink(missing_ok=True)

    def get(self, file_id: str) -> FileJob:
        job = self.session.get(FileJob, file_id)
        if job is None:
            raise JobNotFoundError("Subtitle job was not found.")
        return job

    def source_document(self, job: FileJob) -> SubtitleDocument:
        return parse_subtitle(self.read_text(job.source_path), SubtitleFormat(job.source_format))

    def generated_document(self, job: FileJob) -> SubtitleDocument | None:
        if not job.generated_path or not job.output_format:
            return None
        try:
            text = self.read_text(job.generated_path)
        except FileNotFoundError:
            return None
        return parse_subtitle(text, SubtitleFormat(job.output_format))

    def apply_transform(
        self, job: FileJob, request: TransformRequest
    ) -> tuple[SubtitleDocument, list[dict[str, object]]]:
        source = self.source_document(job)
        thresholds = _analysis_config(request.thresholds)
        options = TransformConfig(
            output_format=SubtitleFormat(request.output_format)
            if request.output_format
            else source.format,
            shift_ms=request.shift_ms,
            speed_factor=request.speed_factor,
            prevent_negative=request.prevent_negative,
            sort_cues=request.sort_cues or request.safe_enabled,
            renumber_srt=request.renumber_srt or request.safe_enabled,
            remove_empty=request.remove_empty or request.safe_enabled,
            remove_duplicates=request.remove_duplicates,
            repair_invalid_timing=request.safe_enabled,
            enforce_gap=request.enforce_gap,
            resolve_overlaps=request.resolve_overlaps,
            enforce_durations=request.enforce_durations,
            split_long=request.split_long,
            merge_short=request.merge_short,
            merge_max_gap_ms=request.merge_max_gap_ms,
            thresholds=thresholds,
        )
        transformed, raw_changes = transform(source, options)
        serialized = serialize_subtitle(transformed)
        # Round-trip validation is mandatory before replacing a generated artifact.
        parse_subtitle(serialized, transformed.format)
        path = self.root / f"{job.id}.generated.{transformed.format.value}"
        self.write_text(str(path), serialized)
        if job.generated_path and job.generated_path != str(path):
            self.remove_file(job.generated_path)
        changes = [change.as_dict() for change in raw_changes]
        job.generated_path = str(path)
        job.output_format = transformed.format.value
        job.changes_json = json.dumps(changes)
        self.save(job)
        return transformed, changes

    def delete(self, job: FileJob) -> None:
        for raw_path in (job.source_path, job.generated_path):
            if raw_path:
                self.remove_file(raw_path)
        self.session.delete(job)
        self.session.commit()

    def cleanup_expired(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(hours=self.settings.retention_hours)
        jobs = list(self.session.scalars(select(FileJob).where(FileJob.created_at < cutoff)))
        for job in jobs:
            self.delete(job)
        return len(jobs)

    def _contained(self, raw_path: str) -> Path:
        path = Path(raw_path).resolve()
        if path.parent != self.root:
            raise ValueError("Stored file path is outside the application data directory.")
        return path


def _analysis_config(value: Thresholds) -> AnalysisConfig:
    return AnalysisConfig(**value.model_dump())


def report(document: SubtitleDocument, thresholds: Thresholds | None = None) -> dict[str, object]:
    return analyze(document, _analysis_config(thresholds or Thresholds()))
