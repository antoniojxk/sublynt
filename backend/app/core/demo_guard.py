"""In-process demo limits, matching InvoiceParse's single-instance guard."""

from collections.abc import Callable
from threading import Lock
from time import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import Settings, get_settings


class DemoLimitError(Exception):
    def __init__(self, status: int, code: str, message: str, retry_after: int):
        self.status = status
        self.code = code
        self.message = message
        self.retry_after = retry_after


class DemoGuard:
    def __init__(self, settings: Settings, clock: Callable[[], float] = time):
        self.settings = settings
        self.clock = clock
        self.lock = Lock()
        self.window = -1
        self.counts: dict[tuple[bool, str], int] = {}
        self.totals: dict[bool, int] = {True: 0, False: 0}
        self.processing = False

    def acquire(self, client: str, processing: bool) -> None:
        with self.lock:
            if processing and self.processing:
                raise DemoLimitError(
                    503, "demo_busy", "Another subtitle is being processed. Try again shortly.", 5
                )
            now = int(self.clock())
            window = now // self.settings.demo_window_seconds
            if window != self.window:
                self.window = window
                self.counts.clear()
                self.totals = {True: 0, False: 0}
            client_limit = (
                self.settings.demo_processing_per_client
                if processing
                else self.settings.demo_reads_per_client
            )
            global_limit = (
                self.settings.demo_processing_global
                if processing
                else self.settings.demo_reads_global
            )
            key = (processing, client[:64])
            if self.counts.get(key, 0) >= client_limit or self.totals[processing] >= global_limit:
                raise DemoLimitError(
                    429,
                    "rate_limited",
                    "The public demo request limit has been reached. Please try again later.",
                    self.settings.demo_window_seconds - now % self.settings.demo_window_seconds,
                )
            self.counts[key] = self.counts.get(key, 0) + 1
            self.totals[processing] += 1
            if processing:
                self.processing = True

    def release(self, processing: bool) -> None:
        if processing:
            with self.lock:
                self.processing = False


class DemoRequestMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_settings()
        if (
            not settings.demo_limits_enabled
            or not request.url.path.startswith("/api/v1/")
            or request.method == "OPTIONS"
        ):
            return await call_next(request)
        # Use the server-provided peer, never arbitrary client-supplied IP headers.
        client = request.client.host if request.client else "unknown"
        processing = request.method == "POST"
        guard: DemoGuard = request.app.state.demo_guard
        try:
            guard.acquire(client, processing)
        except DemoLimitError as exc:
            return JSONResponse(
                status_code=exc.status,
                content={"error": {"code": exc.code, "message": exc.message}},
                headers={"Retry-After": str(exc.retry_after), "Cache-Control": "no-store"},
            )
        try:
            return await call_next(request)
        finally:
            guard.release(processing)
