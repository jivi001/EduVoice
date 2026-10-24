from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

if settings.is_production:
    settings.check_production()  # refuse to start with unsafe settings
else:
    Base.metadata.create_all(engine)  # convenience for local dev; production uses `bootstrap init`


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Cache-Control"] = "no-store"
        if settings.is_production:
            resp.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return resp


app = FastAPI(
    title="AICTE Grievance & Case Monitoring API (SIH26264)",
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",
)
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


@app.get("/health")
def health():
    return {"status": "ok"}
