from pathlib import Path

from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures"


def test_complete_upload_transform_preview_download_delete_workflow(client: TestClient) -> None:
    uploaded = client.post(
        "/api/v1/files",
        files={
            "file": ("captions.srt", (FIXTURES / "sample.srt").read_bytes(), "application/x-subrip")
        },
    )
    assert uploaded.status_code == 201
    job = uploaded.json()
    assert job["analysis"]["caption_count"] == 2
    assert job["analysis"]["issue_count"] > 0

    file_id = job["id"]
    assert client.get(f"/api/v1/files/{file_id}").status_code == 200
    transformed = client.post(
        f"/api/v1/files/{file_id}/transform",
        json={"preset": "safe", "output_format": "vtt", "resolve_overlaps": True},
    )
    assert transformed.status_code == 200
    assert transformed.json()["output_format"] == "vtt"

    preview = client.get(f"/api/v1/files/{file_id}/preview")
    assert preview.status_code == 200
    assert preview.json()["transformed"] is not None
    assert preview.json()["changes"]

    downloaded = client.get(f"/api/v1/files/{file_id}/download")
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"WEBVTT")
    assert "captions-corrected.vtt" in downloaded.headers["content-disposition"]

    assert client.delete(f"/api/v1/files/{file_id}").status_code == 204
    assert client.delete(f"/api/v1/files/{file_id}").status_code == 204
    assert client.get(f"/api/v1/files/{file_id}").status_code == 404


def test_security_rejections_and_html_is_plain_text(client: TestClient) -> None:
    traversal = client.post(
        "/api/v1/files",
        files={"file": ("../../unsafe.srt", b"1\n00:00:00,000 --> 00:00:01,000\n<b>text</b>\n")},
    )
    assert traversal.status_code == 201
    payload = traversal.json()
    assert payload["filename"] == "unsafe.srt"
    preview = client.get(f"/api/v1/files/{payload['id']}/preview").json()
    assert preview["original"][0]["text"] == "<b>text</b>"

    oversized = client.post("/api/v1/files", files={"file": ("large.srt", b"a" * 1025)})
    assert oversized.status_code == 422
    assert oversized.json()["error"]["code"] == "invalid_subtitle"
    binary = client.post("/api/v1/files", files={"file": ("bad.srt", b"1\x00bad")})
    assert binary.status_code == 422
    unsupported = client.post("/api/v1/files", files={"file": ("bad.txt", b"hello")})
    assert unsupported.status_code == 422


def test_download_requires_transformation(client: TestClient) -> None:
    response = client.post(
        "/api/v1/files", files={"file": ("captions.vtt", (FIXTURES / "sample.vtt").read_bytes())}
    )
    file_id = response.json()["id"]
    download = client.get(f"/api/v1/files/{file_id}/download")
    assert download.status_code == 409
    assert download.json()["error"]["code"] == "not_transformed"
