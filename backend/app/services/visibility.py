"""
Cross-bureau visibility and confidentiality policy enforcement.

Applies strict data protection:
- Responsible Bureau / Central Admin: Full access to complaint and complainant details.
- Cross-Bureau Ordinary Confidentiality: Shared metadata only (category, status, dates, bureau).
- Cross-Bureau High Confidentiality: Masked down to Case ID, Institution, and Bureau only.
- Restricted remarks & restricted history events are strictly stripped before serialization.
"""
from typing import Any
from ..models import CaseHistory, ComplaintCase, User, UserBureauAssignment, UserRegionAssignment


def is_central_admin(user: User) -> bool:
    return user.role == "admin"


def get_user_bureau_ids(user: User) -> set[int]:
    """Returns set of bureau IDs the user has explicit assignment to."""
    if is_central_admin(user):
        return set()  # Admin has global scope
    return {a.bureau_id for a in user.bureau_assignments}


def get_user_regions(user: User) -> set[str]:
    """Returns set of regions assigned to user."""
    return {a.region for a in user.region_assignments}


def can_view_full_case(user: User, case: ComplaintCase) -> bool:
    """True if user is central admin or belongs to the case's current responsible bureau."""
    if is_central_admin(user):
        return True
    return case.current_bureau_id in get_user_bureau_ids(user)


def serialize_case_for_user(case: ComplaintCase, user: User) -> dict[str, Any]:
    """
    Serializes a ComplaintCase dictionary honoring confidentiality levels and user role scope.
    """
    has_full_access = can_view_full_case(user, case)

    # Base payload always includes identifying metadata
    data: dict[str, Any] = {
        "id": case.id,
        "case_id": case.case_id,
        "institution_id": case.institution_id,
        "institution_name": case.institution.name if case.institution else "",
        "permanent_id": case.institution.permanent_id if case.institution else "",
        "state": case.institution.state if case.institution else "",
        "region": case.institution.region if case.institution else "",
        "current_bureau_id": case.current_bureau_id,
        "current_bureau_code": case.current_bureau.code if case.current_bureau else "",
        "current_bureau_name": case.current_bureau.name if case.current_bureau else "",
        "confidentiality_level": case.confidentiality_level,
        "is_full_access": has_full_access,
    }

    if has_full_access:
        # Full view for responsible bureau and central admin
        data.update({
            "source_system": case.source_system,
            "source_record_id": case.source_record_id,
            "source_bureau_id": case.source_bureau_id,
            "source_bureau_code": case.source_bureau.code if case.source_bureau else "",
            "complainant_type": case.complainant_type,
            "complainant_name": case.complainant_name,
            "complainant_email": case.complainant_email,
            "complainant_phone": case.complainant_phone,
            "category": case.category,
            "subject": case.subject,
            "description": case.description,
            "received_date": case.received_date.isoformat(),
            "created_at": case.created_at.isoformat(),
            "updated_at": case.updated_at.isoformat(),
            "status": case.status,
            "assigned_officer_id": case.assigned_officer_id,
            "assigned_officer_name": case.assigned_officer.name if case.assigned_officer else None,
            "last_action": case.last_action,
            "next_action": case.next_action,
            "expected_disposal_date": case.expected_disposal_date.isoformat() if case.expected_disposal_date else None,
            "effective_deadline": case.effective_deadline.isoformat() if case.effective_deadline else None,
            "sla_status": case.sla_status,
        })
    elif case.confidentiality_level == "HIGH":
        # Cross-bureau view for HIGH confidentiality: Strictly Case ID, Institution, and Bureau only
        data.update({
            "category": "[CONFIDENTIAL - HIGH]",
            "subject": "[CONFIDENTIAL GRIEVANCE DETAILS RESTRICTED]",
            "description": "Details restricted under High Confidentiality policy. Handled exclusively by responsible bureau.",
            "complainant_type": "[RESTRICTED]",
            "complainant_name": None,
            "complainant_email": None,
            "complainant_phone": None,
            "status": "[RESTRICTED]",
            "received_date": None,
            "created_at": None,
            "effective_deadline": None,
            "sla_status": "[RESTRICTED]",
            "last_action": None,
            "next_action": None,
        })
    else:
        # Cross-bureau view for ORDINARY confidentiality: Shared metadata permitted
        data.update({
            "source_system": case.source_system,
            "source_record_id": None,  # Redacted
            "source_bureau_id": case.source_bureau_id,
            "source_bureau_code": case.source_bureau.code if case.source_bureau else "",
            "complainant_type": case.complainant_type,
            "complainant_name": None,   # Redacted
            "complainant_email": None,  # Redacted
            "complainant_phone": None,  # Redacted
            "category": case.category,
            "subject": case.subject,
            "description": "[Description restricted to responsible bureau]",
            "received_date": case.received_date.isoformat(),
            "created_at": case.created_at.isoformat(),
            "updated_at": case.updated_at.isoformat(),
            "status": case.status,
            "assigned_officer_id": None,
            "assigned_officer_name": None,
            "last_action": case.last_action,
            "next_action": case.next_action,
            "expected_disposal_date": None,
            "effective_deadline": case.effective_deadline.isoformat() if case.effective_deadline else None,
            "sla_status": case.sla_status,
        })

    return data


def filter_case_history_for_user(case: ComplaintCase, user: User) -> list[dict[str, Any]]:
    """
    Filters case history entries according to user role and confidentiality level.
    Never exposes restricted remarks to cross-bureau users.
    """
    has_full_access = can_view_full_case(user, case)

    # For High confidentiality cases, cross-bureau users see no history events
    if not has_full_access and case.confidentiality_level == "HIGH":
        return []

    results: list[dict[str, Any]] = []
    for h in case.history_entries:
        if is_central_admin(user):
            # Admin sees all events including CENTRAL_ONLY
            visible = True
        elif has_full_access:
            # Responsible bureau sees CROSS_BUREAU_SUMMARY and RESPONSIBLE_BUREAU
            visible = h.event_visibility in ("CROSS_BUREAU_SUMMARY", "RESPONSIBLE_BUREAU")
        else:
            # Cross-bureau sees only CROSS_BUREAU_SUMMARY
            visible = h.event_visibility == "CROSS_BUREAU_SUMMARY"

        if visible:
            results.append({
                "id": h.id,
                "case_id": h.case_id,
                "action_type": h.action_type,
                "actor_name": h.actor_name if (has_full_access or is_central_admin(user)) else "Officer",
                "previous_status": h.previous_status,
                "new_status": h.new_status,
                "source_bureau_code": h.source_bureau.code if h.source_bureau else None,
                "destination_bureau_code": h.destination_bureau.code if h.destination_bureau else None,
                "action_summary": h.action_summary,
                # Restricted remarks never exposed cross-bureau
                "restricted_remarks": h.restricted_remarks if has_full_access else None,
                "event_visibility": h.event_visibility,
                "created_at": h.created_at.isoformat(),
            })

    return results
