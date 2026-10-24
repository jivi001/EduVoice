"""
Complaint Cases Router.

Implements:
1. Scoped case retrieval and filtering.
2. Case registration with stable ID generation and SLA calculation.
3. Complete lifecycle transitions (Transfer, Accept, Escalate, Dispose, Assign).
4. Synchronous cross-bureau overlap detection.
5. Strict confidentiality-level serialization.
"""
from datetime import date
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..clock import get_current_date, get_now
from ..db import get_db
from ..models import (
    Bureau,
    CaseHistory,
    CaseRelationship,
    ComplaintCase,
    Institution,
    User,
)
from ..security import get_current_user
from ..services.case_number import generate_case_id
from ..services.lifecycle import (
    accept_transferred_case,
    acknowledge_escalation,
    dispose_case,
    escalate_case,
    transfer_case,
    update_case_status,
    user_can_manage_bureau,
)
from ..services.overlap import detect_cross_bureau_overlaps_for_institution
from ..services.sla import calculate_effective_deadline, refresh_case_sla
from ..services.visibility import (
    can_view_full_case,
    filter_case_history_for_user,
    get_user_bureau_ids,
    is_central_admin,
    serialize_case_for_user,
)

router = APIRouter(prefix="/cases", tags=["cases"])


class CaseCreateIn(BaseModel):
    permanent_id: str
    bureau_id: int
    complainant_type: str = "Student"
    complainant_name: str | None = None
    complainant_email: str | None = None
    complainant_phone: str | None = None
    category: str = Field(min_length=2, max_length=64)
    subject: str = Field(min_length=2, max_length=255)
    description: str = Field(min_length=5)
    confidentiality_level: str = "ORDINARY"  # ORDINARY | HIGH
    received_date: date | None = None
    imported_due_date: date | None = None
    imported_due_date_trusted: bool = False


class StatusUpdateIn(BaseModel):
    next_status: str
    summary: str
    restricted_remarks: str | None = None


class TransferIn(BaseModel):
    destination_bureau_id: int
    reason: str
    restricted_remarks: str | None = None


class EscalateIn(BaseModel):
    reason: str
    restricted_remarks: str | None = None


class DisposeIn(BaseModel):
    resolution_summary: str
    restricted_remarks: str | None = None


class AssignIn(BaseModel):
    officer_id: int
    notes: str | None = None


@router.get("")
def list_cases(
    search: str | None = Query(None),
    permanent_id: str | None = Query(None),
    institution_id: int | None = Query(None),
    case_id: str | None = Query(None),
    bureau_id: int | None = Query(None),
    region: str | None = Query(None),
    state: str | None = Query(None),
    status: str | None = Query(None),
    category: str | None = Query(None),
    confidentiality_level: str | None = Query(None),
    overdue_only: bool = Query(False),
    overlap_only: bool = Query(False),
    limit: int = Query(100, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(ComplaintCase).join(Institution, ComplaintCase.institution_id == Institution.id)

    # Scoping: if not admin, by default users see their bureau cases and authorized shared cases
    if not is_central_admin(user):
        allowed_bids = get_user_bureau_ids(user)
        # Officers can filter by their bureau or see cases from other bureaus if viewing by institution
        if bureau_id:
            query = query.filter(ComplaintCase.current_bureau_id == bureau_id)
        elif not institution_id and not permanent_id:
            query = query.filter(ComplaintCase.current_bureau_id.in_(allowed_bids))
    elif bureau_id:
        query = query.filter(ComplaintCase.current_bureau_id == bureau_id)

    # Filters
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(or_(ComplaintCase.case_id.ilike(s), Institution.permanent_id.ilike(s), Institution.name.ilike(s)))
    if permanent_id:
        query = query.filter(Institution.permanent_id.ilike(f"%{permanent_id.strip()}%"))
    if institution_id:
        query = query.filter(ComplaintCase.institution_id == institution_id)
    if case_id:
        query = query.filter(ComplaintCase.case_id.ilike(f"%{case_id.strip()}%"))
    if region:
        query = query.filter(Institution.region == region)
    if state:
        query = query.filter(Institution.state == state)
    if status:
        query = query.filter(ComplaintCase.status == status)
    if category:
        query = query.filter(ComplaintCase.category == category)
    if confidentiality_level:
        query = query.filter(ComplaintCase.confidentiality_level == confidentiality_level)

    cases = query.order_by(ComplaintCase.created_at.desc()).all()

    # Refresh SLA in-memory for each case
    for c in cases:
        refresh_case_sla(c)

    if overdue_only:
        cases = [c for c in cases if c.sla_status == "OVERDUE"]

    if overlap_only:
        # Filter for cases that have active open overlaps
        open_overlap_case_ids: set[int] = set()
        open_rels = (
            db.query(CaseRelationship)
            .filter_by(relationship_type="CROSS_BUREAU_OVERLAP", alert_status="OPEN")
            .all()
        )
        for rel in open_rels:
            open_overlap_case_ids.add(rel.case_id_1)
            open_overlap_case_ids.add(rel.case_id_2)
        cases = [c for c in cases if c.id in open_overlap_case_ids]

    paginated = cases[offset : offset + limit]
    return {
        "total": len(cases),
        "limit": limit,
        "offset": offset,
        "cases": [serialize_case_for_user(c, user) for c in paginated],
    }


@router.post("", status_code=201)
def create_case(
    body: CaseCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Verify bureau
    bureau = db.query(Bureau).filter_by(id=body.bureau_id, is_active=True).first()
    if not bureau:
        raise HTTPException(400, "Bureau not found or inactive.")

    # Check permission: user must be admin or member of that bureau
    if not user_can_manage_bureau(user, bureau.id):
        raise HTTPException(403, f"You are not authorized to create cases in Bureau {bureau.code}.")

    # Verify institution
    inst = db.query(Institution).filter_by(permanent_id=body.permanent_id.strip()).first()
    if not inst:
        raise HTTPException(404, f"Institution with Permanent ID '{body.permanent_id}' not found.")

    received_date = body.received_date or get_current_date()
    now_utc = get_now()

    # Generate sequential unique case ID
    case_id = generate_case_id(db, received_date)

    # Compute effective deadline
    deadline_utc, sla_status = calculate_effective_deadline(
        db=db,
        received_date=received_date,
        bureau_id=bureau.id,
        category=body.category.strip(),
        imported_due_date=body.imported_due_date,
        imported_due_date_trusted=body.imported_due_date_trusted,
    )

    conf_level = body.confidentiality_level.upper()
    if conf_level not in ("ORDINARY", "HIGH"):
        conf_level = "ORDINARY"

    case = ComplaintCase(
        case_id=case_id,
        institution_id=inst.id,
        source_system="MANUAL",
        source_bureau_id=bureau.id,
        current_bureau_id=bureau.id,
        complainant_type=body.complainant_type,
        complainant_name=body.complainant_name,
        complainant_email=body.complainant_email,
        complainant_phone=body.complainant_phone,
        category=body.category.strip(),
        subject=body.subject.strip(),
        description=body.description.strip(),
        confidentiality_level=conf_level,
        received_date=received_date,
        created_at=now_utc,
        updated_at=now_utc,
        status="Pending",
        imported_due_date=body.imported_due_date,
        imported_due_date_trusted=body.imported_due_date_trusted,
        effective_deadline=deadline_utc,
        sla_status=sla_status,
        last_action=f"Registered by {user.name}",
    )
    db.add(case)
    db.flush()

    # Initial history entry
    db.add(
        CaseHistory(
            case_id=case.id,
            actor_id=user.id,
            actor_name=user.name,
            action_type="CREATED",
            new_status="Pending",
            source_bureau_id=bureau.id,
            destination_bureau_id=bureau.id,
            action_summary=f"Case registered in Bureau {bureau.code} by {user.name}.",
            event_visibility="CROSS_BUREAU_SUMMARY",
            created_at=now_utc,
        )
    )
    db.flush()

    # Synchronous cross-bureau overlap detection
    detect_cross_bureau_overlaps_for_institution(db, inst.id)

    db.commit()
    db.refresh(case)

    return serialize_case_for_user(case, user)


@router.get("/{id}")
def get_case(
    id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = db.query(ComplaintCase).filter_by(id=id).first()
    if not case:
        raise HTTPException(404, "Case not found.")

    refresh_case_sla(case)

    serialized = serialize_case_for_user(case, user)
    serialized["history"] = filter_case_history_for_user(case, user)

    # Attach related overlap alerts
    overlaps = (
        db.query(CaseRelationship)
        .filter(
            or_(CaseRelationship.case_id_1 == case.id, CaseRelationship.case_id_2 == case.id),
            CaseRelationship.relationship_type == "CROSS_BUREAU_OVERLAP",
        )
        .all()
    )
    serialized["overlaps"] = [
        {
            "id": r.id,
            "paired_case_id": r.case_2.case_id if r.case_id_1 == case.id else r.case_1.case_id,
            "paired_bureau": (
                r.case_2.current_bureau.code if r.case_id_1 == case.id else r.case_1.current_bureau.code
            ),
            "alert_status": r.alert_status,
            "review_status": r.review_status,
            "matching_reason": r.matching_reason,
            "detected_at": r.detected_at.isoformat(),
            "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
            "resolution_reason": r.resolution_reason,
        }
        for r in overlaps
    ]

    return serialized


@router.patch("/{id}/status")
def update_status(
    id: int,
    body: StatusUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = db.query(ComplaintCase).filter_by(id=id).first()
    if not case:
        raise HTTPException(404, "Case not found.")

    try:
        history = update_case_status(
            db=db,
            case=case,
            next_status=body.next_status,
            actor=user,
            summary=body.summary,
            restricted_remarks=body.restricted_remarks,
        )
        db.commit()
    except (ValueError, PermissionError) as e:
        db.rollback()
        raise HTTPException(400, str(e))

    return {"ok": True, "status": case.status, "history_id": history.id}


@router.post("/{id}/transfer")
def transfer(
    id: int,
    body: TransferIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = db.query(ComplaintCase).filter_by(id=id).first()
    if not case:
        raise HTTPException(404, "Case not found.")

    try:
        history = transfer_case(
            db=db,
            case=case,
            destination_bureau_id=body.destination_bureau_id,
            actor=user,
            reason=body.reason,
            restricted_remarks=body.restricted_remarks,
        )
        db.commit()
    except (ValueError, PermissionError) as e:
        db.rollback()
        raise HTTPException(400, str(e))

    return {"ok": True, "status": case.status, "current_bureau_id": case.current_bureau_id}


@router.post("/{id}/accept-transfer")
def accept_transfer(
    id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = db.query(ComplaintCase).filter_by(id=id).first()
    if not case:
        raise HTTPException(404, "Case not found.")

    try:
        history = accept_transferred_case(db=db, case=case, actor=user)
        db.commit()
    except (ValueError, PermissionError) as e:
        db.rollback()
        raise HTTPException(400, str(e))

    return {"ok": True, "status": case.status}


@router.post("/{id}/escalate")
def escalate(
    id: int,
    body: EscalateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = db.query(ComplaintCase).filter_by(id=id).first()
    if not case:
        raise HTTPException(404, "Case not found.")

    try:
        history = escalate_case(
            db=db,
            case=case,
            actor=user,
            reason=body.reason,
            restricted_remarks=body.restricted_remarks,
        )
        db.commit()
    except (ValueError, PermissionError) as e:
        db.rollback()
        raise HTTPException(400, str(e))

    return {"ok": True, "status": case.status}


@router.post("/{id}/acknowledge-escalation")
def ack_escalation(
    id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = db.query(ComplaintCase).filter_by(id=id).first()
    if not case:
        raise HTTPException(404, "Case not found.")

    try:
        history = acknowledge_escalation(db=db, case=case, actor=user)
        db.commit()
    except (ValueError, PermissionError) as e:
        db.rollback()
        raise HTTPException(400, str(e))

    return {"ok": True, "status": case.status}


@router.post("/{id}/dispose")
def dispose(
    id: int,
    body: DisposeIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = db.query(ComplaintCase).filter_by(id=id).first()
    if not case:
        raise HTTPException(404, "Case not found.")

    try:
        history = dispose_case(
            db=db,
            case=case,
            actor=user,
            resolution_summary=body.resolution_summary,
            restricted_remarks=body.restricted_remarks,
        )
        db.commit()
    except (ValueError, PermissionError) as e:
        db.rollback()
        raise HTTPException(400, str(e))

    return {"ok": True, "status": case.status}


@router.post("/{id}/assign")
def assign_officer(
    id: int,
    body: AssignIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = db.query(ComplaintCase).filter_by(id=id).first()
    if not case:
        raise HTTPException(404, "Case not found.")

    if not user_can_manage_bureau(user, case.current_bureau_id):
        raise HTTPException(403, "Not authorized to assign officers for this bureau.")

    target_user = db.query(User).filter_by(id=body.officer_id).first()
    if not target_user:
        raise HTTPException(404, "Target officer user not found.")

    prev_officer_id = case.assigned_officer_id
    case.assigned_officer_id = target_user.id
    now_utc = get_now()

    summary = f"Assigned to officer {target_user.name} by {user.name}."
    case.last_action = summary
    case.updated_at = now_utc

    db.add(
        CaseHistory(
            case_id=case.id,
            actor_id=user.id,
            actor_name=user.name,
            action_type="ASSIGNED",
            previous_officer_id=prev_officer_id,
            new_officer_id=target_user.id,
            action_summary=summary,
            restricted_remarks=body.notes,
            event_visibility="RESPONSIBLE_BUREAU",
            created_at=now_utc,
        )
    )
    db.commit()

    return {"ok": True, "assigned_officer_id": target_user.id, "assigned_officer_name": target_user.name}
