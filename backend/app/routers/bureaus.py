"""
Bureaus and Cells Router.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Bureau, User, UserBureauAssignment
from ..security import get_current_user

router = APIRouter(prefix="/bureaus", tags=["bureaus"])


@router.get("")
def list_bureaus(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    bureaus = db.query(Bureau).filter_by(is_active=True).all()
    results = []
    for b in bureaus:
        officers = (
            db.query(User)
            .join(UserBureauAssignment)
            .filter(UserBureauAssignment.bureau_id == b.id, User.status == "active")
            .all()
        )
        results.append({
            "id": b.id,
            "code": b.code,
            "name": b.name,
            "supervisor_id": b.supervisor_id,
            "supervisor_name": b.supervisor.name if b.supervisor else None,
            "officer_count": len(officers),
            "officers": [{"id": o.id, "name": o.name, "username": o.username} for o in officers],
        })
    return results
