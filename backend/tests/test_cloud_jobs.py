import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from google.api_core.exceptions import NotFound, PreconditionFailed

from app.core.config import Settings
from app.schemas import TransformRequest
from app.services.cloud_jobs import CloudJobService, JobConflictError
from app.services.jobs import JobNotFoundError

SOURCE = b"1\n00:00:01,000 --> 00:00:03,000\nHello world\n"


class Bucket:
    def __init__(self):
        self.objects = {}
        self.counter = 0

    def blob(self, key):
        return Blob(self, key)


class Blob:
    def __init__(self, bucket, key):
        self.bucket = bucket
        self.key = key
        self.generation = None
        self.custom_time = None

    def download_as_bytes(self):
        if self.key not in self.bucket.objects:
            raise NotFound("missing")
        self.generation, payload = self.bucket.objects[self.key]
        return payload.encode()

    def upload_from_string(self, payload, *, content_type, if_generation_match):
        current = self.bucket.objects.get(self.key, (0, None))[0]
        if current != if_generation_match:
            raise PreconditionFailed("changed")
        assert content_type == "application/json"
        assert self.custom_time is not None
        self.bucket.counter += 1
        self.generation = self.bucket.counter
        self.bucket.objects[self.key] = (self.generation, payload)

    def delete(self, *, if_generation_match):
        current = self.bucket.objects.get(self.key)
        if current is None:
            raise NotFound("missing")
        if current[0] != if_generation_match:
            raise PreconditionFailed("changed")
        del self.bucket.objects[self.key]


@pytest.fixture
def cloud(monkeypatch):
    bucket = Bucket()
    monkeypatch.setattr(
        "app.services.cloud_jobs.storage.Client",
        lambda: SimpleNamespace(bucket=lambda _: bucket),
    )
    return lambda: CloudJobService(Settings(storage_bucket="test-bucket")), bucket


def test_complete_job_survives_new_service_instances(cloud):
    factory, bucket = cloud
    job = factory().create("captions.srt", SOURCE)
    service = factory()
    loaded = service.get(job.id)
    assert service.source_document(loaded).cues[0].text == "Hello world"
    service.apply_transform(loaded, TransformRequest(preset="safe", output_format="vtt"))
    restarted = factory()
    loaded = restarted.get(job.id)
    assert restarted.generated_document(loaded).format.value == "vtt"
    assert restarted.read_text(loaded.generated_path).startswith("WEBVTT")
    restarted.delete(loaded)
    assert not bucket.objects
    with pytest.raises(JobNotFoundError):
        factory().get(job.id)


def test_concurrent_transform_cannot_overwrite_or_resurrect_deleted_job(cloud):
    factory, _ = cloud
    job = factory().create("captions.srt", SOURCE)
    first, second = factory(), factory()
    a, b = first.get(job.id), second.get(job.id)
    first.apply_transform(a, TransformRequest(preset="safe"))
    with pytest.raises(JobConflictError):
        second.apply_transform(b, TransformRequest(preset="safe"))
    second.get(job.id)
    first.delete(a)
    with pytest.raises(JobConflictError):
        second.apply_transform(b, TransformRequest(preset="safe"))


def test_expired_jobs_are_inaccessible_and_ids_are_validated(cloud):
    factory, bucket = cloud
    job = factory().create("captions.srt", SOURCE)
    key = f"jobs/{job.id}.json"
    generation, content = bucket.objects[key]
    payload = json.loads(content)
    payload["job"]["created_at"] = (datetime.now(UTC) - timedelta(hours=25)).isoformat()
    bucket.objects[key] = generation, json.dumps(payload)
    with pytest.raises(JobNotFoundError, match="expired"):
        factory().get(job.id)
    with pytest.raises(JobNotFoundError):
        factory().get("../other-job")


def test_cloud_storage_through_api_requests(cloud, client):
    from app.api.routes import service_dependency
    from app.main import app

    factory, bucket = cloud
    app.dependency_overrides[service_dependency] = factory
    try:
        uploaded = client.post("/api/v1/files", files={"file": ("captions.srt", SOURCE)})
        assert uploaded.status_code == 201
        assert uploaded.headers["cache-control"] == "no-store"
        file_id = uploaded.json()["id"]
        root = f"/api/v1/files/{file_id}"
        assert (
            client.post(
                root + "/transform", json={"preset": "safe", "output_format": "vtt"}
            ).status_code
            == 200
        )
        assert client.get(root + "/preview").json()["transformed"][0]["text"] == "Hello world"
        download = client.get(root + "/download")
        assert download.status_code == 200
        assert download.text.startswith("WEBVTT")
        assert "captions-corrected.vtt" in download.headers["content-disposition"]
        assert client.delete(root).status_code == 204
        assert client.delete(root).status_code == 204
        assert client.get(root).status_code == 404
        assert not bucket.objects
    finally:
        app.dependency_overrides.clear()
