"""
Cross-bureau overlap detection and resolution service.

Enforces deterministic detection:
Multiple active cases for the same institution in different responsible bureaus
produce an alert and persistent case relationship.
"""
from datetime import datetime
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..clock import get_now
from ..models import (
    CaseRelationship,
    ComplaintCase,
    Institution,
    Notification,
    User,
    UserBureauAssignment,
)
from .sla import ACTIVE_STATUSES


def normalize_case_pair(id_a: int, id_b: int) -> tuple[int, int]:
    """Ensures case_id_1 < case_id_2 for canonical pairing."""
    return (id_a, id_b) if id_a < id_b else (id_b, id_a)


def detect_cross_bureau_overlaps_for_institution(db: Session, institution_id: int) -> list[CaseRelationship]:
    """
    Synchronously evaluates all active cases for an institution and creates/updates
    cross-bureau overlap relationships.
    Uses row-level locking on the institution where supported.
    """
    # Lock the institution row during evaluation to prevent race conditions
    inst = db.query(Institution).filter_by(id=institution_id).with_for_update().first()
    if not inst:
        return []

    # Get all cases for this institution
    all_cases = (
        db.query(ComplaintCase)
        .filter(ComplaintCase.institution_id == institution_id)
        .all()
    )

    active_cases = [c for c in all_cases if c.status in ACTIVE_STATUSES]
    now_utc = get_now()
    created_or_updated: list[CaseRelationship] = []

    # 1. Evaluate every active pair across different bureaus
    active_pair_keys: set[tuple[int, int]] = set()

    for i in range(len(active_cases)):
        for j in range(i + 1, len(active_cases)):
            c1 = active_cases[i]
            c2 = active_cases[j]

            if c1.current_bureau_id != c2.current_bureau_id:
                p1, p2 = normalize_case_pair(c1.id, c2.id)
                active_pair_keys.add((p1, p2))

                rel = (
                    db.query(CaseRelationship)
                    .filter_by(case_id_1=p1, case_id_2=p2)
                    .first()
                )

                b1_code = c1.current_bureau.code if c1.current_bureau else str(c1.current_bureau_id)
                b2_code = c2.current_bureau.code if c2.current_bureau else str(c2.current_bureau_id)
                reason = (
                    f"Active cases exist across multiple bureaus ({b1_code} and {b2_code}) "
                    f"for Institution '{inst.name}' (Permanent ID: {inst.permanent_id})."
                )

                if not rel:
                    rel = CaseRelationship(
                        case_id_1=p1,
                        case_id_2=p2,
                        relationship_type="CROSS_BUREAU_OVERLAP",
                        review_status="PENDING_REVIEW",
                        alert_status="OPEN",
                        matching_reason=reason,
                        detected_at=now_utc,
                    )
                    db.add(rel)
                    db.flush()
                    _notify_overlap_parties(db, rel, c1, c2, inst.name)
                    created_or_updated.append(rel)
                elif rel.alert_status != "OPEN" and rel.review_status != "DISMISSED":
                    # Reopen if previously resolved and conditions qualify again
                    rel.alert_status = "OPEN"
                    rel.matching_reason = reason
                    rel.resolved_at = None
                    rel.resolution_reason = None
                    db.flush()
                    _notify_overlap_parties(db, rel, c1, c2, inst.name)
                    created_or_updated.append(rel)

    # 2. Auto-resolve existing relationships for this institution if condition no longer holds
    existing_rels = (
        db.query(CaseRelationship)
        .join(ComplaintCase, CaseRelationship.case_id_1 == ComplaintCase.id)
        .filter(
            ComplaintCase.institution_id == institution_id,
            CaseRelationship.relationship_type == "CROSS_BUREAU_OVERLAP",
            CaseRelationship.alert_status == "OPEN",
        )
        .all()
    )

    case_map = {c.id: c for c in all_cases}

    for rel in existing_rels:
        p1, p2 = rel.case_id_1, rel.case_id_2
        c1 = case_map.get(p1)
        c2 = case_map.get(p2)

        if not c1 or not c2:
            continue

        # Condition 1: Either case is disposed
        if c1.status not in ACTIVE_STATUSES or c2.status not in ACTIVE_STATUSES:
            rel.alert_status = "RESOLVED"
            rel.resolved_at = now_utc
            rel.resolution_reason = "Auto-resolved: One or both cases have been disposed."
            _resolve_related_notifications(db, rel.id)
            created_or_updated.append(rel)
        # Condition 2: Both cases now belong to the same bureau
        elif c1.current_bureau_id == c2.current_bureau_id:
            rel.alert_status = "RESOLVED"
            rel.resolved_at = now_utc
            rel.resolution_reason = (
                f"Auto-resolved: Both cases transferred to the same bureau ({c1.current_bureau.code})."
            )
            _resolve_related_notifications(db, rel.id)
            created_or_updated.append(rel)

    db.flush()
    return created_or_updated


def _notify_overlap_parties(
    db: Session,
    rel: CaseRelationship,
    case_1: ComplaintCase,
    case_2: ComplaintCase,
    institution_name: str,
) -> None:
    """Creates persistent, deduplicated notifications for central admins and relevant bureau officers."""
    # Find all recipients: central admins + officers of bureau 1 + officers of bureau 2
    central_admins = db.query(User).filter(User.role == "admin", User.status == "active").all()
    b1_users = (
        db.query(User)
        .join(UserBureauAssignment)
        .filter(UserBureauAssignment.bureau_id == case_1.current_bureau_id, User.status == "active")
        .all()
    )
    b2_users = (
        db.query(User)
        .join(UserBureauAssignment)
        .filter(UserBureauAssignment.bureau_id == case_2.current_bureau_id, User.status == "active")
        .all()
    )

    recipients = {u.id: u for u in central_admins + b1_users + b2_users}.values()
    now_utc = get_now()

    for user in recipients:
        dedup_key = f"OVERLAP_{rel.case_id_1}_{rel.case_id_2}_{user.id}"
        existing = db.query(Notification).filter_by(dedup_key=dedup_key).first()

        title = f"Cross-Bureau Overlap: {case_1.case_id} & {case_2.case_id}"
        msg = (
            f"Overlapping active cases detected for {institution_name} "
            f"between Bureau {case_1.current_bureau.code} and Bureau {case_2.current_bureau.code}."
        )

        if not existing:
            n = Notification(
                recipient_id=user.id,
                alert_type="OVERLAP_DETECTED",
                related_case_id=case_1.id,
                related_relationship_id=rel.id,
                dedup_key=dedup_key,
                title=title,
                message=msg,
                status="UNREAD",
                created_at=now_utc,
            )
            db.add(n)
        elif existing.status == "RESOLVED":
            existing.status = "UNREAD"
            existing.created_at = now_utc
            existing.resolved_at = None


def _resolve_related_notifications(db: Session, relationship_id: int) -> None:
    """Marks related notifications as resolved."""
    now_utc = get_now()
    notifications = (
        db.query(Notification)
        .filter(
            Notification.related_relationship_id == relationship_id,
            Notification.status != "RESOLVED",
        )
        .all()
    )
    for n in notifications:
        n.status = "RESOLVED"
        n.resolved_at = now_utc
