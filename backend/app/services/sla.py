"""
SLA and Deadline calculations for AICTE complaint tracking.

Deadline precedence:
1. Valid, trusted imported external due date takes precedence.
2. Otherwise, calculated from active SLAConfig (calendar days from received_date).
3. If neither exists, classified as NO_SLA_CONFIGURED.
"""
from datetime import date, datetime, time, timedelta, timezone
from sqlalchemy.orm import Session

from ..clock import APP_TIMEZONE, ensure_utc, get_now
from ..models import ComplaintCase, SLAConfig

ACTIVE_STATUSES = {"Pending", "Under Process", "Transferred", "Escalated"}
TERMINAL_STATUSES = {"Disposed"}


def calculate_effective_deadline(
    db: Session,
    received_date: date,
    bureau_id: int,
    category: str,
    imported_due_date: date | None = None,
    imported_due_date_trusted: bool = False,
) -> tuple[datetime | None, str]:
    """
    Returns (effective_deadline_utc, initial_sla_status).
    Deadlines end at 23:59:59.999999 of the calculated date in Asia/Kolkata.
    """
    # 1. Trusted external due date takes precedence
    if imported_due_date and imported_due_date_trusted:
        dt_local = datetime.combine(imported_due_date, time(23, 59, 59, 999999), tzinfo=APP_TIMEZONE)
        deadline_utc = dt_local.astimezone(timezone.utc)
        return deadline_utc, "ON_TRACK"

    # 2. Configured SLA rule (specific category/bureau or fallback)
    rule = (
        db.query(SLAConfig)
        .filter(
            SLAConfig.is_active == True,
            (SLAConfig.bureau_id == bureau_id) | (SLAConfig.bureau_id == None),
            (SLAConfig.category == category) | (SLAConfig.category == None),
        )
        .order_by(
            SLAConfig.category.isnot(None).desc(),
            SLAConfig.bureau_id.isnot(None).desc(),
        )
        .first()
    )

    if rule:
        deadline_date = received_date + timedelta(days=rule.max_calendar_days)
        dt_local = datetime.combine(deadline_date, time(23, 59, 59, 999999), tzinfo=APP_TIMEZONE)
        deadline_utc = dt_local.astimezone(timezone.utc)
        return deadline_utc, "ON_TRACK"

    # 3. No SLA configured
    return None, "NO_SLA_CONFIGURED"


def evaluate_case_sla_status(case: ComplaintCase, threshold_days: int = 5) -> str:
    """Evaluate current SLA status based on injectable clock."""
    if case.status in TERMINAL_STATUSES:
        return "DISPOSED"

    if not case.effective_deadline:
        return "NO_SLA_CONFIGURED"

    now_utc = ensure_utc(get_now())
    deadline_utc = ensure_utc(case.effective_deadline)

    if now_utc > deadline_utc:
        return "OVERDUE"

    remaining = deadline_utc - now_utc
    if remaining.total_seconds() <= (threshold_days * 86400):
        return "APPROACHING"

    return "ON_TRACK"


def refresh_case_sla(case: ComplaintCase, threshold_days: int = 5) -> None:
    """Updates case.sla_status in-place based on current time."""
    case.sla_status = evaluate_case_sla_status(case, threshold_days)
