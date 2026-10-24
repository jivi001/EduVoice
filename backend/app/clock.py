from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

APP_TIMEZONE = ZoneInfo("Asia/Kolkata")

_clock_override: datetime | None = None
_time_offset: timedelta = timedelta(0)


def get_now() -> datetime:
    """Returns current UTC datetime, honoring any test or demo clock override/offset."""
    if _clock_override is not None:
        return _clock_override
    now_utc = datetime.now(timezone.utc)
    return now_utc + _time_offset


def get_current_date() -> date:
    """Returns current date in application timezone (Asia/Kolkata)."""
    now_utc = get_now()
    return now_utc.astimezone(APP_TIMEZONE).date()


def get_current_year() -> int:
    """Returns current year in application timezone."""
    return get_current_date().year


def to_app_tz(dt: datetime) -> datetime:
    """Convert UTC datetime to application timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(APP_TIMEZONE)


def ensure_utc(dt: datetime | None) -> datetime | None:
    """Ensures datetime is offset-aware UTC for safe comparisons."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def set_fixed_time(dt: datetime | None) -> None:
    """Set a fixed point in time for tests."""
    global _clock_override, _time_offset
    if dt is not None and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    _clock_override = dt
    _time_offset = timedelta(0)


def advance_time(days: int = 0, hours: int = 0) -> datetime:
    """Advance simulated clock by days/hours for demonstration purposes."""
    global _time_offset, _clock_override
    delta = timedelta(days=days, hours=hours)
    if _clock_override is not None:
        _clock_override += delta
        return _clock_override
    _time_offset += delta
    return get_now()


def reset_clock() -> None:
    """Reset clock to system time."""
    global _clock_override, _time_offset
    _clock_override = None
    _time_offset = timedelta(0)
