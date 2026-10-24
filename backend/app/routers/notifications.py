"""
Persistent Notifications Router.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..clock import get_now
from ..db import get_db
from ..models import Notification, User
from ..security import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    notifs = (
        db.query(Notification)
        .filter_by(recipient_id=user.id)
        .order_by(Notification.created_at.desc())
        .limit(100)
        .all()
    )
    unread_count = sum(1 for n in notifs if n.status == "UNREAD")

    return {
        "unread_count": unread_count,
        "notifications": [
            {
                "id": n.id,
                "alert_type": n.alert_type,
                "title": n.title,
                "message": n.message,
                "status": n.status,
                "related_case_id": n.related_case_id,
                "related_case_number": n.related_case.case_id if n.related_case else None,
                "created_at": n.created_at.isoformat(),
                "acknowledged_at": n.acknowledged_at.isoformat() if n.acknowledged_at else None,
                "resolved_at": n.resolved_at.isoformat() if n.resolved_at else None,
            }
            for n in notifs
        ],
    }


@router.post("/{id}/acknowledge")
def acknowledge_notification(
    id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    notif = db.query(Notification).filter_by(id=id, recipient_id=user.id).first()
    if not notif:
        raise HTTPException(404, "Notification not found.")

    notif.status = "ACKNOWLEDGED"
    notif.acknowledged_at = get_now()
    db.commit()

    return {"ok": True, "status": notif.status}


@router.post("/acknowledge-all")
def acknowledge_all(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    now_utc = get_now()
    unread = (
        db.query(Notification)
        .filter(Notification.recipient_id == user.id, Notification.status == "UNREAD")
        .all()
    )
    for n in unread:
        n.status = "ACKNOWLEDGED"
        n.acknowledged_at = now_utc

    db.commit()
    return {"ok": True, "count": len(unread)}
