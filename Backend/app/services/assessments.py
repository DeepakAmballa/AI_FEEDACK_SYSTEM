"""Assessment helpers shared by the admin, faculty, student routes and the evaluator.

Assessments are created by admins and may be shared by several subjects (``AssessmentSubject``).
Each submission records the subject it was made through (``StudentSubmission.subject_id``); that
subject decides which faculty may evaluate it and which course profile grounds the AI.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.models import Assessment, AssessmentSubject, Subject, StudentSubmission

EVALUATION_MODES = ("document", "answer_key", "observation")


def subject_ids_of(db: Session, assessment: Assessment) -> List[int]:
    ids = [l.subject_id for l in db.query(AssessmentSubject).filter(AssessmentSubject.assessment_id == assessment.id)]
    if not ids and assessment.subject_id:
        ids = [assessment.subject_id]
    return ids


def assessments_for_subject(db: Session, subject_id: int, active_only: bool = True):
    q = db.query(Assessment).outerjoin(AssessmentSubject, AssessmentSubject.assessment_id == Assessment.id).filter(
        or_(AssessmentSubject.subject_id == subject_id, Assessment.subject_id == subject_id)
    )
    if active_only:
        q = q.filter(Assessment.is_active == True)  # noqa: E712
    return q.distinct().order_by(Assessment.created_at.desc()).all()


def submission_subject_id(sub: StudentSubmission) -> Optional[int]:
    return sub.subject_id or (sub.assessment.subject_id if sub.assessment else None)


def submission_subject(db: Session, sub: StudentSubmission) -> Optional[Subject]:
    sid = submission_subject_id(sub)
    return db.query(Subject).filter(Subject.id == sid).first() if sid else None


def submissions_for_subject(db: Session, subject_id: int):
    """Submissions made through a subject (legacy rows fall back to the assessment's subject)."""
    return db.query(StudentSubmission).join(Assessment, Assessment.id == StudentSubmission.assessment_id).filter(
        or_(StudentSubmission.subject_id == subject_id,
            (StudentSubmission.subject_id.is_(None)) & (Assessment.subject_id == subject_id))
    ).order_by(StudentSubmission.submitted_at.desc()).all()


# ─── Rubric validation (admin-authored rubrics) ───────────────────────────────

def normalize_rubric(criteria: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate an admin rubric and return it in ``criteria_data`` format.

    Each criterion: name, max_marks > 0, optional description and exactly four levels ordered
    best → weakest with descriptors and mark bands inside [0, max_marks].
    """
    if not criteria:
        raise HTTPException(400, "A rubric needs at least one criterion.")
    out, names = [], set()
    for i, c in enumerate(criteria, start=1):
        name = (c.get("name") or "").strip()
        if not name:
            raise HTTPException(400, f"Criterion {i} needs a name.")
        if name.lower() in names:
            raise HTTPException(400, f"Criterion names must be unique ('{name}' is repeated).")
        names.add(name.lower())
        try:
            cmax = float(c.get("max_marks"))
        except (TypeError, ValueError):
            raise HTTPException(400, f"'{name}' needs maximum marks.")
        if cmax <= 0:
            raise HTTPException(400, f"'{name}' maximum marks must be greater than 0.")

        levels = []
        for j, lvl in enumerate(c.get("levels") or []):
            desc = (lvl.get("description") or "").strip()
            if not desc:
                raise HTTPException(400, f"'{name}': every level needs a descriptor.")
            lo = lvl.get("min_marks")
            hi = lvl.get("max_marks")
            lo = float(lo) if lo not in (None, "") else None
            hi = float(hi) if hi not in (None, "") else None
            if lo is None or hi is None:
                raise HTTPException(400, f"'{name}' level '{lvl.get('name') or j + 1}': enter its mark band.")
            if not (0 <= lo <= hi <= cmax + 1e-9):
                raise HTTPException(400, f"'{name}' level '{lvl.get('name') or j + 1}': band must lie within 0–{cmax:g} and min ≤ max.")
            levels.append({
                "level": 4 - j if len(c.get("levels") or []) == 4 else len(c.get("levels")) - j,
                "name": (lvl.get("name") or f"Level {j + 1}").strip(),
                "description": desc,
                "min_marks": round(lo, 2),
                "max_marks": round(hi, 2),
            })
        if len(levels) < 2:
            raise HTTPException(400, f"'{name}' needs at least two performance levels.")
        if abs(levels[0]["max_marks"] - cmax) > 1e-6:
            raise HTTPException(400, f"'{name}': the top level must reach the criterion maximum ({cmax:g}).")
        for a, b in zip(levels, levels[1:]):
            if b["max_marks"] > a["max_marks"] + 1e-9:
                raise HTTPException(400, f"'{name}': list levels from best to weakest.")
        out.append({
            "name": name,
            "max_marks": round(cmax, 2),
            "description": (c.get("description") or levels[0]["description"]).strip(),
            "levels": levels,
        })
    return out


def rubric_total(criteria: List[Dict[str, Any]]) -> float:
    return round(sum(float(c["max_marks"]) for c in criteria), 2)
