"""
CSV Ingestion service for SIH26264 complaint cases.

Enforces:
1. Max 200 data rows per upload.
2. Registry verification (authoritative institution registry; no silent overwrites).
3. External source record ID idempotency (no silent rewrites or lifecycle bypass).
4. Synchronous overlap detection on every created case.
5. Baseline 'IMPORTED' CaseHistory event.
6. Row-level outcome tracking and review queue (ImportIssue).
"""
import csv
import io
from datetime import date, datetime
from typing import Any
from sqlalchemy.orm import Session

from ..clock import get_now
from ..models import (
    Bureau,
    CaseHistory,
    ComplaintCase,
    ImportBatch,
    ImportIssue,
    ImportRow,
    Institution,
    User,
)
from .case_number import generate_case_id
from .overlap import detect_cross_bureau_overlaps_for_institution
from .sla import calculate_effective_deadline

MAX_IMPORT_ROWS = 200

EXPECTED_HEADERS = {
    "permanent_id",
    "institution_name",
    "bureau_code",
    "category",
    "subject",
    "description",
    "received_date",
}


def parse_date(date_str: str | None) -> date | None:
    if not date_str or not date_str.strip():
        return None
    s = date_str.strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def process_csv_import(
    db: Session,
    csv_content: str,
    filename: str,
    initiating_user: User,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Processes an uploaded CSV file.
    Validates headers, row count, registry records, duplicates, and commits accepted rows.
    """
    now_utc = get_now()
    reader = csv.DictReader(io.StringIO(csv_content))
    if not reader.fieldnames:
        raise ValueError("The uploaded CSV is empty or has no header row.")

    normalized_headers = {h.strip().lower(): h for h in reader.fieldnames if h}
    missing = EXPECTED_HEADERS - set(normalized_headers.keys())
    if missing:
        raise ValueError(f"Missing required CSV columns: {sorted(missing)}")

    rows = list(reader)
    if len(rows) > MAX_IMPORT_ROWS:
        raise ValueError(
            f"Upload exceeds maximum limit of {MAX_IMPORT_ROWS} rows (received {len(rows)}). "
            f"Please split your dataset into smaller batches."
        )

    # Pre-cache institutions and bureaus
    all_insts = {inst.permanent_id: inst for inst in db.query(Institution).all()}
    all_bureaus = {b.code.upper(): b for b in db.query(Bureau).filter_by(is_active=True).all()}

    batch = ImportBatch(
        source_system="CSV_IMPORT",
        initiating_user_id=initiating_user.id,
        filename=filename,
        total_rows=len(rows),
        status="PROCESSING",
        created_at=now_utc,
    )
    if not dry_run:
        db.add(batch)
        db.flush()

    accepted_count = 0
    rejected_count = 0
    review_count = 0
    row_reports: list[dict[str, Any]] = []
    affected_institution_ids: set[int] = set()

    for idx, r in enumerate(rows, start=1):
        # Normalize row fields
        get_val = lambda k: (r.get(normalized_headers.get(k, "")) or "").strip()
        perm_id = get_val("permanent_id")
        inst_name = get_val("institution_name")
        bureau_code = get_val("bureau_code").upper()
        source_system = get_val("source_system") or "CSV_IMPORT"
        source_record_id = get_val("source_record_id") or None
        complainant_type = get_val("complainant_type") or "Student"
        category = get_val("category")
        subject = get_val("subject")
        description = get_val("description")
        confidentiality = get_val("confidentiality_level").upper() or "ORDINARY"
        if confidentiality not in ("ORDINARY", "HIGH"):
            confidentiality = "ORDINARY"

        status_val = get_val("status") or "Pending"
        if status_val not in ("Pending", "Under Process", "Transferred", "Escalated", "Disposed"):
            status_val = "Pending"

        received_date_str = get_val("received_date")
        received_date = parse_date(received_date_str)
        due_date_str = get_val("due_date")
        due_date = parse_date(due_date_str)

        row_errors: list[str] = []
        is_review = False
        review_type = ""
        review_desc = ""

        # Validation 1: Required fields
        if not perm_id:
            row_errors.append("Permanent ID is required.")
        if not category:
            row_errors.append("Category is required.")
        if not subject:
            row_errors.append("Subject is required.")
        if not description:
            row_errors.append("Description is required.")
        if not received_date:
            row_errors.append(f"Invalid or missing received_date: '{received_date_str}'.")

        # Validation 2: Bureau check
        bureau = all_bureaus.get(bureau_code)
        if not bureau:
            row_errors.append(f"Bureau code '{bureau_code}' does not match any active AICTE bureau.")

        # Validation 3: Registry check
        inst = all_insts.get(perm_id)
        if perm_id and not inst:
            is_review = True
            review_type = "UNKNOWN_INSTITUTION"
            review_desc = (
                f"Permanent ID '{perm_id}' not found in AICTE Institution registry. "
                f"Requires institution verification before case can be created."
            )
        elif inst and inst_name:
            # Check name consistency
            if inst.name.strip().lower() != inst_name.strip().lower():
                is_review = True
                review_type = "REGISTRY_CONFLICT"
                review_desc = (
                    f"Name mismatch for Permanent ID '{perm_id}': registry has '{inst.name}' "
                    f"while CSV has '{inst_name}'. Requires administrative verification."
                )

        # Validation 4: Idempotency / Duplicate source record check
        if source_record_id:
            existing_case = (
                db.query(ComplaintCase)
                .filter_by(source_system=source_system, source_record_id=source_record_id)
                .first()
            )
            if existing_case:
                is_review = True
                review_type = "DUPLICATE_SOURCE_RECORD"
                review_desc = (
                    f"A case ({existing_case.case_id}) already exists for "
                    f"{source_system}:{source_record_id}. Re-import cannot overwrite existing case."
                )

        # Determine row outcome
        created_case_id = None
        if row_errors:
            row_status = "REJECTED"
            rejected_count += 1
        elif is_review:
            row_status = "NEEDS_REVIEW"
            review_count += 1
        else:
            row_status = "ACCEPTED"
            accepted_count += 1

            if not dry_run and inst and bureau and received_date:
                # Generate unique case ID
                case_id = generate_case_id(db, received_date)

                # Calculate SLA deadline
                deadline_utc, sla_status = calculate_effective_deadline(
                    db=db,
                    received_date=received_date,
                    bureau_id=bureau.id,
                    category=category,
                    imported_due_date=due_date,
                    imported_due_date_trusted=bool(due_date),
                )

                new_case = ComplaintCase(
                    case_id=case_id,
                    institution_id=inst.id,
                    source_system=source_system,
                    source_record_id=source_record_id,
                    source_bureau_id=bureau.id,
                    current_bureau_id=bureau.id,
                    complainant_type=complainant_type,
                    category=category,
                    subject=subject,
                    description=description,
                    confidentiality_level=confidentiality,
                    received_date=received_date,
                    created_at=now_utc,
                    updated_at=now_utc,
                    status=status_val,
                    imported_due_date=due_date,
                    imported_due_date_provenance=f"CSV:{filename}" if due_date else None,
                    imported_due_date_trusted=bool(due_date),
                    effective_deadline=deadline_utc,
                    sla_status=sla_status,
                )
                db.add(new_case)
                db.flush()
                created_case_id = new_case.id
                affected_institution_ids.add(inst.id)

                # Baseline IMPORTED history event
                db.add(
                    CaseHistory(
                        case_id=new_case.id,
                        actor_id=initiating_user.id,
                        actor_name=initiating_user.name,
                        action_type="IMPORTED",
                        new_status=status_val,
                        source_bureau_id=bureau.id,
                        destination_bureau_id=bureau.id,
                        action_summary=(
                            f"Case imported via CSV batch ({filename}). "
                            f"Initial status: {status_val}. Source ID: {source_record_id or 'N/A'}."
                        ),
                        event_visibility="CROSS_BUREAU_SUMMARY",
                        created_at=now_utc,
                    )
                )

        row_report = {
            "row_number": idx,
            "permanent_id": perm_id,
            "source_record_id": source_record_id,
            "status": row_status,
            "errors": row_errors or ([review_desc] if is_review else []),
            "created_case_id": created_case_id,
        }
        row_reports.append(row_report)

        if not dry_run:
            imp_row = ImportRow(
                batch_id=batch.id,
                row_number=idx,
                source_record_id=source_record_id,
                permanent_id=perm_id,
                status=row_status,
                validation_errors=row_errors or ([review_desc] if is_review else None),
                created_case_id=created_case_id,
                raw_data={"row_number": idx, "permanent_id": perm_id, "bureau": bureau_code},
            )
            db.add(imp_row)
            db.flush()

            if is_review:
                db.add(
                    ImportIssue(
                        batch_id=batch.id,
                        row_id=imp_row.id,
                        issue_type=review_type,
                        description=review_desc,
                        status="PENDING",
                    )
                )

    if not dry_run:
        # Update batch summary
        batch.accepted_rows = accepted_count
        batch.rejected_rows = rejected_count
        batch.review_rows = review_count
        if rejected_count == 0 and review_count == 0:
            batch.status = "COMPLETED"
        elif accepted_count > 0:
            batch.status = "PARTIAL_SUCCESS"
        else:
            batch.status = "FAILED"
        batch.completed_at = get_now()
        db.flush()

        # Synchronous overlap detection on all affected institutions
        for inst_id in affected_institution_ids:
            detect_cross_bureau_overlaps_for_institution(db, inst_id)

    return {
        "batch_id": getattr(batch, "id", None),
        "filename": filename,
        "total_rows": len(rows),
        "accepted_rows": accepted_count,
        "rejected_rows": rejected_count,
        "review_rows": review_count,
        "status": "COMPLETED" if (rejected_count == 0 and review_count == 0) else ("PARTIAL_SUCCESS" if accepted_count > 0 else "FAILED"),
        "rows": row_reports,
    }
