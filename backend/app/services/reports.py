"""
MIS Reporting and Safe CSV Export service for AICTE Complaint Tracking.

Implements:
1. Bureau-wise workload & disposal rate (disposed / total * 100).
2. Region-wise volume.
3. Status distribution and active ageing.
4. Overlap statistics (Open vs Resolved).
5. Safe CSV export with formula injection neutralization (=, +, -, @).
6. Strict role-based scoping (Bureau officers only see authorized metrics).
"""
import csv
import io
from datetime import datetime
from typing import Any
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..clock import ensure_utc, get_current_date, get_now
from ..models import (
    Bureau,
    CaseRelationship,
    ComplaintCase,
    Institution,
    User,
)
from .visibility import get_user_bureau_ids, is_central_admin


def get_scoped_case_query(db: Session, user: User):
    """Returns base query filtered by the user's authorized bureau scope."""
    q = db.query(ComplaintCase)
    if not is_central_admin(user):
        user_bureaus = get_user_bureau_ids(user)
        q = q.filter(ComplaintCase.current_bureau_id.in_(user_bureaus))
    return q


def generate_mis_reports(db: Session, user: User) -> dict[str, Any]:
    """Generates complete MIS analytical aggregations scoped to the user."""
    today = get_current_date()
    now_utc = get_now()

    base_cases = get_scoped_case_query(db, user)
    all_cases = base_cases.all()

    total_registered = len(all_cases)
    active_cases = [c for c in all_cases if c.status != "Disposed"]
    total_active = len(active_cases)
    disposed_count = sum(1 for c in all_cases if c.status == "Disposed")

    # Status distribution
    status_counts: dict[str, int] = {
        "Pending": 0,
        "Under Process": 0,
        "Transferred": 0,
        "Escalated": 0,
        "Disposed": 0,
    }
    for c in all_cases:
        if c.status in status_counts:
            status_counts[c.status] += 1

    # Overdue and Approaching
    overdue_count = 0
    approaching_count = 0
    now_utc_aware = ensure_utc(now_utc)
    for c in active_cases:
        if c.effective_deadline:
            c_deadline = ensure_utc(c.effective_deadline)
            if now_utc_aware > c_deadline:
                overdue_count += 1
            elif (c_deadline - now_utc_aware).total_seconds() <= (5 * 86400):
                approaching_count += 1

    # Bureau-wise breakdown
    all_bureaus = db.query(Bureau).filter_by(is_active=True).all()
    if not is_central_admin(user):
        allowed_bids = get_user_bureau_ids(user)
        all_bureaus = [b for b in all_bureaus if b.id in allowed_bids]

    bureau_stats: list[dict[str, Any]] = []
    for b in all_bureaus:
        b_cases = [c for c in all_cases if c.current_bureau_id == b.id]
        b_total = len(b_cases)
        b_disposed = sum(1 for c in b_cases if c.status == "Disposed")
        b_active = b_total - b_disposed
        b_overdue = sum(
            1
            for c in b_cases
            if c.status != "Disposed"
            and c.effective_deadline
            and now_utc_aware > ensure_utc(c.effective_deadline)
        )
        disposal_rate = round((b_disposed / b_total * 100), 1) if b_total > 0 else 0.0

        bureau_stats.append({
            "bureau_id": b.id,
            "bureau_code": b.code,
            "bureau_name": b.name,
            "total_cases": b_total,
            "active_cases": b_active,
            "disposed_cases": b_disposed,
            "overdue_cases": b_overdue,
            "disposal_rate_pct": disposal_rate,
        })

    # Region-wise breakdown
    region_stats: dict[str, dict[str, int]] = {}
    for c in all_cases:
        reg = c.institution.region if c.institution and c.institution.region else "Unknown"
        if reg not in region_stats:
            region_stats[reg] = {"total": 0, "active": 0, "disposed": 0}
        region_stats[reg]["total"] += 1
        if c.status == "Disposed":
            region_stats[reg]["disposed"] += 1
        else:
            region_stats[reg]["active"] += 1

    # Active Case Ageing: 0-15 days, 16-30 days, 31-60 days, >60 days
    ageing = {"0_15_days": 0, "16_30_days": 0, "31_60_days": 0, "over_60_days": 0}
    for c in active_cases:
        age_days = (today - c.received_date).days
        if age_days <= 15:
            ageing["0_15_days"] += 1
        elif age_days <= 30:
            ageing["16_30_days"] += 1
        elif age_days <= 60:
            ageing["31_60_days"] += 1
        else:
            ageing["over_60_days"] += 1

    # Cross-bureau overlap statistics
    overlap_q = db.query(CaseRelationship).filter(CaseRelationship.relationship_type == "CROSS_BUREAU_OVERLAP")
    open_overlaps = overlap_q.filter(CaseRelationship.alert_status == "OPEN").count()
    resolved_overlaps = overlap_q.filter(CaseRelationship.alert_status == "RESOLVED").count()

    overall_disposal_rate = round((disposed_count / total_registered * 100), 1) if total_registered > 0 else 0.0

    return {
        "metrics": {
            "total_registered": total_registered,
            "total_active": total_active,
            "disposed": disposed_count,
            "pending": status_counts["Pending"],
            "under_process": status_counts["Under Process"],
            "transferred": status_counts["Transferred"],
            "escalated": status_counts["Escalated"],
            "overdue_active": overdue_count,
            "approaching_active": approaching_count,
            "open_cross_bureau_overlaps": open_overlaps,
            "resolved_cross_bureau_overlaps": resolved_overlaps,
            "disposal_rate_pct": overall_disposal_rate,
        },
        "bureau_breakdown": bureau_stats,
        "region_breakdown": [
            {"region": r, "total": v["total"], "active": v["active"], "disposed": v["disposed"]}
            for r, v in sorted(region_stats.items())
        ],
        "ageing_breakdown": ageing,
    }


def sanitize_csv_cell(value: Any) -> str:
    """
    Spreadsheet formula injection prevention.
    Prefixes values starting with '=', '+', '-', '@', '\t', '\r' with an apostrophe.
    """
    if value is None:
        return ""
    s = str(value)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{s}"
    return s


def export_cases_to_safe_csv(cases: list[ComplaintCase], user: User) -> str:
    """
    Exports cases to CSV, enforcing CSV safety and role-based confidentiality.
    """
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    headers = [
        "Case ID",
        "AICTE Permanent ID",
        "Institution Name",
        "Region",
        "State",
        "Responsible Bureau",
        "Category",
        "Subject",
        "Status",
        "Received Date",
        "Effective Deadline",
        "SLA Status",
        "Confidentiality",
    ]
    writer.writerow(headers)

    for c in cases:
        is_high_confidential_cross = (c.confidentiality_level == "HIGH" and not is_central_admin(user) and c.current_bureau_id not in get_user_bureau_ids(user))

        if is_high_confidential_cross:
            row = [
                sanitize_csv_cell(c.case_id),
                sanitize_csv_cell(c.institution.permanent_id if c.institution else ""),
                sanitize_csv_cell(c.institution.name if c.institution else ""),
                sanitize_csv_cell(c.institution.region if c.institution else ""),
                sanitize_csv_cell(c.institution.state if c.institution else ""),
                sanitize_csv_cell(c.current_bureau.code if c.current_bureau else ""),
                "[CONFIDENTIAL - HIGH]",
                "[RESTRICTED]",
                "[RESTRICTED]",
                "",
                "",
                "[RESTRICTED]",
                "HIGH",
            ]
        else:
            row = [
                sanitize_csv_cell(c.case_id),
                sanitize_csv_cell(c.institution.permanent_id if c.institution else ""),
                sanitize_csv_cell(c.institution.name if c.institution else ""),
                sanitize_csv_cell(c.institution.region if c.institution else ""),
                sanitize_csv_cell(c.institution.state if c.institution else ""),
                sanitize_csv_cell(c.current_bureau.code if c.current_bureau else ""),
                sanitize_csv_cell(c.category),
                sanitize_csv_cell(c.subject),
                sanitize_csv_cell(c.status),
                sanitize_csv_cell(c.received_date.isoformat()),
                sanitize_csv_cell(c.effective_deadline.isoformat() if c.effective_deadline else "NO_SLA"),
                sanitize_csv_cell(c.sla_status),
                sanitize_csv_cell(c.confidentiality_level),
            ]
        writer.writerow(row)

    return output.getvalue()
