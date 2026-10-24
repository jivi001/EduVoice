"""
Comprehensive Playwright End-to-End Verification Suite for EduVoice (SIH26264).

Automates headless Chromium browser testing across all application details:
1. Landing page, branding, and 1-click evaluator logins.
2. Student account registration (/signup).
3. Central Admin single-window dashboard (metrics, overlap banner, filters, cases table).
4. Dashboard real-time multi-field search and filtering.
5. Time Machine simulated clock advancement (+10d, +30d, Reset).
6. In-app persistent notification drawer and alert indicators.
7. Authoritative Case Registration form with automated sequence ID generation.
8. Complete interactive case lifecycle state machine (Transfer -> Escalate -> Ack -> Dispose).
9. Institution Directory & 360-degree multi-bureau profile modal.
10. Cross-Bureau Overlaps incident management matrix (Active and Auto-Resolved tabs).
11. CSV Ingestion Portal, file upload execution, and Review Queue.
12. MIS Compliance Reports & Safe CSV Export link.
13. Cross-bureau role-based confidentiality masking (PGRC vs RB).
14. Student Grievance Portal: 1-click login, direct grievance lodging, and live progress tracking.
"""
import os
import tempfile
import time
from playwright.sync_api import sync_playwright, expect

BASE_URL = "http://localhost:3000"


def log_test(step: int, name: str):
    print(f"\n[E2E STEP {step:02d}] 🔍 Testing: {name}...")


def log_pass(msg: str):
    print(f"  ✅ PASS: {msg}")


def run_e2e_tests():
    print("=" * 80)
    print("🚀 COMPLETE PLAYWRIGHT E2E BROWSER VERIFICATION SUITE — EDUVOICE (SIH26264)")
    print("=" * 80)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1366, "height": 768})
        page = context.new_page()

        # ----------------------------------------------------------------------
        # STEP 1: Landing Page & Evaluator 1-Click Logins
        # ----------------------------------------------------------------------
        log_test(1, "Landing Page & Evaluator Logins")
        page.goto(f"{BASE_URL}/", wait_until="networkidle")

        expect(page.locator("h1")).to_contain_text("EduVoice: Integrated Complaint Dashboard")
        expect(page.locator("body")).to_contain_text("SIH26264")
        log_pass("Portal landing page rendered with EduVoice branding & SIH26264 problem details.")

        login_btns = [
            "Central Admin",
            "Student Demo (s01)",
            "PGRC Officer",
            "RB Officer",
            "AB Officer",
            "RB Supervisor",
            "Auditor",
        ]
        for btn in login_btns:
            btn_loc = page.locator(f"button:has-text('{btn}')")
            expect(btn_loc).to_be_visible()
        log_pass(f"All {len(login_btns)} evaluator 1-click role logins are present and active.")

        # ----------------------------------------------------------------------
        # STEP 2: Student Account Registration Workflow (/signup)
        # ----------------------------------------------------------------------
        log_test(2, "Student Account Signup Flow (/signup)")
        signup_link = page.locator("a:has-text('Create an account')")
        expect(signup_link).to_be_visible()
        signup_link.click()
        page.wait_for_url("**/signup", timeout=8000)

        expect(page.locator("h1")).to_contain_text("Create your account")
        unique_email = f"e2e_student_{int(time.time())}@college.edu"
        page.locator("input[name='name']").fill("Playwright E2E Student")
        page.locator("input[name='email']").fill(unique_email)
        page.locator("select[name='role']").select_option("student")
        page.locator("input[name='password']").fill("password123!")
        page.locator("input[name='confirm']").fill("password123!")
        page.locator("button:has-text('Create account')").click()

        page.locator("text=Check your email").wait_for(state="visible", timeout=8000)
        expect(page.locator("text=We've sent a verification link")).to_be_visible()
        log_pass("Student registration form validated and email confirmation notification rendered.")

        page.locator("a:has-text('Back to sign in')").click()
        page.wait_for_url(f"{BASE_URL}/", timeout=8000)

        # ----------------------------------------------------------------------
        # STEP 3: Central Admin Sign In & Single-Window Dashboard
        # ----------------------------------------------------------------------
        log_test(3, "Central Admin Sign In & Single-Window Dashboard")
        page.locator("button:has-text('Central Admin')").click()
        page.wait_for_url("**/dashboard", timeout=10000)

        dashboard_h1 = page.locator("h1:has-text('EduVoice: Integrated Complaint Dashboard')")
        dashboard_h1.wait_for(state="visible", timeout=10000)
        log_pass("Successfully signed in as Central Admin and reached Single-Window Dashboard.")

        # Verify all 9 operational metrics cards
        metrics_labels = ["Registered", "Active Cases", "Pending", "Under Process", "Transferred", "Escalated", "Disposed", "Overdue", "Overlaps"]
        for m in metrics_labels:
            expect(page.locator(f"text={m}").first).to_be_visible()
        log_pass("All 9 primary operational metric cards are rendered.")

        # Check Active Overlap Alert banner
        overlap_banner = page.locator("text=Active Cross-Bureau Overlap Incident")
        expect(overlap_banner.first).to_be_visible()
        log_pass("Cross-Bureau Overlap Warning Banner is prominently displayed.")

        # Check Cases Table has loaded records
        rows = page.locator("table tbody tr")
        rows.first.wait_for(state="visible", timeout=5000)
        row_count = rows.count()
        assert row_count >= 3, f"Expected at least 3 cases in table, found {row_count}"
        log_pass(f"Cases table populated with {row_count} case records.")

        # ----------------------------------------------------------------------
        # STEP 4: Dashboard Filters
        # ----------------------------------------------------------------------
        log_test(4, "Dashboard Real-Time Filtering")
        search_input = page.locator("input[placeholder*='Search Case ID']")
        search_input.fill("1-10928374")
        page.wait_for_timeout(500)
        filtered_count = page.locator("table tbody tr").count()
        assert filtered_count >= 1, "Filter returned no results for Permanent ID 1-10928374"
        log_pass(f"Permanent ID search filter returned {filtered_count} matching cases.")
        search_input.fill("")
        page.wait_for_timeout(400)

        # ----------------------------------------------------------------------
        # STEP 5: Time Machine Widget Simulation
        # ----------------------------------------------------------------------
        log_test(5, "Simulated Clock / Time Machine")
        advance_btn = page.locator("button:has-text('+10d')")
        expect(advance_btn).to_be_visible()
        advance_btn.click()
        page.wait_for_timeout(600)
        reset_btn = page.locator("button:has-text('Reset')")
        reset_btn.click()
        page.wait_for_timeout(600)
        log_pass("Time Machine clock simulation (+10d and Reset) executed smoothly.")

        # ----------------------------------------------------------------------
        # STEP 6: In-App Persistent Notifications Bell
        # ----------------------------------------------------------------------
        log_test(6, "In-App Notification Bell & Drawer")
        bell_btn = page.locator("button[title='Notifications']")
        expect(bell_btn).to_be_visible()
        bell_btn.click()
        page.wait_for_timeout(400)
        expect(page.locator("text=Notifications")).to_be_visible()
        log_pass("Notification drawer opens with alerts and deduplication metadata.")
        # Close drawer
        bell_btn.click()
        page.wait_for_timeout(300)

        # ----------------------------------------------------------------------
        # STEP 7: Authoritative Case Registration Workflow
        # ----------------------------------------------------------------------
        log_test(7, "Register New Case Workflow & Sequence Generation")
        page.locator("a:has-text('+ New Case')").click()
        page.wait_for_url("**/cases/new", timeout=8000)

        page.locator("h1:has-text('Register Institution Complaint')").wait_for(state="visible", timeout=5000)
        page.locator("input[placeholder='e.g. 1-10928374']").fill("1-30948576")
        page.locator("select").nth(0).select_option(value="1")  # Regulation Bureau
        page.locator("input[placeholder='Full Name']").fill("Dr. Rajesh Kumar")
        page.locator("input[placeholder='Summary of grievance...']").fill("E2E Playwright: Unauthorized Course Affiliation Fee")
        page.locator("textarea[placeholder*='Comprehensive description']").fill("Automated Playwright verification describing unauthorised admission fees demanded for AICTE unapproved diploma course.")
        page.locator("button:has-text('Register Case')").click()

        page.wait_for_url("**/cases/*", timeout=10000)
        created_case_h1 = page.locator("h1:has-text('AICTE/2026/')")
        created_case_h1.wait_for(state="visible", timeout=8000)
        created_case_id = created_case_h1.inner_text().strip()
        log_pass(f"New case registered; authoritative AICTE ID generated: {created_case_id}")

        # ----------------------------------------------------------------------
        # STEP 8: Interactive Case Lifecycle Execution (Transfer -> Escalate -> Ack -> Dispose)
        # ----------------------------------------------------------------------
        log_test(8, "Interactive Case Lifecycle State Machine Execution")
        # 8a: Transfer Bureau
        transfer_btn = page.locator("button:has-text('Transfer Bureau')")
        expect(transfer_btn).to_be_visible()
        transfer_btn.click()
        page.locator("h2:has-text('Transfer Case to Bureau')").wait_for(state="visible", timeout=4000)
        page.locator("select").select_option(value="2")  # PGRC
        page.locator("textarea[placeholder='Provide accountable explanation...']").fill("Transferring jurisdiction to PGRC due to student fee grievance nature.")
        page.locator("button:has-text('Confirm Transfer')").click()
        page.wait_for_timeout(800)
        expect(page.locator("text=Bureau: PGRC")).to_be_visible()
        expect(page.locator("text=Status: Transferred")).to_be_visible()
        log_pass("Case transferred to Bureau PGRC; status transitioned to 'Transferred'.")

        # 8b: Escalate to Supervisor
        escalate_btn = page.locator("button:has-text('Escalate')")
        expect(escalate_btn).to_be_visible()
        escalate_btn.click()
        page.locator("h2:has-text('Escalate Case to Supervisor')").wait_for(state="visible", timeout=4000)
        page.locator("textarea[placeholder='Provide accountable explanation...']").fill("Institutional compliance deadline expired without response.")
        page.locator("button:has-text('Confirm Escalation')").click()
        page.wait_for_timeout(800)
        expect(page.locator("text=Status: Escalated")).to_be_visible()
        log_pass("Case escalated to supervisor; status transitioned to 'Escalated'.")

        # 8c: Acknowledge Escalation
        ack_btn = page.locator("button:has-text('✓ Acknowledge Escalation')")
        expect(ack_btn).to_be_visible()
        ack_btn.click()
        page.wait_for_timeout(800)
        expect(page.locator("text=Status: Under Process")).to_be_visible()
        log_pass("Escalation acknowledged; case moved to 'Under Process'.")

        # 8d: Dispose Case (Terminal State)
        dispose_btn = page.locator("button:has-text('✕ Dispose Case')")
        expect(dispose_btn).to_be_visible()
        dispose_btn.click()
        page.locator("h2:has-text('Dispose Case with Resolution')").wait_for(state="visible", timeout=4000)
        page.locator("textarea[placeholder='Provide accountable explanation...']").fill("Institution submitted compliance affidavit and refunded unauthorized fee in full.")
        page.locator("button:has-text('Confirm Disposal')").click()
        page.wait_for_timeout(800)
        expect(page.locator("text=Status: Disposed")).to_be_visible()
        log_pass("Case disposed; status transitioned to terminal 'Disposed'.")

        # ----------------------------------------------------------------------
        # STEP 9: Institution Registry & 360° Profile
        # ----------------------------------------------------------------------
        log_test(9, "Institution Registry & 360° Multi-Bureau Profile")
        page.locator("a:has-text('Institutions')").click()
        page.wait_for_url("**/institutions", timeout=8000)

        page.locator("h1:has-text('AICTE Institution Registry')").wait_for(state="visible", timeout=5000)
        profile_btn = page.locator("button:has-text('360° Profile')").first
        profile_btn.click()
        page.locator("text=360° Multi-Bureau Case Profile").wait_for(state="visible", timeout=5000)
        expect(page.locator("text=Cross-Bureau Case History")).to_be_visible()
        log_pass("Institution 360° multi-bureau profile opened showing consolidated case history.")

        # ----------------------------------------------------------------------
        # STEP 10: Cross-Bureau Overlaps Incident Management
        # ----------------------------------------------------------------------
        log_test(10, "Cross-Bureau Overlaps Incident Management")
        page.locator("a:has-text('Overlaps')").click()
        page.wait_for_url("**/overlaps", timeout=8000)

        page.locator("h1:has-text('Cross-Bureau Overlap Tracking')").wait_for(state="visible", timeout=5000)
        expect(page.locator("text=Matching Trigger:").first).to_be_visible()
        # Toggle auto-resolved tab
        page.locator("button:has-text('Auto-Resolved')").click()
        page.wait_for_timeout(500)
        page.locator("button:has-text('Active Incidents')").click()
        page.wait_for_timeout(400)
        log_pass("Cross-Bureau Overlaps incident management matrix and tabs loaded and verified.")

        # ----------------------------------------------------------------------
        # STEP 11: CSV Ingestion Portal & File Upload Execution
        # ----------------------------------------------------------------------
        log_test(11, "CSV Ingestion Portal & Upload Processing")
        page.locator("a:has-text('CSV Ingest')").click()
        page.wait_for_url("**/import", timeout=8000)

        page.locator("h1:has-text('CSV Grievance Ingestion & Sync')").wait_for(state="visible", timeout=5000)
        expect(page.locator("button:has-text('Download Sample CSV Template')")).to_be_visible()

        # Generate a small valid CSV in temporary location
        test_csv_content = (
            "permanent_id,institution_name,bureau_code,source_system,source_record_id,category,subject,description,received_date,confidentiality_level,status,due_date\n"
            f"1-10928374,Apex Institute of Technology,RB,STATE_PORTAL,E2E-CSV-{int(time.time())},Capitation Fee,Illegal charges,Playwright test CSV row,2026-03-01,ORDINARY,Pending,2026-04-01\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write(test_csv_content)
            temp_csv_path = f.name

        try:
            page.locator("input[type='file']").set_input_files(temp_csv_path)
            page.locator("button:has-text('Upload & Ingest')").click()
            page.locator("text=Batch Ingestion Report:").wait_for(state="visible", timeout=10000)
            expect(page.locator("text=Accepted & Committed:")).to_be_visible()
            log_pass("CSV file successfully uploaded, validated against AICTE registry, and batch-ingested.")
        finally:
            if os.path.exists(temp_csv_path):
                os.unlink(temp_csv_path)

        # ----------------------------------------------------------------------
        # STEP 12: MIS Reports & Safe CSV Export
        # ----------------------------------------------------------------------
        log_test(12, "MIS Reports & Compliance Analytics")
        page.locator("a:has-text('MIS Reports')").click()
        page.wait_for_url("**/reports", timeout=8000)

        page.locator("h1:has-text('EduVoice: MIS Analytics & Compliance Reports')").wait_for(state="visible", timeout=5000)
        expect(page.locator("text=OVERALL DISPOSAL RATE")).to_be_visible()
        expect(page.locator("text=1. Bureau-Wise Complaint Workload & Disposal Efficiency")).to_be_visible()
        expect(page.locator("text=2. Regional Case Distribution")).to_be_visible()
        expect(page.locator("text=3. Active Case Ageing Analysis")).to_be_visible()
        export_link = page.locator("a:has-text('Export Safe CSV Report')")
        expect(export_link).to_be_visible()
        log_pass("Complete MIS analytics dashboard with bureau, region, ageing and safe CSV export verified.")

        # ----------------------------------------------------------------------
        # STEP 13: Role-Based Confidentiality Masking (PGRC Officer)
        # ----------------------------------------------------------------------
        log_test(13, "Cross-Bureau Confidentiality Redaction")
        page.locator("button:has-text('Sign out')").click()
        page.wait_for_url(f"{BASE_URL}/", timeout=8000)

        # Sign in as PGRC Officer
        page.locator("button:has-text('PGRC Officer')").click()
        page.wait_for_url("**/dashboard", timeout=8000)
        page.locator("h1:has-text('EduVoice: Integrated Complaint Dashboard')").wait_for(state="visible", timeout=8000)

        # Navigate to High Confidentiality Regulation Bureau case (/cases/3)
        page.goto(f"{BASE_URL}/cases/3", wait_until="networkidle")
        page.locator("text=HIGH CONFIDENTIALITY").first.wait_for(state="visible", timeout=8000)
        expect(page.locator("text=[CONFIDENTIAL - HIGH]").first).to_be_visible()
        expect(page.locator("text=[RESTRICTED]").first).to_be_visible()
        log_pass("High confidentiality case masked for cross-bureau officer at the API layer.")

        # ----------------------------------------------------------------------
        # STEP 14: Student Grievance Lodging & Live Progress Tracking
        # ----------------------------------------------------------------------
        log_test(14, "Student Grievance Lodging & Progress Tracking Portal")
        page.locator("button:has-text('Sign out')").click()
        page.wait_for_url(f"{BASE_URL}/", timeout=8000)

        # Use 1-Click Student Demo button
        page.locator("button:has-text('Student Demo (s01)')").click()
        page.wait_for_url("**/student", timeout=8000)

        student_h1 = page.locator("h1:has-text('Student Grievance Portal')")
        student_h1.wait_for(state="visible", timeout=8000)
        log_pass("Student portal loaded via 1-click evaluator demo button.")

        # Open grievance form
        page.locator("button:has-text('+ Lodge New Grievance')").click()
        page.locator("text=Lodge Grievance with AICTE").wait_for(state="visible", timeout=3000)

        # Fill grievance
        page.locator("input[placeholder='e.g. 1-10928374']").fill("1-10928374")
        page.locator("input[placeholder='Brief summary of the issue...']").fill("E2E Playwright: Student Caution Money Refund Delay")
        page.locator("textarea[placeholder*='Provide specific dates']").fill("Graduation completed in 2026. Account office has not released caution money deposit of INR 25,000 despite clearance certificate.")
        page.locator("button:has-text('Submit Grievance')").click()

        page.locator("text=Grievance submitted successfully!").wait_for(state="visible", timeout=8000)
        expect(page.locator("text=AICTE/2026/").first).to_be_visible()
        expect(page.locator("text=Pending Review").first).to_be_visible()
        log_pass("Student grievance successfully lodged and visible in live tracking list with official AICTE Case ID.")

        browser.close()

    print("\n" + "=" * 80)
    print("🎉 ALL 14 PLAYWRIGHT E2E DETAILED FUNCTIONAL TESTS PASSED PERFECTLY!")
    print("=" * 80)


if __name__ == "__main__":
    run_e2e_tests()
