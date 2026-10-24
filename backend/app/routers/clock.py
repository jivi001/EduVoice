"""
Time Machine / Clock Router for deterministic SLA, deadline, and overdue testing.
"""
from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..clock import advance_time, get_current_date, get_now, reset_clock, to_app_tz
from ..models import User
from ..security import get_current_user

router = APIRouter(prefix="/clock", tags=["clock"])


class AdvanceClockIn(BaseModel):
    days: int = 0
    hours: int = 0


@router.get("")
def get_clock_status(user: User = Depends(get_current_user)):
    now_utc = get_now()
    now_local = to_app_tz(now_utc)
    return {
        "current_utc": now_utc.isoformat(),
        "current_local": now_local.isoformat(),
        "current_date": get_current_date().isoformat(),
        "timezone": "Asia/Kolkata",
    }


@router.post("/advance")
def advance_simulated_clock(body: AdvanceClockIn, user: User = Depends(get_current_user)):
    now_utc = advance_time(days=body.days, hours=body.hours)
    now_local = to_app_tz(now_utc)
    return {
        "message": f"Clock advanced by {body.days} days, {body.hours} hours.",
        "new_utc": now_utc.isoformat(),
        "new_local": now_local.isoformat(),
        "new_date": get_current_date().isoformat(),
    }


@router.post("/reset")
def reset_simulated_clock(user: User = Depends(get_current_user)):
    reset_clock()
    now_utc = get_now()
    now_local = to_app_tz(now_utc)
    return {
        "message": "Clock reset to system time.",
        "current_utc": now_utc.isoformat(),
        "current_local": now_local.isoformat(),
    }
