import pytest

from app.core.config import Settings, get_settings
from app.core.demo_guard import DemoGuard, DemoLimitError
from app.main import app


def test_processing_limits_reset_and_reads_remain_available():
    now = [100.0]
    guard = DemoGuard(Settings(), clock=lambda: now[0])
    for _ in range(5):
        guard.acquire("client", True)
        guard.release(True)
    with pytest.raises(DemoLimitError) as error:
        guard.acquire("client", True)
    assert error.value.status == 429
    assert error.value.retry_after == 500
    guard.acquire("client", False)
    now[0] = 600.0
    guard.acquire("client", True)
    guard.release(True)


def test_global_limit_cannot_be_bypassed_by_changing_client():
    guard = DemoGuard(Settings(), clock=lambda: 100.0)
    for i in range(30):
        guard.acquire(str(i), True)
        guard.release(True)
    with pytest.raises(DemoLimitError) as error:
        guard.acquire("new-client", True)
    assert error.value.status == 429


def test_only_one_processing_request_and_release_restores_capacity():
    guard = DemoGuard(Settings())
    guard.acquire("a", True)
    with pytest.raises(DemoLimitError) as error:
        guard.acquire("b", True)
    assert error.value.status == 503
    guard.release(True)
    guard.acquire("b", True)
    guard.release(True)


def test_read_limit():
    guard = DemoGuard(Settings(demo_reads_per_client=2))
    guard.acquire("a", False)
    guard.acquire("a", False)
    with pytest.raises(DemoLimitError) as error:
        guard.acquire("a", False)
    assert error.value.status == 429


def test_rate_limit_is_cors_visible_and_forwarded_headers_do_not_bypass(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_limits_enabled", True)
    monkeypatch.setattr(app.state, "demo_guard", DemoGuard(settings))
    origin = settings.cors_origin_list[0]
    for i in range(5):
        response = client.post(
            "/api/v1/files",
            headers={"Origin": origin, "X-Forwarded-For": f"198.51.100.{i}"},
        )
        assert response.status_code == 422
    response = client.post("/api/v1/files", headers={"Origin": origin})
    assert response.status_code == 429
    assert response.headers["access-control-allow-origin"] == origin
    assert int(response.headers["retry-after"]) > 0
    assert response.json()["error"]["code"] == "rate_limited"
    assert client.delete("/api/v1/files/missing").status_code == 204
