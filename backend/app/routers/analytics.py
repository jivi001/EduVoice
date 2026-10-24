"""
Analytics, Dashboard Metrics, and MIS Reports Router.
"""
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ComplaintCase, Institution, User
from ..security import get_current_user
from ..services.reports import export_cases_to_safe_csv, generate_mis_reports
from ..services.visibility import get_user_bureau_ids, is_central_admin

router = APIRouter(tags=["analytics"])


@router.get("/dashboard/metrics")
def get_dashboard_metrics(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mis = generate_mis_reports(db, user)
    return mis["metrics"]


@router.get("/reports/mis")
def get_mis_reports(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return generate_mis_reports(db, user)


@router.get("/reports/export/cases")
def export_cases(
    bureau_id: int | None = Query(None),
    region: str | None = Query(None),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(ComplaintCase).join(Institution, ComplaintCase.institution_id == Institution.id)

    if not is_central_admin(user):
        allowed_bids = get_user_bureau_ids(user)
        query = query.filter(ComplaintCase.current_bureau_id.in_(allowed_bids))
    elif bureau_id:
        query = query.filter(ComplaintCase.current_bureau_id == bureau_id)

    if region:
        query = query.filter(Institution.region == region)
    if status:
        query = query.filter(ComplaintCase.status == status)

    cases = query.order_by(ComplaintCase.received_date.desc()).all()
    csv_text = export_cases_to_safe_csv(cases, user)

    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=aicte_complaints_export.csv"},
    )
