"""Admin-owned assessments: create assessments, author their rubrics (from the RTLP library),
and map each assessment to one or more subjects. Faculty and students see the assessments
mapped to their subjects; only admins create or change assessments and rubrics."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.models import (
    Assessment, AssessmentSubject, AssessmentType, AuditLog, FinalEvaluation, StudentSubmission, Subject,
)
from app.services.assessments import EVALUATION_MODES, normalize_rubric, rubric_total, subject_ids_of
from app.services.rubrics.library import library

router = APIRouter(prefix="/api/admin", tags=["Admin — Assessments"])


class RubricLevelIn(BaseModel):
    name: str
    description: str
    min_marks: Optional[float] = None
    max_marks: Optional[float] = None


class RubricCriterionIn(BaseModel):
    name: str
    max_marks: float
    description: Optional[str] = None
    levels: List[RubricLevelIn]


class AdminAssessmentIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    instructions: Optional[str] = None
    subject_ids: List[int] = Field(min_length=1)
    template_code: Optional[str] = None          # RTLP code the rubric started from
    evaluation_mode: Optional[str] = None        # document | answer_key | observation
    rubric: List[RubricCriterionIn] = Field(min_length=1)
    course_unit: Optional[str] = None
    reference_answer: Optional[str] = None
    due_date: Optional[datetime] = None
    start_date: Optional[datetime] = None
    allowed_file_types: Optional[str] = None
    discrepancy_threshold: float = Field(default=0.20, ge=0, le=1)
    is_active: bool = True


def _log(db, user_id, action, rid, details=None):
    db.add(AuditLog(user_id=user_id, action=action, resource_type="assessment", resource_id=rid, details=details))


def _template(code: Optional[str]) -> Optional[Dict[str, Any]]:
    if not code:
        return None
    t = next((t for t in library() if t["code"] == code), None)
    if not t:
        raise HTTPException(400, f"Unknown RTLP template {code}.")
    return t


def _signature(criteria):
    return [(c["name"], round(float(c["max_marks"]), 2),
             tuple((l["name"], l["description"], round(float(l["min_marks"]), 2), round(float(l["max_marks"]), 2))
                   for l in c["levels"])) for c in criteria]


def _apply(db: Session, a: Assessment, data: AdminAssessmentIn) -> None:
    subjects = db.query(Subject).filter(Subject.id.in_(data.subject_ids)).all()
    if len(subjects) != len(set(data.subject_ids)):
        raise HTTPException(400, "One or more selected subjects do not exist.")

    criteria = normalize_rubric([c.model_dump() for c in data.rubric])
    tpl = _template(data.template_code)
    mode = data.evaluation_mode or (tpl["evaluation_mode"] if tpl else "document")
    if mode not in EVALUATION_MODES:
        raise HTTPException(400, f"Evaluation mode must be one of {', '.join(EVALUATION_MODES)}.")
    if mode == "answer_key" and not (data.reference_answer or "").strip():
        raise HTTPException(400, "Answer-key assessments need the answer key.")

    if tpl:
        from app.services.rubrics.library import scale_criteria
        pristine = _signature(normalize_rubric(scale_criteria(tpl["criteria"], rubric_total(criteria))))
        source = f"RTLP {tpl['code']}" + ("" if _signature(criteria) == pristine else " (edited)")
        atype = db.query(AssessmentType).filter(AssessmentType.rtlp_code == tpl["code"]).first()
    else:
        source, atype = "Custom", None

    a.title = data.title.strip()
    a.description = data.description
    a.instructions = data.instructions
    a.course_unit = data.course_unit or None
    a.reference_answer = data.reference_answer or None
    a.due_date, a.start_date = data.due_date, data.start_date
    a.allowed_file_types = data.allowed_file_types or "pdf,docx,doc,pptx,ppt,txt,images"
    a.discrepancy_threshold = data.discrepancy_threshold
    a.is_active = data.is_active
    a.rubric_data = criteria
    a.rubric_source = source
    a.evaluation_mode = mode
    a.max_marks = rubric_total(criteria)
    a.assessment_type_id = atype.id if atype else None
    a.assessment_type = tpl["name"] if tpl else "Custom"
    a.rubric_version_id = None  # the assessment's own rubric is authoritative
    a.subject_id = data.subject_ids[0]


def _sync_subjects(db: Session, a: Assessment, subject_ids: List[int]) -> None:
    wanted = set(subject_ids)
    current = {l.subject_id: l for l in db.query(AssessmentSubject).filter(AssessmentSubject.assessment_id == a.id)}
    for sid, link in current.items():
        if sid not in wanted:
            used = db.query(StudentSubmission).filter(
                StudentSubmission.assessment_id == a.id, StudentSubmission.subject_id == sid).first()
            if used:
                name = link.subject.name if link.subject else sid
                raise HTTPException(400, f"'{name}' already has submissions for this assessment and cannot be unmapped.")
            db.delete(link)
    for sid in wanted - set(current):
        db.add(AssessmentSubject(assessment_id=a.id, subject_id=sid))


def _out(db: Session, a: Assessment, full: bool = False) -> Dict[str, Any]:
    sids = subject_ids_of(db, a)
    subjects = db.query(Subject).filter(Subject.id.in_(sids)).all() if sids else []
    subs = db.query(StudentSubmission).filter(StudentSubmission.assessment_id == a.id, StudentSubmission.is_draft == False)  # noqa: E712
    published = db.query(FinalEvaluation).join(StudentSubmission, StudentSubmission.id == FinalEvaluation.submission_id) \
        .filter(StudentSubmission.assessment_id == a.id, FinalEvaluation.is_published == True).count()  # noqa: E712
    item = {
        "id": a.id,
        "title": a.title,
        "description": a.description,
        "subjects": [{"id": s.id, "name": s.name, "code": s.code} for s in subjects],
        "subject_ids": [s.id for s in subjects],
        "max_marks": a.max_marks,
        "due_date": a.due_date.isoformat() if a.due_date else None,
        "start_date": a.start_date.isoformat() if a.start_date else None,
        "rubric_source": a.rubric_source or (f"Type: {a.assessment_type}" if a.assessment_type else None),
        "template_code": (a.rubric_source or "")[5:].split(" ")[0] if (a.rubric_source or "").startswith("RTLP ") else None,
        "assessment_type": a.assessment_type,
        "evaluation_mode": a.evaluation_mode or "document",
        "criteria_count": len(a.rubric_data or []),
        "admin_managed": a.rubric_data is not None,
        "is_active": a.is_active,
        "submission_count": subs.count(),
        "published_count": published,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }
    if full:
        from app.services.ai.context import resolve_rubric
        item.update({
            "instructions": a.instructions,
            "course_unit": a.course_unit,
            "reference_answer": a.reference_answer,
            "allowed_file_types": a.allowed_file_types,
            "discrepancy_threshold": a.discrepancy_threshold,
            "rubric": a.rubric_data or resolve_rubric(db, a)["criteria"],
        })
    return item


@router.get("/rubric-templates")
def rubric_templates(admin=Depends(require_admin)):
    """The RTLP Chapter-14 rubric library — starting points for assessment rubrics."""
    return library()


@router.get("/assessments")
def list_assessments(db: Session = Depends(get_db), admin=Depends(require_admin)):
    return [_out(db, a) for a in db.query(Assessment).order_by(Assessment.created_at.desc()).all()]


@router.get("/assessments/{assessment_id}")
def get_assessment(assessment_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    a = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not a:
        raise HTTPException(404, "Assessment not found")
    return _out(db, a, full=True)


@router.post("/assessments")
def create_assessment(data: AdminAssessmentIn, db: Session = Depends(get_db), admin=Depends(require_admin)):
    a = Assessment(created_by_id=admin.id)
    _apply(db, a, data)
    db.add(a)
    db.flush()
    _sync_subjects(db, a, data.subject_ids)
    _log(db, admin.id, "create_assessment", a.id, f"{a.title} → subjects {data.subject_ids} ({a.rubric_source})")
    db.commit()
    db.refresh(a)
    return _out(db, a, full=True)


@router.put("/assessments/{assessment_id}")
def update_assessment(assessment_id: int, data: AdminAssessmentIn, db: Session = Depends(get_db), admin=Depends(require_admin)):
    a = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not a:
        raise HTTPException(404, "Assessment not found")
    _apply(db, a, data)
    _sync_subjects(db, a, data.subject_ids)
    _log(db, admin.id, "update_assessment", a.id, f"subjects {data.subject_ids} ({a.rubric_source})")
    db.commit()
    db.refresh(a)
    out = _out(db, a, full=True)
    if out["published_count"]:
        out["warning"] = ("Feedback already published for this assessment keeps the rubric it was evaluated with; "
                          "the updated rubric applies to new evaluations.")
    return out


@router.delete("/assessments/{assessment_id}")
def deactivate_assessment(assessment_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    """Hide an assessment from faculty and students (submissions and results are kept)."""
    a = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not a:
        raise HTTPException(404, "Assessment not found")
    a.is_active = False
    _log(db, admin.id, "deactivate_assessment", a.id)
    db.commit()
    return {"message": "Assessment deactivated. Existing submissions and results are kept."}
