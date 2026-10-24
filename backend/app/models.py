"""
Database schema.

Includes:
1. Core Identity & User authentication (User, UserBureauAssignment, UserRegionAssignment)
2. SIH26264 Institution Complaint Monitoring & Tracking (Institution, Bureau, ComplaintCase, CaseHistory,
   CaseRelationship, SLAConfig, Notification, ImportBatch, ImportRow, ImportIssue, AuditEvent, CaseNumberSequence)
3. Preserved legacy EduVoice models for backwards compatibility.
"""
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


# ==============================================================================
# 1. Identity & Permissions
# ==============================================================================

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    # Roles: admin (Central Administrator) | officer (Bureau Officer) |
    # supervisor (Bureau/Regional Supervisor) | auditor (Read-Only Auditor) | student | teacher
    role: Mapped[str] = mapped_column(String(32))
    password_hash: Mapped[str] = mapped_column(String(255))
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(24), default="active")
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)

    bureau_assignments: Mapped[list["UserBureauAssignment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    region_assignments: Mapped[list["UserRegionAssignment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class EmailToken(Base):
    """One-time, short-lived tokens for email verification links."""
    __tablename__ = "email_tokens"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    purpose: Mapped[str] = mapped_column(String(24))
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class UserBureauAssignment(Base):
    """Explicit membership linking a user to one or more bureaus."""
    __tablename__ = "user_bureau_assignments"
    __table_args__ = (UniqueConstraint("user_id", "bureau_id", name="uq_user_bureau"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    bureau_id: Mapped[int] = mapped_column(ForeignKey("bureaus.id"), index=True)
    role_in_bureau: Mapped[str] = mapped_column(String(32), default="officer")  # officer | supervisor

    user: Mapped["User"] = relationship(back_populates="bureau_assignments")
    bureau: Mapped["Bureau"] = relationship()


class UserRegionAssignment(Base):
    """Explicit membership linking a user to one or more regions."""
    __tablename__ = "user_region_assignments"
    __table_args__ = (UniqueConstraint("user_id", "region", name="uq_user_region"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    region: Mapped[str] = mapped_column(String(64), index=True)

    user: Mapped["User"] = relationship(back_populates="region_assignments")


# ==============================================================================
# 2. Institution Registry & Bureaus
# ==============================================================================

class Institution(Base):
    """Authoritative registry of AICTE approved technical institutions."""
    __tablename__ = "institutions"

    id: Mapped[int] = mapped_column(primary_key=True)
    permanent_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    state: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    region: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)

    cases: Mapped[list["ComplaintCase"]] = relationship(back_populates="institution")


class Bureau(Base):
    """Internal AICTE Bureau or Cell (e.g. RB, PGRC, Approval Bureau)."""
    __tablename__ = "bureaus"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    supervisor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    supervisor: Mapped["User | None"] = relationship(foreign_keys=[supervisor_id])


# ==============================================================================
# 3. Case Number Sequence (Concurrency-Safe Annual Allocator)
# ==============================================================================

class CaseNumberSequence(Base):
    """Tracks annual sequential counter for AICTE/YYYY/NNNNNN case IDs."""
    __tablename__ = "case_number_sequences"

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


# ==============================================================================
# 4. Complaint Case & Lifecycle
# ==============================================================================

class ComplaintCase(Base):
    """Core institution-related grievance/complaint record."""
    __tablename__ = "complaint_cases"
    __table_args__ = (
        UniqueConstraint("source_system", "source_record_id", name="uq_source_system_record"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"), index=True, nullable=False)

    source_system: Mapped[str] = mapped_column(String(64), default="MANUAL", index=True)
    source_record_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)

    source_bureau_id: Mapped[int] = mapped_column(ForeignKey("bureaus.id"), nullable=False)
    current_bureau_id: Mapped[int] = mapped_column(ForeignKey("bureaus.id"), index=True, nullable=False)

    complainant_type: Mapped[str] = mapped_column(String(32), default="Student")  # Student | Faculty | Other Stakeholder
    complainant_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    complainant_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    complainant_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)

    category: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    confidentiality_level: Mapped[str] = mapped_column(String(16), default="ORDINARY", index=True)  # ORDINARY | HIGH

    received_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Status: Pending | Under Process | Transferred | Escalated | Disposed
    status: Mapped[str] = mapped_column(String(24), default="Pending", index=True, nullable=False)
    assigned_officer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)

    last_action: Mapped[str | None] = mapped_column(String(255), nullable=True)
    next_action: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expected_disposal_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # SLA and deadline tracking
    imported_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    imported_due_date_provenance: Mapped[str | None] = mapped_column(String(120), nullable=True)
    imported_due_date_trusted: Mapped[bool] = mapped_column(Boolean, default=False)
    effective_deadline: Mapped[datetime | None] = mapped_column(DateTime, index=True, nullable=True)
    # SLA Status: ON_TRACK | APPROACHING | OVERDUE | NO_SLA_CONFIGURED
    sla_status: Mapped[str] = mapped_column(String(24), default="NO_SLA_CONFIGURED", index=True)

    institution: Mapped["Institution"] = relationship(back_populates="cases")
    source_bureau: Mapped["Bureau"] = relationship(foreign_keys=[source_bureau_id])
    current_bureau: Mapped["Bureau"] = relationship(foreign_keys=[current_bureau_id])
    assigned_officer: Mapped["User | None"] = relationship(foreign_keys=[assigned_officer_id])
    history_entries: Mapped[list["CaseHistory"]] = relationship(
        back_populates="case", cascade="all, delete-orphan", order_by="CaseHistory.created_at.asc()"
    )


class CaseHistory(Base):
    """Complete, append-only audit trail for every action taken on a case."""
    __tablename__ = "case_histories"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("complaint_cases.id"), index=True, nullable=False)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_name: Mapped[str] = mapped_column(String(120), nullable=False)
    action_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)

    previous_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(24), nullable=True)

    source_bureau_id: Mapped[int | None] = mapped_column(ForeignKey("bureaus.id"), nullable=True)
    destination_bureau_id: Mapped[int | None] = mapped_column(ForeignKey("bureaus.id"), nullable=True)

    previous_officer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    new_officer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    action_summary: Mapped[str] = mapped_column(Text, nullable=False)
    restricted_remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Visibility: CROSS_BUREAU_SUMMARY | RESPONSIBLE_BUREAU | CENTRAL_ONLY
    event_visibility: Mapped[str] = mapped_column(String(32), default="CROSS_BUREAU_SUMMARY", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)

    case: Mapped["ComplaintCase"] = relationship(back_populates="history_entries")
    actor: Mapped["User | None"] = relationship(foreign_keys=[actor_id])
    source_bureau: Mapped["Bureau | None"] = relationship(foreign_keys=[source_bureau_id])
    destination_bureau: Mapped["Bureau | None"] = relationship(foreign_keys=[destination_bureau_id])


# ==============================================================================
# 5. Cross-Bureau Overlap & Case Relationships
# ==============================================================================

class CaseRelationship(Base):
    """Canonical pairing of two related or overlapping complaint cases."""
    __tablename__ = "case_relationships"
    __table_args__ = (
        CheckConstraint("case_id_1 < case_id_2", name="ck_ordered_case_pair"),
        UniqueConstraint("case_id_1", "case_id_2", name="uq_case_pair"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id_1: Mapped[int] = mapped_column(ForeignKey("complaint_cases.id"), index=True, nullable=False)
    case_id_2: Mapped[int] = mapped_column(ForeignKey("complaint_cases.id"), index=True, nullable=False)

    # CROSS_BUREAU_OVERLAP | POTENTIAL_DUPLICATE | CONFIRMED_RELATED
    relationship_type: Mapped[str] = mapped_column(String(32), default="CROSS_BUREAU_OVERLAP", index=True)
    # PENDING_REVIEW | CONFIRMED_RELATED | DISMISSED
    review_status: Mapped[str] = mapped_column(String(32), default="PENDING_REVIEW", index=True)
    # OPEN | ACKNOWLEDGED | RESOLVED
    alert_status: Mapped[str] = mapped_column(String(24), default="OPEN", index=True)

    matching_reason: Mapped[str] = mapped_column(Text, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    resolution_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    case_1: Mapped["ComplaintCase"] = relationship(foreign_keys=[case_id_1])
    case_2: Mapped["ComplaintCase"] = relationship(foreign_keys=[case_id_2])
    reviewed_by: Mapped["User | None"] = relationship(foreign_keys=[reviewed_by_id])


# ==============================================================================
# 6. SLA Configuration & Notifications
# ==============================================================================

class SLAConfig(Base):
    """Configurable SLA timelines by bureau or category."""
    __tablename__ = "sla_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    bureau_id: Mapped[int | None] = mapped_column(ForeignKey("bureaus.id"), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    max_calendar_days: Mapped[int] = mapped_column(Integer, default=30)
    approaching_threshold_days: Mapped[int] = mapped_column(Integer, default=5)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Notification(Base):
    """Persistent, deduplicated alerts for officers and administrators."""
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    alert_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)

    related_case_id: Mapped[int | None] = mapped_column(ForeignKey("complaint_cases.id"), nullable=True)
    related_relationship_id: Mapped[int | None] = mapped_column(ForeignKey("case_relationships.id"), nullable=True)

    dedup_key: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # UNREAD | READ | ACKNOWLEDGED | RESOLVED
    status: Mapped[str] = mapped_column(String(24), default="UNREAD", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    recipient: Mapped["User"] = relationship()
    related_case: Mapped["ComplaintCase | None"] = relationship()
    related_relationship: Mapped["CaseRelationship | None"] = relationship()


# ==============================================================================
# 7. CSV Ingestion Tracking
# ==============================================================================

class ImportBatch(Base):
    """Tracks CSV upload ingestion sessions."""
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_system: Mapped[str] = mapped_column(String(64), nullable=False)
    initiating_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)

    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    accepted_rows: Mapped[int] = mapped_column(Integer, default=0)
    rejected_rows: Mapped[int] = mapped_column(Integer, default=0)
    review_rows: Mapped[int] = mapped_column(Integer, default=0)

    # PROCESSING | COMPLETED | PARTIAL_SUCCESS | FAILED
    status: Mapped[str] = mapped_column(String(24), default="PROCESSING")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    rows: Mapped[list["ImportRow"]] = relationship(back_populates="batch", cascade="all, delete-orphan")


class ImportRow(Base):
    """Row-level tracking and audit for CSV imports."""
    __tablename__ = "import_rows"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), index=True, nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_record_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    permanent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # ACCEPTED | REJECTED | NEEDS_REVIEW
    status: Mapped[str] = mapped_column(String(24), default="ACCEPTED")
    validation_errors: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    created_case_id: Mapped[int | None] = mapped_column(ForeignKey("complaint_cases.id"), nullable=True)
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    batch: Mapped["ImportBatch"] = relationship(back_populates="rows")


class ImportIssue(Base):
    """Review queue for ambiguous institutions, conflicts, and duplicate reviews."""
    __tablename__ = "import_issues"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), index=True, nullable=False)
    row_id: Mapped[int] = mapped_column(ForeignKey("import_rows.id"), nullable=False)
    issue_type: Mapped[str] = mapped_column(String(48), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # PENDING | RESOLVED | IGNORED
    status: Mapped[str] = mapped_column(String(24), default="PENDING", index=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# ==============================================================================
# 8. Security Audit Logs
# ==============================================================================

class AuditEvent(Base):
    """Security and compliance audit log for sensitive operations."""
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_username: Mapped[str] = mapped_column(String(120), nullable=False)
    event_type: Mapped[str] = mapped_column(String(48), index=True, nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(48), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)


# ==============================================================================
# 9. Legacy EduVoice Models (Preserved)
# ==============================================================================

class Teacher(Base):
    __tablename__ = "teachers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class Subject(Base):
    __tablename__ = "subjects"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(120))


class Assignment(Base):
    __tablename__ = "assignments"
    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    semester: Mapped[str] = mapped_column(String(20))
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)

    teacher: Mapped[Teacher] = relationship()
    subject: Mapped[Subject] = relationship()


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("student_id", "assignment_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"))


class Issuance(Base):
    __tablename__ = "issuances"
    __table_args__ = (UniqueConstraint("student_id", "assignment_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"))


class SpentToken(Base):
    __tablename__ = "spent_tokens"
    nonce_hash: Mapped[str] = mapped_column(String(64), primary_key=True)


class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"), index=True)
    clarity: Mapped[int] = mapped_column(Integer)
    pace: Mapped[int] = mapped_column(Integer)
    examples: Mapped[int] = mapped_column(Integer)
    doubts: Mapped[int] = mapped_column(Integer)
    overall: Mapped[int] = mapped_column(Integer)
    went_well: Mapped[str] = mapped_column(Text, default="")
    to_improve: Mapped[str] = mapped_column(Text, default="")
    sentiment: Mapped[str] = mapped_column(String(16), default="neutral")
    flags: Mapped[list] = mapped_column(JSON, default=list)
    moderation: Mapped[str] = mapped_column(String(16), default="visible")
    day: Mapped[date] = mapped_column(Date)
