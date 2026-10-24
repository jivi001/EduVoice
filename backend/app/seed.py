"""
Development Seed Script for SIH26264 AICTE Case Monitoring & Overlap Tracking.

Run:  python -m app.seed
Idempotent: safe to run multiple times.
"""
from datetime import date, timedelta
from sqlalchemy import select

from .clock import get_current_date, get_now
from .config import settings
from .db import Base, SessionLocal, engine
from .models import (
    Assignment,
    Bureau,
    CaseHistory,
    ComplaintCase,
    Enrollment,
    Institution,
    SLAConfig,
    Subject,
    Teacher,
    User,
    UserBureauAssignment,
    UserRegionAssignment,
)
from .security import hash_password
from .services.case_number import generate_case_id
from .services.overlap import detect_cross_bureau_overlaps_for_institution
from .services.sla import calculate_effective_deadline


def seed(db) -> None:
    now_utc = get_now()
    today = get_current_date()

    # 1. Seed Bureaus
    bureaus_data = [
        ("RB", "Regulation Bureau"),
        ("PGRC", "Public Grievance Redressal Cell"),
        ("AB", "Approval Bureau"),
    ]
    bureau_map: dict[str, Bureau] = {}
    for code, name in bureaus_data:
        b = db.query(Bureau).filter_by(code=code).first()
        if not b:
            b = Bureau(code=code, name=name, is_active=True, created_at=now_utc)
            db.add(b)
            db.flush()
        bureau_map[code] = b

    # 2. Seed Users
    users_data = [
        ("admin", "Central Administrator", "admin", "admin123"),
        ("officer_pgrc", "PGRC Officer Sharma", "officer", "officer123"),
        ("officer_rb", "RB Officer Verma", "officer", "officer123"),
        ("officer_ab", "AB Officer Rao", "officer", "officer123"),
        ("supervisor_rb", "RB Supervisor Dr. Gupta", "supervisor", "super123"),
        ("auditor", "AICTE Compliance Auditor", "auditor", "auditor123"),
        ("kumar", "Dr. Kumar", "teacher", "teacher123"),
        ("devi", "Prof. Devi", "teacher", "teacher123"),
    ] + [
        (f"s{i:02d}", f"Student {i:02d}", "student", "student123") for i in range(1, 9)
    ]
    user_map: dict[str, User] = {}
    for username, name, role, pwd in users_data:
        u = db.query(User).filter_by(username=username).first()
        if not u:
            u = User(
                username=username,
                name=name,
                role=role,
                password_hash=hash_password(pwd),
                status="active",
                email=f"{username}@aicte-india.org",
                email_verified=True,
            )
            db.add(u)
            db.flush()
        user_map[username] = u

    # Link supervisor to RB
    bureau_map["RB"].supervisor_id = user_map["supervisor_rb"].id

    # 3. User Bureau Assignments
    assignments = [
        ("officer_pgrc", "PGRC", "officer"),
        ("officer_rb", "RB", "officer"),
        ("officer_ab", "AB", "officer"),
        ("supervisor_rb", "RB", "supervisor"),
    ]
    for uname, bcode, roletype in assignments:
        u = user_map[uname]
        b = bureau_map[bcode]
        existing_assign = (
            db.query(UserBureauAssignment)
            .filter_by(user_id=u.id, bureau_id=b.id)
            .first()
        )
        if not existing_assign:
            db.add(UserBureauAssignment(user_id=u.id, bureau_id=b.id, role_in_bureau=roletype))

    # Regional assignment for supervisor
    if not db.query(UserRegionAssignment).filter_by(user_id=user_map["supervisor_rb"].id).first():
        db.add(UserRegionAssignment(user_id=user_map["supervisor_rb"].id, region="Northern"))

    # Legacy Course data (Preserved for compatibility)
    if not db.query(Teacher).first():
        t1 = user_map["kumar"]
        t2 = user_map["devi"]
        teachers = [Teacher(name=t1.name, user_id=t1.id), Teacher(name=t2.name, user_id=t2.id)]
        subjects = [Subject(code="NS101", name="Network Security"), Subject(code="ML201", name="Machine Learning")]
        db.add_all([*teachers, *subjects])
        db.flush()
        assignments_list = [
            Assignment(teacher_id=teachers[0].id, subject_id=subjects[0].id, semester="Sem 5"),
            Assignment(teacher_id=teachers[1].id, subject_id=subjects[1].id, semester="Sem 5"),
        ]
        db.add_all(assignments_list)
        db.flush()
        students = [user_map[f"s{i:02d}"] for i in range(1, 9)]
        db.add_all([Enrollment(student_id=s.id, assignment_id=a.id) for s in students for a in assignments_list])
        db.flush()

    # 4. Institutions
    institutions_data = [
        ("1-10928374", "Apex Institute of Technology", "Delhi", "Northern", "Sector 12, Dwarka, New Delhi"),
        ("1-20938475", "Western College of Engineering & Tech", "Maharashtra", "Western", "Shivajinagar, Pune, MH"),
        ("1-30948576", "Bangalore Science & Tech Institute", "Karnataka", "South-West", "Whitefield, Bangalore, KA"),
        ("1-40958677", "Eastern National Polytechnic", "West Bengal", "Eastern", "Salt Lake, Sector V, Kolkata, WB"),
    ]
    inst_map: dict[str, Institution] = {}
    for pid, name, state, region, addr in institutions_data:
        inst = db.query(Institution).filter_by(permanent_id=pid).first()
        if not inst:
            inst = Institution(
                permanent_id=pid,
                name=name,
                state=state,
                region=region,
                address=addr,
                is_active=True,
                created_at=now_utc,
                updated_at=now_utc,
            )
            db.add(inst)
            db.flush()
        inst_map[pid] = inst

    # 5. SLA Configurations
    if not db.query(SLAConfig).first():
        db.add_all([
            SLAConfig(max_calendar_days=30, approaching_threshold_days=5),
            SLAConfig(category="Capitation Fee", max_calendar_days=15, approaching_threshold_days=3),
            SLAConfig(category="Ragging", max_calendar_days=7, approaching_threshold_days=2),
        ])
        db.flush()

    # 6. Seed Demonstration Cases (if no cases exist)
    if not db.query(ComplaintCase).first():
        # Case 1: PGRC on Apex Institute (Active)
        inst_apex = inst_map["1-10928374"]
        date_1 = today - timedelta(days=10)
        c1_id = generate_case_id(db, date_1)
        deadline_1, sla_1 = calculate_effective_deadline(
            db, date_1, bureau_map["PGRC"].id, "Capitation Fee"
        )
        case_1 = ComplaintCase(
            case_id=c1_id,
            institution_id=inst_apex.id,
            source_system="PGRC_PORTAL",
            source_record_id="PGRC-2026-0811",
            source_bureau_id=bureau_map["PGRC"].id,
            current_bureau_id=bureau_map["PGRC"].id,
            complainant_type="Student",
            complainant_name="Aman Verma",
            complainant_email="aman.v@example.com",
            complainant_phone="+919876543210",
            category="Capitation Fee",
            subject="Demand for unauthorized development fee prior to semester exam",
            description="College accounts office demanded mandatory ₹45,000 extra fee without receipt.",
            confidentiality_level="ORDINARY",
            received_date=date_1,
            created_at=now_utc - timedelta(days=10),
            updated_at=now_utc - timedelta(days=10),
            status="Pending",
            assigned_officer_id=user_map["officer_pgrc"].id,
            effective_deadline=deadline_1,
            sla_status=sla_1,
            last_action="Received from Public Grievance Portal",
        )
        db.add(case_1)
        db.flush()

        db.add(
            CaseHistory(
                case_id=case_1.id,
                actor_id=user_map["officer_pgrc"].id,
                actor_name=user_map["officer_pgrc"].name,
                action_type="CREATED",
                new_status="Pending",
                source_bureau_id=bureau_map["PGRC"].id,
                destination_bureau_id=bureau_map["PGRC"].id,
                action_summary="Case imported from PGRC grievance portal.",
                event_visibility="CROSS_BUREAU_SUMMARY",
                created_at=now_utc - timedelta(days=10),
            )
        )

        # Case 2: RB on Apex Institute (Active - triggers cross-bureau overlap with Case 1!)
        date_2 = today - timedelta(days=6)
        c2_id = generate_case_id(db, date_2)
        deadline_2, sla_2 = calculate_effective_deadline(
            db, date_2, bureau_map["RB"].id, "Infrastructure Deficiency"
        )
        case_2 = ComplaintCase(
            case_id=c2_id,
            institution_id=inst_apex.id,
            source_system="RB_INSPECTION",
            source_record_id="RB-2026-1044",
            source_bureau_id=bureau_map["RB"].id,
            current_bureau_id=bureau_map["RB"].id,
            complainant_type="Faculty",
            complainant_name="Prof. R. C. Mathur",
            complainant_email="rc.mathur@apex.edu",
            category="Infrastructure Deficiency",
            subject="Non-functional computing laboratory and lack of fire safety clearance",
            description="Computer labs have outdated, broken equipment. Fire NOC has not been renewed.",
            confidentiality_level="ORDINARY",
            received_date=date_2,
            created_at=now_utc - timedelta(days=6),
            updated_at=now_utc - timedelta(days=6),
            status="Under Process",
            assigned_officer_id=user_map["officer_rb"].id,
            effective_deadline=deadline_2,
            sla_status=sla_2,
            last_action="Show-cause notice drafted for management",
        )
        db.add(case_2)
        db.flush()

        db.add(
            CaseHistory(
                case_id=case_2.id,
                actor_id=user_map["officer_rb"].id,
                actor_name=user_map["officer_rb"].name,
                action_type="CREATED",
                new_status="Under Process",
                source_bureau_id=bureau_map["RB"].id,
                destination_bureau_id=bureau_map["RB"].id,
                action_summary="Inspection grievance registered in Regulation Bureau.",
                event_visibility="CROSS_BUREAU_SUMMARY",
                created_at=now_utc - timedelta(days=6),
            )
        )

        # Trigger overlap detection on Apex Institute!
        detect_cross_bureau_overlaps_for_institution(db, inst_apex.id)

        # Case 3: High Confidentiality Case in Western College
        inst_west = inst_map["1-20938475"]
        date_3 = today - timedelta(days=4)
        c3_id = generate_case_id(db, date_3)
        deadline_3, sla_3 = calculate_effective_deadline(
            db, date_3, bureau_map["RB"].id, "Financial Irregularity"
        )
        case_3 = ComplaintCase(
            case_id=c3_id,
            institution_id=inst_west.id,
            source_system="VIGILANCE_SECRETARIAT",
            source_record_id="VIG-2026-0099",
            source_bureau_id=bureau_map["RB"].id,
            current_bureau_id=bureau_map["RB"].id,
            complainant_type="Other Stakeholder",
            complainant_name="Whistleblower Anonymous",
            category="Financial Irregularity",
            subject="Misappropriation of central research grants",
            description="Highly sensitive inquiry into utilization of grants allocated for AI research centre.",
            confidentiality_level="HIGH",
            received_date=date_3,
            created_at=now_utc - timedelta(days=4),
            updated_at=now_utc - timedelta(days=4),
            status="Under Process",
            assigned_officer_id=user_map["officer_rb"].id,
            effective_deadline=deadline_3,
            sla_status=sla_3,
            last_action="Special inquiry committee instituted",
        )
        db.add(case_3)
        db.flush()

        db.add(
            CaseHistory(
                case_id=case_3.id,
                actor_id=user_map["officer_rb"].id,
                actor_name=user_map["officer_rb"].name,
                action_type="CREATED",
                new_status="Under Process",
                source_bureau_id=bureau_map["RB"].id,
                destination_bureau_id=bureau_map["RB"].id,
                action_summary="High confidentiality inquiry initiated.",
                restricted_remarks="Committee members: Joint Secretary, Director RB.",
                event_visibility="RESPONSIBLE_BUREAU",
                created_at=now_utc - timedelta(days=4),
            )
        )

        # Case 4: Disposed Case in Eastern National Polytechnic (Approval Bureau)
        inst_east = inst_map["1-40958677"]
        date_4 = today - timedelta(days=40)
        c4_id = generate_case_id(db, date_4)
        case_4 = ComplaintCase(
            case_id=c4_id,
            institution_id=inst_east.id,
            source_system="APPROVAL_PORTAL",
            source_record_id="AB-2026-0412",
            source_bureau_id=bureau_map["AB"].id,
            current_bureau_id=bureau_map["AB"].id,
            complainant_type="Student",
            category="Admission Irregularity",
            subject="Delayed intake approval for diploma batch 2026",
            description="Intake approval certificate was delayed due to document deficiency.",
            confidentiality_level="ORDINARY",
            received_date=date_4,
            created_at=now_utc - timedelta(days=40),
            updated_at=now_utc - timedelta(days=15),
            status="Disposed",
            effective_deadline=now_utc - timedelta(days=10),
            sla_status="DISPOSED",
            last_action="Resolved and intake certificate dispatched",
            expected_disposal_date=today - timedelta(days=15),
        )
        db.add(case_4)
        db.flush()

        db.add(
            CaseHistory(
                case_id=case_4.id,
                actor_id=user_map["officer_ab"].id,
                actor_name=user_map["officer_ab"].name,
                action_type="DISPOSED",
                previous_status="Under Process",
                new_status="Disposed",
                source_bureau_id=bureau_map["AB"].id,
                destination_bureau_id=bureau_map["AB"].id,
                action_summary="Case resolved: Intake approval certificate issued following document verification.",
                event_visibility="CROSS_BUREAU_SUMMARY",
                created_at=now_utc - timedelta(days=15),
            )
        )

    db.commit()


if __name__ == "__main__":
    if settings.is_production:
        raise SystemExit("Refusing to load demo data in production. Use: python -m app.bootstrap init")
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    print("AICTE SIH26264 Demonstration Seed Loaded Successfully!")
    print("Demo Logins:")
    print(" - admin / admin123 (Central Administrator)")
    print(" - officer_pgrc / officer123 (PGRC Officer)")
    print(" - officer_rb / officer123 (Regulation Bureau Officer)")
    print(" - officer_ab / officer123 (Approval Bureau Officer)")
    print(" - supervisor_rb / super123 (RB Supervisor)")
    print(" - auditor / auditor123 (Compliance Auditor)")
