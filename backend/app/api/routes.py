from __future__ import annotations

import json
from contextlib import suppress
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.database import get_db
from app.db.models import FileJob
from app.schemas import JobResponse, PreviewResponse, TransformRequest, TransformResponse
from app.services.cloud_jobs import CloudJobService
from app.services.jobs import JobNotFoundError, JobService, report, safe_download_name
from sublynt_core.models import Cue, SubtitleDocument

router = APIRouter(prefix="/api/v1")


def service_dependency(
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> JobService:
    if settings.storage_bucket:
        return CloudJobService(settings)
    return JobService(session, settings)


Service = Annotated[JobService, Depends(service_dependency)]


def _job(service: JobService, file_id: str) -> FileJob:
    try:
        return service.get(file_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail={"code": "not_found", "message": str(exc)}
        ) from exc


def _job_response(service: JobService, job: FileJob) -> JobResponse:
    source = service.source_document(job)
    transformed = service.generated_document(job)
    return JobResponse(
        id=job.id,
        filename=job.original_name,
        created_at=job.created_at.isoformat(),
        analysis=report(source),
        transformed_analysis=report(transformed) if transformed else None,
        has_transformation=transformed is not None,
        output_format=job.output_format,
    )


@router.post(
    "/files",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and analyze a subtitle file",
)
async def upload_file(
    service: Service,
    file: Annotated[UploadFile, File(description="An UTF-8 SRT or WebVTT file")],
) -> JobResponse:
    data = await file.read(service.settings.max_upload_bytes + 1)
    try:
        job = service.create(file.filename or "upload", data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_subtitle", "message": str(exc)},
        ) from exc
    return _job_response(service, job)


@router.get("/files/{file_id}", response_model=JobResponse, summary="Get job analysis")
def get_file(file_id: str, service: Service) -> JobResponse:
    return _job_response(service, _job(service, file_id))


@router.post(
    "/files/{file_id}/transform",
    response_model=TransformResponse,
    summary="Apply deterministic subtitle transformations",
)
def transform_file(file_id: str, request: TransformRequest, service: Service) -> TransformResponse:
    job = _job(service, file_id)
    transformed, changes = service.apply_transform(job, request)
    return TransformResponse(
        file_id=job.id,
        output_format=transformed.format.value,
        change_count=len(changes),
        changes=changes,
        analysis=report(transformed, request.thresholds),
    )


def _cues(document: SubtitleDocument) -> list[dict[str, object]]:
    return [_cue(cue, index) for index, cue in enumerate(document.cues, start=1)]


def _cue(cue: Cue, index: int) -> dict[str, object]:
    return {
        "index": index,
        "identifier": cue.identifier,
        "start_ms": cue.start_ms,
        "end_ms": cue.end_ms,
        "text": cue.text,
        "lines": cue.lines,
        "settings": cue.settings,
    }


@router.get(
    "/files/{file_id}/preview",
    response_model=PreviewResponse,
    summary="Preview original and result",
)
def preview_file(file_id: str, service: Service) -> PreviewResponse:
    job = _job(service, file_id)
    source = service.source_document(job)
    transformed = service.generated_document(job)
    return PreviewResponse(
        original=_cues(source),
        transformed=_cues(transformed) if transformed else None,
        changes=json.loads(job.changes_json),
    )


@router.get("/files/{file_id}/download", summary="Download the corrected subtitle")
def download_file(file_id: str, service: Service) -> Response:
    job = _job(service, file_id)
    document = service.generated_document(job)
    if document is None or not job.generated_path or not job.output_format:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "not_transformed",
                "message": "Apply a transformation before downloading.",
            },
        )
    filename = quote(safe_download_name(job.original_name, job.output_format))
    return Response(
        service.read_text(job.generated_path),
        media_type="text/vtt" if job.output_format == "vtt" else "application/x-subrip",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.delete(
    "/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a subtitle job"
)
def delete_file(file_id: str, service: Service) -> Response:
    with suppress(JobNotFoundError):
        service.delete(service.get(file_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
