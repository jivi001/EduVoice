"""
Cross-Bureau Overlap Alerts and Review Router.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..clock import get_now
from ..db import get_db
from ..models import CaseRelationship, User
from ..security import get_current_user
from ..services.visibility import is_central_admin

router = APIRouter(prefix="/overlaps", tags=["overlaps"])


class OverlapReviewIn(BaseModel):
    review_status: str  # CONFIRMED_RELATED | DISMISSED
    resolution_reason: str | None = None


@router.get("")
def list_overlaps(
    status: str | None = Query("OPEN", description="OPEN | RESOLVED | ALL"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(CaseRelationship).filter(
        CaseRelationship.relationship_type == "CROSS_BUREAU_OVERLAP"
    )
    if status and status.upper() != "ALL":
        query = query.filter(CaseRelationship.alert_status == status.upper())

    rels = query.order_by(CaseRelationship.detected_at.desc()).all()

    return [
        {
            "id": r.id,
            "case_1": {
                "id": r.case_1.id,
                "case_id": r.case_1.case_id,
                "bureau_code": r.case_1.current_bureau.code,
                "status": r.case_1.status,
                "subject": r.case_1.subject if r.case_1.confidentiality_level != "HIGH" else "[RESTRICTED]",
            },
            "case_2": {
                "id": r.case_2.id,
                "case_id": r.case_2.case_id,
                "bureau_code": r.case_2.current_bureau.code,
                "status": r.case_2.status,
                "subject": r.case_2.subject if r.case_2.confidentiality_level != "HIGH" else "[RESTRICTED]",
            },
            "institution": {
                "id": r.case_1.institution_id,
                "permanent_id": r.case_1.institution.permanent_id,
                "name": r.case_1.institution.name,
                "state": r.case_1.institution.state,
                "region": r.case_1.institution.region,
            },
            "relationship_type": r.relationship_type,
            "review_status": r.review_status,
            "alert_status": r.alert_status,
            "matching_reason": r.matching_reason,
            "detected_at": r.detected_at.isoformat(),
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
            "reviewed_by_name": r.reviewed_by.name if r.reviewed_by else None,
            "resolution_reason": r.resolution_reason,
            "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
        }
        for r in rels
    ]


@router.post("/{id}/review")
def review_overlap(
    id: int,
    body: OverlapReviewIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rel = db.query(CaseRelationship).filter_by(id=id).first()
    if not rel:
        raise HTTPException(404, "Overlap relationship not found.")

    if body.review_status not in ("CONFIRMED_RELATED", "DISMISSED"):
        raise HTTPException(400, "review_status must be 'CONFIRMED_RELATED' or 'DISMISSED'.")

    now_utc = get_now()
    rel.review_status = body.review_status
    rel.reviewed_by_id = user.id
    rel.reviewed_at = now_utc
    if body.resolution_reason:
        rel.resolution_reason = body.resolution_reason

    if body.review_status == "DISMISSED":
        rel.alert_status = "RESOLVED"
        rel.resolved_at = now_utc

    db.commit()
    return {"ok": True, "review_status": rel.review_status, "alert_status": rel.alert_status}
