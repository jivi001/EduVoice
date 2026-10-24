"""
Centralized case lifecycle state machine, validation, and transition engine.

Strictly enforces:
1. 5 statuses: Pending, Under Process, Transferred, Escalated, Disposed.
2. Disposed is strictly terminal.
3. Direct Pending -> Disposed is rejected.
4. Role and bureau-scope authorization checks.
5. Audit history recording with event visibility classification.
6. Synchronous overlap detection on state changes.
"""
from typing import Any
from sqlalchemy.orm import Session

from ..clock import get_now
from ..models import (
    AuditEvent,
    Bureau,
    CaseHistory,
    ComplaintCase,
    Notification,
    User,
    UserBureauAssignment,
)
from .overlap import detect_cross_bureau_overlaps_for_institution

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "Pending": {"Under Process", "Transferred", "Escalated"},
    "Under Process": {"Transferred", "Escalated", "Disposed"},
    "Transferred": {"Under Process", "Transferred", "Escalated", "Disposed"},
    "Escalated": {"Under Process", "Transferred", "Escalated", "Disposed"},
    "Disposed": set(),  # Terminal
}


def user_can_manage_bureau(user: User, bureau_id: int) -> bool:
    """Checks if user has officer or supervisor scope for the given bureau."""
    if user.role == "admin":
        return True
    return any(a.bureau_id == bureau_id for a in user.bureau_assignments)


def validate_transition(
    case: ComplaintCase,
    next_status: str,
    actor: User,
) -> None:
    """Validates if status transition is allowed and actor is authorized."""
    curr = case.status
    if curr == "Disposed":
        raise ValueError("Disposed cases are terminal and cannot be modified through ordinary status updates.")

    allowed = ALLOWED_TRANSITIONS.get(curr, set())
    if next_status not in allowed:
        if curr == "Pending" and next_status == "Disposed":
            raise ValueError(
                "Direct disposal from Pending is not allowed. The case must enter 'Under Process' first."
            )
        raise ValueError(f"Invalid status transition from '{curr}' to '{next_status}'. Allowed: {sorted(allowed)}")

    # Authorization checks
    if actor.role != "admin":
        # Check bureau authority
        if not user_can_manage_bureau(actor, case.current_bureau_id):
            raise PermissionError(
                f"User '{actor.username}' is not authorized to act on cases in Bureau {case.current_bureau.code}."
            )


def update_case_status(
    db: Session,
    case: ComplaintCase,
    next_status: str,
    actor: User,
    summary: str,
    restricted_remarks: str | None = None,
    destination_bureau_id: int | None = None,
    new_officer_id: int | None = None,
    event_visibility: str = "CROSS_BUREAU_SUMMARY",
) -> CaseHistory:
    """
    Executes a status change, validates state machine, logs CaseHistory,
    records AuditEvent, and triggers synchronous overlap evaluation.
    """
    validate_transition(case, next_status, actor)

    prev_status = case.status
    prev_bureau_id = case.current_bureau_id
    prev_officer_id = case.assigned_officer_id
    now_utc = get_now()

    case.status = next_status
    case.updated_at = now_utc
    case.last_action = summary

    # Bureau transfer update
    if destination_bureau_id and destination_bureau_id != case.current_bureau_id:
        case.current_bureau_id = destination_bureau_id

    # Officer assignment update
    if new_officer_id is not None:
        case.assigned_officer_id = new_officer_id

    # Append CaseHistory entry
    action_type = "STATUS_CHANGE"
    if next_status == "Transferred":
        action_type = "TRANSFERRED"
    elif next_status == "Escalated":
        action_type = "ESCALATED"
    elif next_status == "Disposed":
        action_type = "DISPOSED"
    elif prev_status == "Transferred" and next_status == "Under Process":
        action_type = "TRANSFER_ACCEPTED"
    elif prev_status == "Escalated" and next_status == "Under Process":
        action_type = "ESCALATION_ACKNOWLEDGED"

    history = CaseHistory(
        case_id=case.id,
        actor_id=actor.id,
        actor_name=actor.name,
        action_type=action_type,
        previous_status=prev_status,
        new_status=next_status,
        source_bureau_id=prev_bureau_id,
        destination_bureau_id=destination_bureau_id or prev_bureau_id,
        previous_officer_id=prev_officer_id,
        new_officer_id=case.assigned_officer_id,
        action_summary=summary,
        restricted_remarks=restricted_remarks,
        event_visibility=event_visibility,
        created_at=now_utc,
    )
    db.add(history)

    # Record security audit log
    audit = AuditEvent(
        actor_id=actor.id,
        actor_username=actor.username,
        event_type=f"CASE_{action_type}",
        target_type="CASE",
        target_id=case.case_id,
        details={
            "previous_status": prev_status,
            "new_status": next_status,
            "bureau_id": case.current_bureau_id,
            "summary": summary,
        },
        timestamp=now_utc,
    )
    db.add(audit)
    db.flush()

    # Synchronous cross-bureau overlap detection on status or bureau change
    detect_cross_bureau_overlaps_for_institution(db, case.institution_id)

    return history


def transfer_case(
    db: Session,
    case: ComplaintCase,
    destination_bureau_id: int,
    actor: User,
    reason: str,
    restricted_remarks: str | None = None,
) -> CaseHistory:
    """Transfers a case to another bureau, keeping history and original case ID."""
    dest_bureau = db.query(Bureau).filter_by(id=destination_bureau_id, is_active=True).first()
    if not dest_bureau:
        raise ValueError(f"Destination bureau ID {destination_bureau_id} not found or inactive.")

    if destination_bureau_id == case.current_bureau_id:
        raise ValueError("Cannot transfer a case to the bureau that currently holds it.")

    summary = f"Case transferred from Bureau {case.current_bureau.code} to Bureau {dest_bureau.code}. Reason: {reason}"
    history = update_case_status(
        db=db,
        case=case,
        next_status="Transferred",
        actor=actor,
        summary=summary,
        restricted_remarks=restricted_remarks,
        destination_bureau_id=destination_bureau_id,
        event_visibility="CROSS_BUREAU_SUMMARY",
    )

    # Persistent notification for receiving bureau officers
    receiving_users = (
        db.query(User)
        .join(UserBureauAssignment)
        .filter(UserBureauAssignment.bureau_id == destination_bureau_id, User.status == "active")
        .all()
    )
    now_utc = get_now()
    for u in receiving_users:
        db.add(
            Notification(
                recipient_id=u.id,
                alert_type="TRANSFER_PENDING",
                related_case_id=case.id,
                dedup_key=f"TRANSFER_{case.id}_{dest_bureau.id}_{u.id}",
                title=f"Incoming Case Transfer: {case.case_id}",
                message=f"Case {case.case_id} has been transferred to {dest_bureau.code} from {case.source_bureau.code}.",
                status="UNREAD",
                created_at=now_utc,
            )
        )

    db.flush()
    return history


def accept_transferred_case(
    db: Session,
    case: ComplaintCase,
    actor: User,
    remarks: str | None = None,
) -> CaseHistory:
    """Accepts a transferred case by an officer/supervisor in the receiving bureau."""
    if case.status != "Transferred":
        raise ValueError(f"Cannot accept case with status '{case.status}'; must be 'Transferred'.")

    if not user_can_manage_bureau(actor, case.current_bureau_id):
        raise PermissionError("Only authorized officers of the receiving bureau can accept transferred cases.")

    summary = f"Case transfer accepted by {actor.name} ({case.current_bureau.code}). Case is now Under Process."
    return update_case_status(
        db=db,
        case=case,
        next_status="Under Process",
        actor=actor,
        summary=summary,
        restricted_remarks=remarks,
        event_visibility="CROSS_BUREAU_SUMMARY",
    )


def escalate_case(
    db: Session,
    case: ComplaintCase,
    actor: User,
    reason: str,
    restricted_remarks: str | None = None,
) -> CaseHistory:
    """Escalates a case to the bureau supervisor or central admin queue."""
    summary = f"Case escalated by {actor.name}. Reason: {reason}"
    history = update_case_status(
        db=db,
        case=case,
        next_status="Escalated",
        actor=actor,
        summary=summary,
        restricted_remarks=restricted_remarks,
        event_visibility="CROSS_BUREAU_SUMMARY",
    )

    # Notify bureau supervisor if configured, or central admins
    supervisor_id = case.current_bureau.supervisor_id
    recipients = []
    if supervisor_id:
        recipients.append(supervisor_id)
    else:
        admins = db.query(User.id).filter(User.role == "admin", User.status == "active").all()
        recipients.extend(r[0] for r in admins)

    now_utc = get_now()
    for uid in set(recipients):
        db.add(
            Notification(
                recipient_id=uid,
                alert_type="ESCALATION",
                related_case_id=case.id,
                dedup_key=f"ESCALATION_{case.id}_{uid}",
                title=f"Case Escalated: {case.case_id}",
                message=f"Case {case.case_id} ({case.institution.name}) was escalated: {reason}",
                status="UNREAD",
                created_at=now_utc,
            )
        )

    db.flush()
    return history


def acknowledge_escalation(
    db: Session,
    case: ComplaintCase,
    actor: User,
    remarks: str | None = None,
) -> CaseHistory:
    """Acknowledges an escalated case and returns it to Under Process."""
    if case.status != "Escalated":
        raise ValueError(f"Cannot acknowledge case with status '{case.status}'; must be 'Escalated'.")

    summary = f"Escalation acknowledged by {actor.name}. Case returned to Under Process."
    return update_case_status(
        db=db,
        case=case,
        next_status="Under Process",
        actor=actor,
        summary=summary,
        restricted_remarks=remarks,
        event_visibility="CROSS_BUREAU_SUMMARY",
    )


def dispose_case(
    db: Session,
    case: ComplaintCase,
    actor: User,
    resolution_summary: str,
    restricted_remarks: str | None = None,
) -> CaseHistory:
    """Disposes a case, validating it came from an active working state, and resolves active overlap alerts."""
    if case.status == "Pending":
        raise ValueError("Direct disposal from Pending is prohibited. Case must be reviewed in 'Under Process' first.")

    summary = f"Case disposed. Resolution: {resolution_summary}"
    history = update_case_status(
        db=db,
        case=case,
        next_status="Disposed",
        actor=actor,
        summary=summary,
        restricted_remarks=restricted_remarks,
        event_visibility="CROSS_BUREAU_SUMMARY",
    )
    return history
