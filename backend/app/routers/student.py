from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..clock import get_current_date, get_now
from ..db import get_db
from ..models import (
    Assignment,
    Bureau,
    CaseHistory,
    ComplaintCase,
    Enrollment,
    Institution,
    Issuance,
    User,
)
from ..security import require_role
from ..services.case_number import generate_case_id
from ..services.overlap import detect_cross_bureau_overlaps_for_institution
from ..services.sla import calculate_effective_deadline

router = APIRouter(prefix="/student", tags=["student"])


class StudentComplaintIn(BaseModel):
    permanent_id: str = Field(min_length=3, max_length=64)
    category: str = Field(min_length=2, max_length=64)
    subject: str = Field(min_length=2, max_length=255)
    description: str = Field(min_length=5)
    confidentiality_level: str = "ORDINARY"  # ORDINARY | HIGH
    phone: str | None = None


@router.get("/complaints")
def list_student_complaints(
    user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    """Lists all complaints filed by the authenticated student."""
    cases = (
        db.query(ComplaintCase)
        .filter(
            (ComplaintCase.complainant_email == user.email)
            | (ComplaintCase.complainant_name == user.name)
        )
        .order_by(ComplaintCase.created_at.desc())
        .all()
    )
    return [
        {
            "id": c.id,
            "case_id": c.case_id,
            "institution_name": c.institution.name if c.institution else "",
            "permanent_id": c.institution.permanent_id if c.institution else "",
            "category": c.category,
            "subject": c.subject,
            "status": c.status,
            "received_date": c.received_date.isoformat(),
            "effective_deadline": c.effective_deadline.isoformat() if c.effective_deadline else None,
            "sla_status": c.sla_status,
            "last_action": c.last_action,
        }
        for c in cases
    ]


@router.post("/complaints", status_code=201)
def submit_student_complaint(
    body: StudentComplaintIn,
    user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    """Allows an authenticated student to lodge an official AICTE grievance."""
    inst = db.query(Institution).filter_by(permanent_id=body.permanent_id.strip()).first()
    if not inst:
        raise HTTPException(404, f"Institution with Permanent ID '{body.permanent_id}' not found.")

    # Route students to Public Grievance Redressal Cell (PGRC) by default
    pgrc = db.query(Bureau).filter_by(code="PGRC").first()
    if not pgrc:
        pgrc = db.query(Bureau).first()
    if not pgrc:
        raise HTTPException(500, "Grievance cell routing unavailable.")

    received_date = get_current_date()
    now_utc = get_now()

    case_id = generate_case_id(db, received_date)
    deadline_utc, sla_status = calculate_effective_deadline(
        db=db,
        received_date=received_date,
        bureau_id=pgrc.id,
        category=body.category.strip(),
    )

    conf_level = body.confidentiality_level.upper()
    if conf_level not in ("ORDINARY", "HIGH"):
        conf_level = "ORDINARY"

    case = ComplaintCase(
        case_id=case_id,
        institution_id=inst.id,
        source_system="STUDENT_PORTAL",
        source_bureau_id=pgrc.id,
        current_bureau_id=pgrc.id,
        complainant_type="Student",
        complainant_name=user.name,
        complainant_email=user.email or f"{user.username}@student.aicte",
        complainant_phone=body.phone,
        category=body.category.strip(),
        subject=body.subject.strip(),
        description=body.description.strip(),
        confidentiality_level=conf_level,
        received_date=received_date,
        created_at=now_utc,
        updated_at=now_utc,
        status="Pending",
        effective_deadline=deadline_utc,
        sla_status=sla_status,
        last_action=f"Lodged by student {user.name}",
    )
    db.add(case)
    db.flush()

    db.add(
        CaseHistory(
            case_id=case.id,
            actor_id=user.id,
            actor_name=user.name,
            action_type="CREATED",
            new_status="Pending",
            source_bureau_id=pgrc.id,
            destination_bureau_id=pgrc.id,
            action_summary=f"Grievance lodged directly by student via Student Portal.",
            event_visibility="CROSS_BUREAU_SUMMARY",
            created_at=now_utc,
        )
    )
    db.flush()

    # Synchronous cross-bureau overlap detection
    detect_cross_bureau_overlaps_for_institution(db, inst.id)

    db.commit()
    db.refresh(case)

    return {
        "id": case.id,
        "case_id": case.case_id,
        "status": case.status,
        "effective_deadline": case.effective_deadline.isoformat() if case.effective_deadline else None,
        "message": "Grievance submitted successfully. Track status using your Case ID.",
    }


# ==============================================================================
# Legacy Course Feedback Endpoints (Preserved)
# ==============================================================================

@router.get("/assignments")
def my_assignments(user: User = Depends(require_role("student")), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Assignment).join(Enrollment, Enrollment.assignment_id == Assignment.id)
        .where(Enrollment.student_id == user.id, Assignment.is_open.is_(True))
    ).all()
    issued = set(db.scalars(select(Issuance.assignment_id).where(Issuance.student_id == user.id)))
    return [
        {
            "assignment_id": a.id,
            "subject": a.subject.name,
            "subject_code": a.subject.code,
            "teacher": a.teacher.name,
            "semester": a.semester,
            "credential_issued": a.id in issued,
        }
        for a in rows
    ]


@router.get("/assignments/{assignment_id}")
def assignment_detail(assignment_id: int, user: User = Depends(require_role("student")),
                      db: Session = Depends(get_db)):
    for a in my_assignments(user, db):
        if a["assignment_id"] == assignment_id:
            return a
    raise HTTPException(404, "Course not found")
