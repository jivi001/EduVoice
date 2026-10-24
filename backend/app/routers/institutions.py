"""
Institution Registry Router.

Provides institution search, registration, and 360-degree cross-bureau case profiles.
"""
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..clock import get_now
from ..db import get_db
from ..models import Institution, User
from ..security import get_current_user
from ..services.visibility import serialize_case_for_user

router = APIRouter(prefix="/institutions", tags=["institutions"])


class InstitutionCreateIn(BaseModel):
    permanent_id: str = Field(min_length=3, max_length=64)
    name: str = Field(min_length=2, max_length=255)
    state: str = Field(min_length=2, max_length=100)
    region: str = Field(min_length=2, max_length=64)
    address: str | None = None


@router.get("")
def list_institutions(
    q: str | None = Query(None, description="Search by Permanent ID or Name"),
    region: str | None = Query(None),
    state: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Institution).filter(Institution.is_active == True)
    if q:
        term = f"%{q.strip()}%"
        query = query.filter(or_(Institution.permanent_id.ilike(term), Institution.name.ilike(term)))
    if region:
        query = query.filter(Institution.region == region)
    if state:
        query = query.filter(Institution.state == state)

    institutions = query.order_by(Institution.name.asc()).limit(100).all()
    return [
        {
            "id": inst.id,
            "permanent_id": inst.permanent_id,
            "name": inst.name,
            "state": inst.state,
            "region": inst.region,
            "address": inst.address,
            "created_at": inst.created_at.isoformat(),
        }
        for inst in institutions
    ]


@router.post("", status_code=201)
def create_institution(
    body: InstitutionCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "admin":
        raise HTTPException(403, "Only Central Administrators can register new institutions.")

    perm_id = body.permanent_id.strip()
    existing = db.query(Institution).filter_by(permanent_id=perm_id).first()
    if existing:
        raise HTTPException(409, f"Institution with Permanent ID '{perm_id}' already exists.")

    now_utc = get_now()
    inst = Institution(
        permanent_id=perm_id,
        name=body.name.strip(),
        state=body.state.strip(),
        region=body.region.strip(),
        address=body.address.strip() if body.address else None,
        created_at=now_utc,
        updated_at=now_utc,
    )
    db.add(inst)
    db.commit()
    db.refresh(inst)

    return {
        "id": inst.id,
        "permanent_id": inst.permanent_id,
        "name": inst.name,
        "state": inst.state,
        "region": inst.region,
        "address": inst.address,
    }


@router.get("/{id}")
def get_institution_profile(
    id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    inst = db.query(Institution).filter_by(id=id).first()
    if not inst:
        raise HTTPException(404, "Institution not found.")

    cases = [serialize_case_for_user(c, user) for c in inst.cases]
    bureau_counts: dict[str, int] = {}
    for c in cases:
        bcode = c.get("current_bureau_code") or "Unknown"
        bureau_counts[bcode] = bureau_counts.get(bcode, 0) + 1

    return {
        "id": inst.id,
        "permanent_id": inst.permanent_id,
        "name": inst.name,
        "state": inst.state,
        "region": inst.region,
        "address": inst.address,
        "is_active": inst.is_active,
        "total_cases": len(cases),
        "bureau_breakdown": bureau_counts,
        "cases": cases,
    }
