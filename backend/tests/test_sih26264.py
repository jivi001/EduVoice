"""
Complete automated verification suite for SIH26264 MVP implementation.

Covers:
1. Institution Registry and Permanent ID uniqueness.
2. Case ID generation and annual sequence formatting (AICTE/YYYY/NNNNNN).
3. State machine validation (all permitted transitions, rejection of Pending -> Disposed, terminal Disposed).
4. Transfer & Acceptance workflow with receiving bureau authorization.
5. Escalation & Acknowledgement workflow.
6. Deterministic Overlap Detection (synchronous trigger, three-bureau scenario, auto-resolution on disposal).
7. Confidentiality filtering (Ordinary vs High confidentiality, restricted remarks redaction).
8. CSV Ingestion (row validation, registry conflict review, duplicate source ID rejection, 200 row cap).
9. SLA Deadlines and Injectable Clock (approaching deadline, overdue condition).
10. MIS Scoped Reports and Spreadsheet Formula Injection Prevention.
"""
from datetime import date, timedelta
import pytest
from starlette.testclient import TestClient

from app.clock import advance_time, get_now, reset_clock, set_fixed_time
from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import (
    Bureau,
    CaseHistory,
    CaseRelationship,
    ComplaintCase,
    Institution,
    Notification,
    SLAConfig,
    User,
    UserBureauAssignment,
)
from app.seed import seed
from app.services.case_number import generate_case_id
from app.services.lifecycle import (
    accept_transferred_case,
    acknowledge_escalation,
    dispose_case,
    escalate_case,
    transfer_case,
    update_case_status,
)
from app.services.overlap import detect_cross_bureau_overlaps_for_institution
from app.services.reports import export_cases_to_safe_csv, sanitize_csv_cell
from app.services.sla import calculate_effective_deadline, evaluate_case_sla_status
from app.services.visibility import filter_case_history_for_user, serialize_case_for_user


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    yield
    reset_clock()


@pytest.fixture
def client():
    return TestClient(app)


def login_as(client: TestClient, username: str, password: str = "officer123"):
    if username == "admin":
        password = "admin123"
    elif username == "supervisor_rb":
        password = "super123"
    r = client.post("/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, f"Login failed for {username}: {r.text}"
    return client


# ==============================================================================
# 1. Institution Registry & Case ID Generation
# ==============================================================================

def test_institution_creation_and_uniqueness(client: TestClient):
    login_as(client, "admin")
    # Duplicate creation should fail with 409
    res = client.post(
        "/institutions",
        json={
            "permanent_id": "1-10928374",  # Already seeded
            "name": "Duplicate College",
            "state": "Delhi",
            "region": "Northern",
        },
    )
    assert res.status_code == 409

    # Valid creation
    new_pid = "1-99988877"
    res2 = client.post(
        "/institutions",
        json={
            "permanent_id": new_pid,
            "name": "New Horizon Polytechnic",
            "state": "Karnataka",
            "region": "South-West",
        },
    )
    assert res2.status_code == 201
    assert res2.json()["permanent_id"] == new_pid


def test_case_id_annual_sequencing():
    with SessionLocal() as db:
        id_2026_1 = generate_case_id(db, date(2026, 1, 15))
        assert id_2026_1.startswith("AICTE/2026/")
        parts = id_2026_1.split("/")
        assert len(parts[2]) == 6  # 6-digit zero padded

        # Historical year
        id_2024 = generate_case_id(db, date(2024, 6, 1))
        assert id_2024.startswith("AICTE/2024/000001")


# ==============================================================================
# 2. Lifecycle State Machine & Authorization
# ==============================================================================

def test_lifecycle_direct_pending_to_disposed_rejected():
    with SessionLocal() as db:
        admin = db.query(User).filter_by(username="admin").first()
        b_pgrc = db.query(Bureau).filter_by(code="PGRC").first()
        inst = db.query(Institution).first()

        # Create fresh pending case
        case = ComplaintCase(
            case_id="AICTE/2026/999001",
            institution_id=inst.id,
            source_system="MANUAL",
            source_bureau_id=b_pgrc.id,
            current_bureau_id=b_pgrc.id,
            category="Test",
            subject="Test direct disposal",
            description="Testing state machine",
            received_date=date.today(),
            created_at=get_now(),
            updated_at=get_now(),
            status="Pending",
        )
        db.add(case)
        db.commit()

        # Direct disposal from Pending MUST raise ValueError
        with pytest.raises(ValueError, match="Direct disposal from Pending is not allowed"):
            update_case_status(db, case, "Disposed", admin, "Attempting direct disposal")


def test_disposed_is_terminal():
    with SessionLocal() as db:
        admin = db.query(User).filter_by(username="admin").first()
        disposed_case = db.query(ComplaintCase).filter_by(status="Disposed").first()
        assert disposed_case is not None

        with pytest.raises(ValueError, match="Disposed cases are terminal"):
            update_case_status(db, disposed_case, "Under Process", admin, "Reopen attempt")


def test_transfer_and_acceptance_workflow():
    with SessionLocal() as db:
        admin = db.query(User).filter_by(username="admin").first()
        officer_ab = db.query(User).filter_by(username="officer_ab").first()
        b_rb = db.query(Bureau).filter_by(code="RB").first()
        b_ab = db.query(Bureau).filter_by(code="AB").first()
        inst = db.query(Institution).first()

        case = ComplaintCase(
            case_id="AICTE/2026/999002",
            institution_id=inst.id,
            source_system="MANUAL",
            source_bureau_id=b_rb.id,
            current_bureau_id=b_rb.id,
            category="Curriculum",
            subject="Approval transfer test",
            description="Transfer test description",
            received_date=date.today(),
            created_at=get_now(),
            updated_at=get_now(),
            status="Under Process",
        )
        db.add(case)
        db.commit()

        # Transfer from RB to AB
        h1 = transfer_case(db, case, b_ab.id, admin, "Cross-domain approval required")
        assert case.status == "Transferred"
        assert case.current_bureau_id == b_ab.id
        assert h1.action_type == "TRANSFERRED"

        # Receiving bureau officer accepts transfer
        h2 = accept_transferred_case(db, case, officer_ab)
        assert case.status == "Under Process"
        assert h2.action_type == "TRANSFER_ACCEPTED"


def test_escalation_and_acknowledgement_workflow():
    with SessionLocal() as db:
        admin = db.query(User).filter_by(username="admin").first()
        supervisor = db.query(User).filter_by(username="supervisor_rb").first()
        b_rb = db.query(Bureau).filter_by(code="RB").first()
        inst = db.query(Institution).first()

        case = ComplaintCase(
            case_id="AICTE/2026/999003",
            institution_id=inst.id,
            source_system="MANUAL",
            source_bureau_id=b_rb.id,
            current_bureau_id=b_rb.id,
            category="Harassment",
            subject="Escalation test",
            description="Testing escalation",
            received_date=date.today(),
            created_at=get_now(),
            updated_at=get_now(),
            status="Under Process",
        )
        db.add(case)
        db.commit()

        # Escalate
        h_esc = escalate_case(db, case, admin, "Requires high-level intervention")
        assert case.status == "Escalated"
        assert h_esc.action_type == "ESCALATED"

        # Supervisor acknowledges escalation
        h_ack = acknowledge_escalation(db, case, supervisor, "Committee appointed")
        assert case.status == "Under Process"
        assert h_ack.action_type == "ESCALATION_ACKNOWLEDGED"


# ==============================================================================
# 3. Synchronous Cross-Bureau Overlap Detection & Auto-Resolution
# ==============================================================================

def test_three_bureau_overlap_and_disposal_auto_resolution():
    with SessionLocal() as db:
        admin = db.query(User).filter_by(username="admin").first()
        b_rb = db.query(Bureau).filter_by(code="RB").first()
        b_pgrc = db.query(Bureau).filter_by(code="PGRC").first()
        b_ab = db.query(Bureau).filter_by(code="AB").first()

        inst = Institution(
            permanent_id="1-55556666",
            name="Three Bureau Test Institute",
            state="Haryana",
            region="North-West",
            created_at=get_now(),
            updated_at=get_now(),
        )
        db.add(inst)
        db.flush()

        # Create Case in RB
        c_rb = ComplaintCase(
            case_id="AICTE/2026/999101",
            institution_id=inst.id,
            source_bureau_id=b_rb.id,
            current_bureau_id=b_rb.id,
            category="Inspection",
            subject="RB Case",
            description="RB complaint",
            received_date=date.today(),
            created_at=get_now(),
            updated_at=get_now(),
            status="Under Process",
        )
        db.add(c_rb)
        db.flush()

        # Create Case in PGRC
        c_pgrc = ComplaintCase(
            case_id="AICTE/2026/999102",
            institution_id=inst.id,
            source_bureau_id=b_pgrc.id,
            current_bureau_id=b_pgrc.id,
            category="Grievance",
            subject="PGRC Case",
            description="PGRC complaint",
            received_date=date.today(),
            created_at=get_now(),
            updated_at=get_now(),
            status="Under Process",
        )
        db.add(c_pgrc)
        db.flush()

        # Create Case in AB
        c_ab = ComplaintCase(
            case_id="AICTE/2026/999103",
            institution_id=inst.id,
            source_bureau_id=b_ab.id,
            current_bureau_id=b_ab.id,
            category="Approval",
            subject="AB Case",
            description="AB complaint",
            received_date=date.today(),
            created_at=get_now(),
            updated_at=get_now(),
            status="Under Process",
        )
        db.add(c_ab)
        db.flush()

        # Synchronous detection on this institution
        detect_cross_bureau_overlaps_for_institution(db, inst.id)

        # There should be 3 distinct open pairs: (RB, PGRC), (RB, AB), (PGRC, AB)
        rels = (
            db.query(CaseRelationship)
            .filter(
                CaseRelationship.relationship_type == "CROSS_BUREAU_OVERLAP",
                CaseRelationship.alert_status == "OPEN",
            )
            .join(ComplaintCase, CaseRelationship.case_id_1 == ComplaintCase.id)
            .filter(ComplaintCase.institution_id == inst.id)
            .all()
        )
        assert len(rels) == 3, f"Expected 3 active overlap pairs, got {len(rels)}"

        # Dispose Case AB: Only pairs involving AB should auto-resolve; (RB, PGRC) must remain OPEN!
        dispose_case(db, c_ab, admin, "AB inquiry completed")

        open_after_dispose = (
            db.query(CaseRelationship)
            .filter(
                CaseRelationship.relationship_type == "CROSS_BUREAU_OVERLAP",
                CaseRelationship.alert_status == "OPEN",
            )
            .join(ComplaintCase, CaseRelationship.case_id_1 == ComplaintCase.id)
            .filter(ComplaintCase.institution_id == inst.id)
            .all()
        )
        assert len(open_after_dispose) == 1, "Only (RB, PGRC) pair should remain open!"
        remaining = open_after_dispose[0]
        assert {remaining.case_id_1, remaining.case_id_2} == {c_rb.id, c_pgrc.id}


# ==============================================================================
# 4. Confidentiality Filtering & Restricted Remarks
# ==============================================================================

def test_high_confidentiality_cross_bureau_masking():
    with SessionLocal() as db:
        officer_pgrc = db.query(User).filter_by(username="officer_pgrc").first()
        officer_rb = db.query(User).filter_by(username="officer_rb").first()
        b_rb = db.query(Bureau).filter_by(code="RB").first()
        inst = db.query(Institution).first()

        # High confidentiality case in RB
        high_case = ComplaintCase(
            case_id="AICTE/2026/888001",
            institution_id=inst.id,
            source_bureau_id=b_rb.id,
            current_bureau_id=b_rb.id,
            complainant_type="Faculty",
            complainant_name="Whistleblower X",
            complainant_email="secret@example.com",
            category="Corruption",
            subject="High level corruption investigation",
            description="Highly sensitive text that must not be revealed cross-bureau",
            confidentiality_level="HIGH",
            received_date=date.today(),
            created_at=get_now(),
            updated_at=get_now(),
            status="Under Process",
        )
        db.add(high_case)
        db.flush()

        # Responsible bureau officer (RB) sees full details
        full_view = serialize_case_for_user(high_case, officer_rb)
        assert full_view["is_full_access"] is True
        assert full_view["complainant_name"] == "Whistleblower X"
        assert full_view["description"] == high_case.description

        # Cross-bureau officer (PGRC) sees ONLY Case ID, Institution, Bureau
        masked_view = serialize_case_for_user(high_case, officer_pgrc)
        assert masked_view["is_full_access"] is False
        assert masked_view["complainant_name"] is None
        assert masked_view["category"] == "[CONFIDENTIAL - HIGH]"
        assert "RESTRICTED" in masked_view["subject"]
        assert masked_view["current_bureau_code"] == "RB"


def test_restricted_remarks_never_leaked_cross_bureau():
    with SessionLocal() as db:
        officer_pgrc = db.query(User).filter_by(username="officer_pgrc").first()
        officer_rb = db.query(User).filter_by(username="officer_rb").first()
        b_rb = db.query(Bureau).filter_by(code="RB").first()
        inst = db.query(Institution).first()

        case = ComplaintCase(
            case_id="AICTE/2026/888002",
            institution_id=inst.id,
            source_bureau_id=b_rb.id,
            current_bureau_id=b_rb.id,
            category="Lab Equipment",
            subject="Defective lab equipment",
            description="Public description",
            confidentiality_level="ORDINARY",
            received_date=date.today(),
            created_at=get_now(),
            updated_at=get_now(),
            status="Under Process",
        )
        db.add(case)
        db.flush()

        h = CaseHistory(
            case_id=case.id,
            actor_id=officer_rb.id,
            actor_name=officer_rb.name,
            action_type="STATUS_CHANGE",
            action_summary="Action summary visible cross-bureau",
            restricted_remarks="TOP SECRET: Police investigation in progress",
            event_visibility="CROSS_BUREAU_SUMMARY",
            created_at=get_now(),
        )
        db.add(h)
        db.commit()

        # Filter for RB officer -> sees restricted remarks
        rb_history = filter_case_history_for_user(case, officer_rb)
        assert rb_history[0]["restricted_remarks"] == "TOP SECRET: Police investigation in progress"

        # Filter for PGRC officer -> restricted remarks is None!
        pgrc_history = filter_case_history_for_user(case, officer_pgrc)
        assert pgrc_history[0]["restricted_remarks"] is None


# ==============================================================================
# 5. CSV Ingestion, Validation & Duplicate Idempotency
# ==============================================================================

def test_csv_import_workflow_and_idempotency(client: TestClient):
    login_as(client, "admin")

    csv_data = """permanent_id,institution_name,bureau_code,source_system,source_record_id,category,subject,description,received_date,confidentiality_level,status
1-10928374,Apex Institute of Technology,PGRC,TEST_PORTAL,REC-9901,Ragging,Ragging complaint,Ragging reported in hostel,2026-02-01,ORDINARY,Pending
1-10928374,Wrong College Name,PGRC,TEST_PORTAL,REC-9902,Fees,Fee dispute,Excess fees charged,2026-02-01,ORDINARY,Pending
1-99999999,Unknown Institute,RB,TEST_PORTAL,REC-9903,Infra,Infra issue,No building,2026-02-01,ORDINARY,Pending
"""

    res = client.post(
        "/import/upload-raw",
        json={"csv_text": csv_data, "filename": "test_import.csv", "dry_run": False},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["accepted_rows"] == 1
    assert data["review_rows"] == 2  # Registry conflict & Unknown institution

    # Second import with SAME source_record_id: MUST NOT duplicate or overwrite!
    res_replay = client.post(
        "/import/upload-raw",
        json={"csv_text": csv_data, "filename": "test_import.csv", "dry_run": False},
    )
    assert res_replay.status_code == 200
    data_replay = res_replay.json()
    # Row 1 is now marked duplicate/review, not accepted!
    assert data_replay["accepted_rows"] == 0
    row_1 = next(r for r in data_replay["rows"] if r["row_number"] == 1)
    assert row_1["status"] == "NEEDS_REVIEW"
    assert "already exists" in row_1["errors"][0]


def test_csv_import_oversized_limit_rejection(client: TestClient):
    login_as(client, "admin")
    # Generate 201 rows
    header = "permanent_id,institution_name,bureau_code,category,subject,description,received_date\n"
    rows = "\n".join(
        f"1-10928374,Apex Institute of Technology,PGRC,Fee,Fee dispute,Excess fees,2026-01-01"
        for _ in range(201)
    )
    res = client.post(
        "/import/upload-raw",
        json={"csv_text": header + rows, "filename": "oversized.csv"},
    )
    assert res.status_code == 400
    assert "exceeds maximum limit of 200" in res.text


# ==============================================================================
# 6. SLA Precedence & Testable Clock
# ==============================================================================

def test_sla_overdue_with_injectable_clock():
    with SessionLocal() as db:
        inst = db.query(Institution).first()
        b_rb = db.query(Bureau).filter_by(code="RB").first()

        fixed_start = get_now()
        set_fixed_time(fixed_start)

        # 30 day SLA
        deadline, _ = calculate_effective_deadline(db, date.today(), b_rb.id, "General")
        case = ComplaintCase(
            case_id="AICTE/2026/777001",
            institution_id=inst.id,
            source_bureau_id=b_rb.id,
            current_bureau_id=b_rb.id,
            category="General",
            subject="Clock test case",
            description="Testing SLA clock",
            received_date=date.today(),
            created_at=fixed_start,
            updated_at=fixed_start,
            status="Under Process",
            effective_deadline=deadline,
        )
        db.add(case)
        db.commit()

        # At start: ON_TRACK
        assert evaluate_case_sla_status(case, threshold_days=5) == "ON_TRACK"

        # Advance time by 27 days -> within 5 days threshold -> APPROACHING
        advance_time(days=27)
        assert evaluate_case_sla_status(case, threshold_days=5) == "APPROACHING"

        # Advance time by another 5 days (total 32 days) -> past deadline -> OVERDUE
        advance_time(days=5)
        assert evaluate_case_sla_status(case, threshold_days=5) == "OVERDUE"

        reset_clock()


# ==============================================================================
# 7. Safe CSV Export Formula Injection Prevention
# ==============================================================================

def test_csv_export_formula_injection_sanitization():
    # Dangerous values starting with =, +, -, @
    assert sanitize_csv_cell("=1+1") == "'=1+1"
    assert sanitize_csv_cell("+cmd|' /C calc'!A0") == "'+cmd|' /C calc'!A0"
    assert sanitize_csv_cell("-SUM(A1:A10)") == "'-SUM(A1:A10)"
    assert sanitize_csv_cell("@excel_expr") == "'@excel_expr"
    assert sanitize_csv_cell("Normal text") == "Normal text"


# ==============================================================================
# 8. Dashboard Metrics & Scoped Reports Consistency
# ==============================================================================

def test_dashboard_metrics_and_scope(client: TestClient):
    # Central Admin sees all cases
    login_as(client, "admin")
    res_admin = client.get("/dashboard/metrics")
    assert res_admin.status_code == 200
    m_admin = res_admin.json()
    assert m_admin["total_registered"] >= 4
    assert m_admin["total_active"] >= 3

    # PGRC Officer sees only PGRC cases in their metrics
    login_as(client, "officer_pgrc")
    res_pgrc = client.get("/dashboard/metrics")
    assert res_pgrc.status_code == 200
    m_pgrc = res_pgrc.json()
    # PGRC officer counts should be strictly less than or equal to total admin counts
    assert m_pgrc["total_registered"] <= m_admin["total_registered"]


# ==============================================================================
# 9. Complete Judge Demonstration Scenario (Section 15 End-to-End)
# ==============================================================================

def test_judge_demonstration_scenario_complete(client: TestClient):
    """
    Executes the exact 15-step demonstration required by Section 15 of prompt:
    1. Create Institution A with a unique Permanent ID.
    2. Import a PGRC case and an RB case for the institution.
    3. Verify that each case has a stable, independently generated ID.
    4. Verify the overlap alert is generated synchronously and persisted.
    5. Sign in as an authorized bureau officer.
    6. Confirm that shared metadata is visible but high-confidentiality details are hidden.
    7. Transfer one case to a third bureau, ensuring the two cases still span different bureaus.
    8. Verify the transfer event and notification.
    9. Accept the transferred case and return it to Under Process.
    10. Escalate a case and verify its independent history event.
    11. Advance the injected clock to test the approaching-deadline and overdue behavior.
    12. Dispose one case and verify that the pair's cross-bureau overlap alert auto-resolves.
    13. Verify historical reports retain disposed cases.
    14. Demonstrate CSV re-import handling without duplicating or rewriting an existing case.
    15. Show the MIS reports and scoped dashboard counts.
    """
    login_as(client, "admin")

    # Step 1: Create Institution A
    inst_pid = "1-DEMO2026"
    r_inst = client.post(
        "/institutions",
        json={
            "permanent_id": inst_pid,
            "name": "Demo National Institute of Technology",
            "state": "Telangana",
            "region": "South-Central",
            "address": "Warangal, Telangana",
        },
    )
    assert r_inst.status_code == 201

    # Step 2: Import a PGRC case and an RB case for the institution
    csv_demo = f"""permanent_id,institution_name,bureau_code,source_system,source_record_id,category,subject,description,received_date,confidentiality_level,status
{inst_pid},Demo National Institute of Technology,PGRC,DEMO_SYS,DEMO-PGRC-001,Fee Refund,Excess tuition fees,Refusal to refund caution deposit,2026-03-01,ORDINARY,Pending
{inst_pid},Demo National Institute of Technology,RB,DEMO_SYS,DEMO-RB-001,Faculty Norms,Inadequate faculty,Faculty shortage in CSE department,2026-03-02,HIGH,Under Process
"""
    r_import = client.post(
        "/import/upload-raw",
        json={"csv_text": csv_demo, "filename": "demo_scenario.csv", "dry_run": False},
    )
    assert r_import.status_code == 200
    imp_data = r_import.json()
    assert imp_data["accepted_rows"] == 2

    # Step 3: Verify each case has a stable, independently generated ID
    cases_resp = client.get(f"/cases?permanent_id={inst_pid}").json()["cases"]
    assert len(cases_resp) == 2
    c_pgrc = next(c for c in cases_resp if c["current_bureau_code"] == "PGRC")
    c_rb = next(c for c in cases_resp if c["current_bureau_code"] == "RB")
    assert c_pgrc["case_id"].startswith("AICTE/2026/")
    assert c_rb["case_id"].startswith("AICTE/2026/")
    assert c_pgrc["case_id"] != c_rb["case_id"]

    # Step 4: Verify overlap alert was generated synchronously and persisted
    overlaps_resp = client.get("/overlaps?status=OPEN").json()
    demo_overlap = next(
        (o for o in overlaps_resp if o["institution"]["permanent_id"] == inst_pid), None
    )
    assert demo_overlap is not None
    assert demo_overlap["alert_status"] == "OPEN"

    # Step 5 & 6: Sign in as PGRC officer and check confidentiality
    login_as(client, "officer_pgrc")
    # PGRC officer views RB case (High confidentiality)
    rb_case_view = client.get(f"/cases/{c_rb['id']}").json()
    assert rb_case_view["is_full_access"] is False
    assert rb_case_view["category"] == "[CONFIDENTIAL - HIGH]"
    assert "RESTRICTED" in rb_case_view["subject"]
    assert rb_case_view["complainant_name"] is None

    # Step 7 & 8: Transfer one case to a third bureau (AB)
    # The two cases now span PGRC and AB -> Overlap alert still valid!
    login_as(client, "admin")
    with SessionLocal() as db:
        b_ab = db.query(Bureau).filter_by(code="AB").first()
        ab_id = b_ab.id

    r_trans = client.post(
        f"/cases/{c_rb['id']}/transfer",
        json={"destination_bureau_id": ab_id, "reason": "Requires Approval Bureau inspection"},
    )
    assert r_trans.status_code == 200

    # Verify notification for AB officer
    login_as(client, "officer_ab")
    notifs_ab = client.get("/notifications").json()
    transfer_notif = next(
        (n for n in notifs_ab["notifications"] if n["related_case_id"] == c_rb["id"]), None
    )
    assert transfer_notif is not None
    assert transfer_notif["alert_type"] == "TRANSFER_PENDING"

    # Step 9: Accept the transferred case by AB officer -> returns to Under Process
    r_acc = client.post(f"/cases/{c_rb['id']}/accept-transfer")
    assert r_acc.status_code == 200
    assert r_acc.json()["status"] == "Under Process"

    # Step 10: Escalate a case and verify history event
    login_as(client, "admin")
    r_esc = client.post(
        f"/cases/{c_pgrc['id']}/escalate",
        json={"reason": "Institute management uncooperative with PGRC enquiry"},
    )
    assert r_esc.status_code == 200
    pgrc_detail = client.get(f"/cases/{c_pgrc['id']}").json()
    assert pgrc_detail["status"] == "Escalated"
    esc_event = next(h for h in pgrc_detail["history"] if h["action_type"] == "ESCALATED")
    assert "Institute management uncooperative" in esc_event["action_summary"]

    # Step 11: Advance injected clock to test approaching and overdue behavior
    client.post("/clock/advance", json={"days": 35, "hours": 0})
    refreshed_case = client.get(f"/cases/{c_pgrc['id']}").json()
    assert refreshed_case["sla_status"] == "OVERDUE"

    # Step 12: Dispose one case (c_pgrc)
    # Since c_pgrc was Pending/Escalated, acknowledge escalation first to move to Under Process, then dispose!
    client.post(f"/cases/{c_pgrc['id']}/acknowledge-escalation")
    r_disp = client.post(
        f"/cases/{c_pgrc['id']}/dispose",
        json={"resolution_summary": "Caution deposit fully refunded to student with proof submitted"},
    )
    assert r_disp.status_code == 200

    # Verify that the overlap alert auto-resolved!
    overlaps_after = client.get("/overlaps?status=ALL").json()
    resolved_overlap = next(
        (o for o in overlaps_after if o["institution"]["permanent_id"] == inst_pid), None
    )
    assert resolved_overlap is not None
    assert resolved_overlap["alert_status"] == "RESOLVED"
    assert "disposed" in resolved_overlap["resolution_reason"].lower()

    # Step 13: Verify historical reports retain disposed cases
    mis = client.get("/reports/mis").json()
    assert mis["metrics"]["disposed"] >= 1

    # Step 14: Demonstrate CSV re-import handling without duplicating or rewriting
    r_reimport = client.post(
        "/import/upload-raw",
        json={"csv_text": csv_demo, "filename": "demo_scenario.csv", "dry_run": False},
    )
    assert r_reimport.status_code == 200
    reimport_data = r_reimport.json()
    assert reimport_data["accepted_rows"] == 0
    assert reimport_data["review_rows"] == 2  # Idempotent duplicate protection

    # Step 15: MIS reports and scoped counts
    login_as(client, "officer_ab")
    mis_ab = client.get("/reports/mis").json()
    assert mis_ab["metrics"]["total_registered"] <= mis["metrics"]["total_registered"]

    # Reset clock
    client.post("/clock/reset")

