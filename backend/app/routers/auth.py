import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

import urllib.parse

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import google_oauth, mail
from ..config import settings
from ..db import get_db
from ..models import EmailToken, Teacher, User
from ..security import (COOKIE_NAME, create_session_token, get_current_user, hash_password, rate_limit,
                        verify_password)

router = APIRouter(prefix="/auth", tags=["auth"])
_DUMMY_HASH = hash_password("dummy-password")  # keeps login timing similar for unknown users


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


MAX_FAILED = 5
LOCK_MINUTES = 15


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC, consistent across SQLite/Postgres


@router.post("/login", dependencies=[Depends(rate_limit("login", 10, 60))])
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == body.username))
    if user and user.locked_until and user.locked_until > _now():
        raise HTTPException(429, f"Too many failed attempts. Try again in {LOCK_MINUTES} minutes.")
    ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if user and ok and user.status != "active":
        text = {
            "pending_verification": "Check your inbox and verify your email before signing in.",
            "pending_approval": "Your account is waiting for administrator approval.",
            "rejected": "This account was not approved. Contact your administrator.",
        }.get(user.status, "This account isn't active yet.")
        raise HTTPException(403, text)
    if not user or not ok:
        if user:
            user.failed_logins = (user.failed_logins or 0) + 1
            if user.failed_logins >= MAX_FAILED:
                user.locked_until = _now() + timedelta(minutes=LOCK_MINUTES)
                user.failed_logins = 0
            db.commit()
        raise HTTPException(401, "Username or password is incorrect")
    if user.failed_logins or user.locked_until:
        user.failed_logins, user.locked_until = 0, None
        db.commit()
    response.set_cookie(
        COOKIE_NAME, create_session_token(user), httponly=True, samesite="lax",
        secure=settings.cookie_secure, max_age=settings.jwt_expire_minutes * 60, path="/",
    )
    return {"name": user.name, "role": user.role}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "name": user.name,
        "username": user.username,
        "role": user.role,
        "bureaus": [{"id": a.bureau.id, "code": a.bureau.code, "name": a.bureau.name} for a in user.bureau_assignments if a.bureau],
        "regions": [a.region for a in user.region_assignments],
        "must_change_password": user.must_change_password,
    }


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


@router.post("/change-password", dependencies=[Depends(rate_limit("pw", 10, 60))])
def change_password(body: ChangePasswordIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Your current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    db.commit()
    return {"ok": True}


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TOKEN_HOURS = 24


class SignupIn(BaseModel):
    email: str
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=10, max_length=128)
    role: str  # "student" or "teacher"


def _issue_token(db: Session, user: User, purpose: str) -> str:
    raw = secrets.token_urlsafe(32)
    db.add(EmailToken(token_hash=hashlib.sha256(raw.encode()).hexdigest(), user_id=user.id,
                       purpose=purpose, expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=TOKEN_HOURS)))
    return raw


@router.post("/signup", status_code=201, dependencies=[Depends(rate_limit("signup", 10, 60))])
def signup(body: SignupIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Enter a valid email address")
    if body.role not in ("student", "teacher"):
        raise HTTPException(400, "Choose whether you're a student or a teacher")
    if settings.allowed_domains and email.split("@")[-1] not in settings.allowed_domains:
        raise HTTPException(400, "This email domain isn't accepted here. Use your college email.")
    if db.scalar(select(User.id).where((User.username == email) | (User.email == email))):
        raise HTTPException(409, "An account with this email already exists. Try signing in instead.")

    user = User(username=email, email=email, name=body.name.strip(), role=body.role,
                password_hash=hash_password(body.password), status="pending_verification")
    db.add(user)
    db.flush()
    raw_token = _issue_token(db, user, "verify_email")
    db.commit()

    link = f"{settings.frontend_origin}/verify?token={raw_token}"
    mail.verify_email_mail(email, link)
    return {"ok": True, "message": "Check your email for a verification link."}


class VerifyIn(BaseModel):
    token: str


@router.post("/verify-email")
def verify_email(body: VerifyIn, db: Session = Depends(get_db)):
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    rec = db.get(EmailToken, token_hash)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if not rec or rec.purpose != "verify_email" or rec.expires_at < now:
        raise HTTPException(400, "This verification link is invalid or has expired.")
    user = db.get(User, rec.user_id)
    if not user or user.status != "pending_verification":
        raise HTTPException(400, "This verification link has already been used.")
    user.email_verified = True
    user.status = "pending_approval"
    db.delete(rec)
    db.commit()

    if settings.admin_notify_email:
        mail.pending_approval_admin_mail(settings.admin_notify_email, user.name, user.email or "", user.role)
    return {"ok": True, "message": "Email verified. An administrator needs to approve your account before you can sign in."}


GOOGLE_STATE_COOKIE = "g_oauth_state"


@router.get("/google/enabled")
def google_enabled():
    return {"enabled": settings.google_enabled}


@router.get("/google/start")
def google_start(response: Response, role: str = ""):
    if not settings.google_enabled:
        raise HTTPException(404, "Google sign-in isn't set up here")
    if role and role not in ("student", "teacher"):
        raise HTTPException(400, "Invalid role")
    state = secrets.token_urlsafe(24)
    redirect = RedirectResponse(google_oauth.authorize_url(state))
    redirect.set_cookie(GOOGLE_STATE_COOKIE, f"{state}:{role}", httponly=True, samesite="lax",
                         secure=settings.cookie_secure, max_age=300, path="/auth/google")
    return redirect


def _to_login(error: str) -> RedirectResponse:
    return RedirectResponse(f"{settings.frontend_origin}/?google_error={urllib.parse.quote(error)}")


@router.get("/google/callback")
def google_callback(request: Request, code: str = "", state: str = "", db: Session = Depends(get_db)):
    cookie = request.cookies.get(GOOGLE_STATE_COOKIE, "")
    saved_state, _, role = cookie.partition(":")
    resp_clear = {"key": GOOGLE_STATE_COOKIE, "path": "/auth/google"}
    if not code or not state or not saved_state or state != saved_state:
        r = _to_login("That sign-in attempt expired or was tampered with. Try again.")
        r.delete_cookie(**resp_clear)
        return r
    try:
        profile = google_oauth.exchange_code(code)
    except google_oauth.GoogleAuthError as e:
        r = _to_login(str(e))
        r.delete_cookie(**resp_clear)
        return r

    email = profile["email"]
    if settings.allowed_domains and email.split("@")[-1] not in settings.allowed_domains:
        r = _to_login("This email domain isn't accepted here. Use your college email.")
        r.delete_cookie(**resp_clear)
        return r

    user = db.scalar(select(User).where((User.username == email) | (User.email == email)))
    if user:
        if user.status != "active":
            text = {
                "pending_verification": "Finish verifying your email, then try Google sign-in again.",
                "pending_approval": "Your account is waiting for administrator approval.",
                "rejected": "This account was not approved. Contact your administrator.",
            }.get(user.status, "This account isn't active yet.")
            r = _to_login(text)
            r.delete_cookie(**resp_clear)
            return r
        # Hand off to the frontend's own domain to set the session cookie there (this
        # request landed directly on the backend, via Google's redirect — the cookie must
        # be set through the frontend's /api proxy instead, or the rest of the app can't see it).
        raw_code = secrets.token_urlsafe(32)
        db.add(EmailToken(token_hash=hashlib.sha256(raw_code.encode()).hexdigest(), user_id=user.id,
                           purpose="google_login", expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=2)))
        db.commit()
        r = RedirectResponse(f"{settings.frontend_origin}/api/auth/google/finish?code={raw_code}")
        r.delete_cookie(**resp_clear)
        return r

    if role not in ("student", "teacher"):
        r = _to_login("New here? Pick Student or Teacher on the sign-up page first.")
        r.delete_cookie(**resp_clear)
        return r
    new_user = User(username=email, email=email, name=profile["name"], role=role,
                     password_hash=hash_password(secrets.token_urlsafe(32)),  # unusable random password; Google-only account
                     email_verified=True, status="pending_approval")
    db.add(new_user)
    db.commit()
    if settings.admin_notify_email:
        mail.pending_approval_admin_mail(settings.admin_notify_email, new_user.name, email, role)
    r = RedirectResponse(f"{settings.frontend_origin}/?google_pending=1")
    r.delete_cookie(**resp_clear)
    return r


@router.get("/google/finish", dependencies=[Depends(rate_limit("google_finish", 20, 60))])
def google_finish(code: str, db: Session = Depends(get_db)):
    """Reached through the frontend's /api proxy, so the session cookie it sets lands on
    the frontend's own domain — see the handoff comment in google_callback above."""
    token_hash = hashlib.sha256(code.encode()).hexdigest()
    rec = db.get(EmailToken, token_hash)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if not rec or rec.purpose != "google_login" or rec.expires_at < now:
        return _to_login("That sign-in link expired. Try Google sign-in again.")
    user = db.get(User, rec.user_id)
    db.delete(rec)
    db.commit()
    if not user or user.status != "active":
        return _to_login("This account isn't active. Contact your administrator.")
    r = RedirectResponse(settings.frontend_origin)
    r.set_cookie(COOKIE_NAME, create_session_token(user), httponly=True, samesite="lax",
                  secure=settings.cookie_secure, max_age=settings.jwt_expire_minutes * 60, path="/")
    return r
