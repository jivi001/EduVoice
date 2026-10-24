from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings
from .db import Base, engine
from .routers import (
    admin,
    analytics,
    auth,
    bureaus,
    cases,
    clock,
    credentials,
    feedback,
    ingest,
    institutions,
    notifications,
    overlaps,
    student,
    teacher,
)

_config_error: str | None = None

try:
    if settings.is_production:
        settings.check_production()
    else:
        try:
            Base.metadata.create_all(engine)
        except Exception as _e:
            # Handle read-only filesystems in serverless preview environments
            pass
except Exception as _exc:
    _config_error = str(_exc)


class PathPrefixMiddleware:
    """Strips Vercel function rewrite prefixes like /api/index or /api/index.py from ASGI scope."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            for prefix in ("/api/index.py", "/api/index"):
                if path.startswith(prefix):
                    new_path = path[len(prefix):]
                    scope["path"] = new_path if new_path.startswith("/") else "/" + new_path
                    break
        await self.app(scope, receive, send)


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if _config_error and request.url.path not in ("/health", "/api/health", "/", "/docs", "/openapi.json"):
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Backend configuration error",
                    "error": _config_error,
                },
            )
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Cache-Control"] = "no-store"
        if settings.is_production:
            resp.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return resp


app = FastAPI(
    title="EduVoice API (SIH26264)",
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",
    redirect_slashes=False,
)
app.add_middleware(PathPrefixMiddleware)
app.add_middleware(SecurityHeaders)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "PUT", "OPTIONS"],
    allow_headers=["Content-Type"],
)

for r in (
    auth.router,
    institutions.router,
    bureaus.router,
    cases.router,
    overlaps.router,
    ingest.router,
    analytics.router,
    notifications.router,
    clock.router,
    credentials.router,
    student.router,
    feedback.router,
    teacher.router,
    admin.router,
):
    app.include_router(r)


@app.get("/")
def root():
    return {
        "name": "EduVoice API (SIH26264)",
        "status": "ok",
        "health": "/health",
    }


@app.get("/health")
@app.get("/api/health")
def health():
    if _config_error:
        return JSONResponse(
            status_code=500,
            content={
                "status": "misconfigured",
                "error": _config_error,
                "hint": "Ensure production environment variables (DATABASE_URL, JWT_SECRET, SIGNING_KEY_PEM_B64, COOKIE_SECURE) are set in Vercel project settings.",
            },
        )
    return {"status": "ok"}
