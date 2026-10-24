"""
CSV Ingestion and Import Review Queue Router.
"""
import csv
import io
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..clock import get_now
from ..db import get_db
from ..models import ImportBatch, ImportIssue, ImportRow, User
from ..security import get_current_user
from ..services.ingestion import process_csv_import
from ..services.reports import sanitize_csv_cell

router = APIRouter(prefix="/import", tags=["import"])


class IssueResolveIn(BaseModel):
    action: str  # RESOLVE | IGNORE
    notes: str | None = None


class RawCsvImportIn(BaseModel):
    csv_text: str
    filename: str = "upload.csv"
    dry_run: bool = False


@router.post("/upload-raw")
def upload_raw_csv(
    body: RawCsvImportIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        result = process_csv_import(
            db=db,
            csv_content=body.csv_text,
            filename=body.filename,
            initiating_user=user,
            dry_run=body.dry_run,
        )
        if not body.dry_run:
            db.commit()
        return result
    except ValueError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Error processing CSV: {str(e)}")


@router.post("/upload")
async def upload_csv(
    file: UploadFile = File(...),
    dry_run: bool = Form(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Only CSV files (.csv) are accepted.")

    content_bytes = await file.read()
    try:
        csv_text = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            csv_text = content_bytes.decode("latin-1")
        except Exception:
            raise HTTPException(400, "Could not decode file as UTF-8 or Latin-1 text.")

    try:
        result = process_csv_import(
            db=db,
            csv_content=csv_text,
            filename=file.filename,
            initiating_user=user,
            dry_run=dry_run,
        )
        if not dry_run:
            db.commit()
        return result
    except ValueError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Error processing CSV: {str(e)}")


@router.get("/batches")
def list_batches(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    batches = db.query(ImportBatch).order_by(ImportBatch.created_at.desc()).limit(50).all()
    return [
        {
            "id": b.id,
            "filename": b.filename,
            "source_system": b.source_system,
            "total_rows": b.total_rows,
            "accepted_rows": b.accepted_rows,
            "rejected_rows": b.rejected_rows,
            "review_rows": b.review_rows,
            "status": b.status,
            "created_at": b.created_at.isoformat(),
            "completed_at": b.completed_at.isoformat() if b.completed_at else None,
        }
        for b in batches
    ]


@router.get("/batches/{id}")
def get_batch(
    id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    b = db.query(ImportBatch).filter_by(id=id).first()
    if not b:
        raise HTTPException(404, "Batch not found.")

    rows = db.query(ImportRow).filter_by(batch_id=b.id).order_by(ImportRow.row_number.asc()).all()
    return {
        "id": b.id,
        "filename": b.filename,
        "status": b.status,
        "total_rows": b.total_rows,
        "accepted_rows": b.accepted_rows,
        "rejected_rows": b.rejected_rows,
        "review_rows": b.review_rows,
        "created_at": b.created_at.isoformat(),
        "rows": [
            {
                "id": r.id,
                "row_number": r.row_number,
                "source_record_id": r.source_record_id,
                "permanent_id": r.permanent_id,
                "status": r.status,
                "validation_errors": r.validation_errors,
                "created_case_id": r.created_case_id,
            }
            for r in rows
        ],
    }


@router.get("/batches/{id}/report")
def download_batch_report(
    id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    b = db.query(ImportBatch).filter_by(id=id).first()
    if not b:
        raise HTTPException(404, "Batch not found.")

    rows = db.query(ImportRow).filter_by(batch_id=b.id).order_by(ImportRow.row_number.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Row Number", "Permanent ID", "Source Record ID", "Processing Status", "Validation Errors / Notes"])

    for r in rows:
        errs = "; ".join(r.validation_errors) if r.validation_errors else ""
        writer.writerow([
            r.row_number,
            sanitize_csv_cell(r.permanent_id),
            sanitize_csv_cell(r.source_record_id),
            r.status,
            sanitize_csv_cell(errs),
        ])

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=import_report_batch_{b.id}.csv"},
    )


@router.get("/issues")
def list_issues(
    status: str | None = "PENDING",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(ImportIssue)
    if status and status.upper() != "ALL":
        query = query.filter(ImportIssue.status == status.upper())

    issues = query.order_by(ImportIssue.id.desc()).all()
    return [
        {
            "id": iss.id,
            "batch_id": iss.batch_id,
            "row_id": iss.row_id,
            "issue_type": iss.issue_type,
            "description": iss.description,
            "status": iss.status,
            "resolution_notes": iss.resolution_notes,
            "resolved_at": iss.resolved_at.isoformat() if iss.resolved_at else None,
        }
        for iss in issues
    ]


@router.post("/issues/{id}/resolve")
def resolve_issue(
    id: int,
    body: IssueResolveIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    iss = db.query(ImportIssue).filter_by(id=id).first()
    if not iss:
        raise HTTPException(404, "Issue not found.")

    now_utc = get_now()
    iss.status = "RESOLVED" if body.action.upper() == "RESOLVE" else "IGNORED"
    iss.resolution_notes = body.notes
    iss.resolved_by_id = user.id
    iss.resolved_at = now_utc
    db.commit()

    return {"ok": True, "status": iss.status}
