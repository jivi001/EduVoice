"""
Case number generator for AICTE complaint tracking.

Format: AICTE/YYYY/NNNNNN
Uses annual sequence table (CaseNumberSequence) with row-level locking where supported.
"""
from datetime import date
from sqlalchemy.orm import Session

from ..clock import get_current_year
from ..models import CaseNumberSequence


def generate_case_id(db: Session, received_date: date | None = None) -> str:
    """
    Allocate the next sequential case ID for the given year.
    Year precedence:
    1. Validated received_date.year if provided.
    2. Current year in application timezone.
    """
    year = received_date.year if received_date else get_current_year()

    # Query with row lock if supported by the database dialect
    seq = db.query(CaseNumberSequence).filter_by(year=year).with_for_update().first()
    if not seq:
        # First case for this calendar year
        seq = CaseNumberSequence(year=year, last_number=1)
        db.add(seq)
        db.flush()
        allocated_num = 1
    else:
        seq.last_number += 1
        db.flush()
        allocated_num = seq.last_number

    return f"AICTE/{year}/{allocated_num:06d}"
