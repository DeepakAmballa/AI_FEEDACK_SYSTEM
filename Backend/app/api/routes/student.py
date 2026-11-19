"""Student routes — submissions, results, subject views."""
import os
from datetime import datetime
import uuid
import logging
import json
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.config import get_settings
from app.models.models import (
    User, StudentProfile, Subject, Assessment, StudentSubmission,
    AIEvaluation, ApprovedFeedback, SubjectEnrollment,
    FinalEvaluation, FacultyEvaluation,
    UserRole, SubmissionStatus
)
from app.schemas.schemas import SubmissionOut, AssessmentOut, SubjectOut, StudentTypedSubmissionCreate
from app.services.document.processor import extract_text, validate_document, is_allowed_file, get_file_extension
from app.services.report.generator import generate_unified_pdf_report
from app.services.assessments import assessments_for_subject, subject_ids_of, submission_subject


def _submission_subject_for(db: Session, assessment: Assessment, student: StudentProfile,
                            subject_id: int = None) -> int:
    """The subject a student submits through: one of the assessment's subjects they are enrolled in."""
    mapped = subject_ids_of(db, assessment)
    enrolled = {e.subject_id for e in db.query(SubjectEnrollment).filter(SubjectEnrollment.student_id == student.id)}
    options = [sid for sid in mapped if sid in enrolled]
    if subject_id is not None:
        if subject_id not in options:
            raise HTTPException(403, "You are not enrolled in a subject this assessment belongs to")
        return subject_id
    if not options:
        raise HTTPException(403, "You are not enrolled in a subject this assessment belongs to")
    return options[0]

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/student", tags=["Student"])

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/student", tags=["Student"])


def _get_student_profile(user: User, db: Session) -> StudentProfile:
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(404, "Student profile not found")
    return profile


def _require_student(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.student:
        raise HTTPException(403, "Student access required")
    return user


# ─── My Subjects ──────────────────────────────────────────────────────────────

@router.get("/subjects")
def my_subjects(db: Session = Depends(get_db), user=Depends(_require_student)):
    student = _get_student_profile(user, db)
    enrollments = db.query(SubjectEnrollment).filter(SubjectEnrollment.student_id == student.id).all()
    result = []
    for e in enrollments:
        s = e.subject
        if s and s.is_active:
            result.append({
                "id": s.id,
                "name": s.name,
                "code": s.code,
                "description": s.description,
            })
    return result


# ─── Assessments ──────────────────────────────────────────────────────────────

@router.get("/subjects/{subject_id}/assessments")
def subject_assessments(subject_id: int, db: Session = Depends(get_db), user=Depends(_require_student)):
    student = _get_student_profile(user, db)
    # Verify enrollment
    enrollment = db.query(SubjectEnrollment).filter(
        SubjectEnrollment.subject_id == subject_id,
        SubjectEnrollment.student_id == student.id,
    ).first()
    if not enrollment and user.role != UserRole.admin:
        raise HTTPException(403, "You are not enrolled in this subject")

    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    return [_assessment_card(db, a, student, subject) for a in assessments_for_subject(db, subject_id)]


def _evaluation_started(db: Session, sub) -> bool:
    """Once the faculty submits their marks (or the work is approved) the submission is locked,
    so the faculty and the AI always evaluate the same work."""
    if sub is None or sub.is_draft:
        return False
    if sub.status in (SubmissionStatus.approved, SubmissionStatus.evaluated):
        return True
    fe = db.query(FacultyEvaluation).filter(FacultyEvaluation.submission_id == sub.id).first()
    return bool(fe and not fe.is_draft)


def _latest_submission(db: Session, assessment_id: int, student_id: int):
    return db.query(StudentSubmission).filter(
        StudentSubmission.assessment_id == assessment_id,
        StudentSubmission.student_id == student_id,
    ).order_by(StudentSubmission.submission_version.desc(), StudentSubmission.id.desc()).first()


def _assessment_card(db: Session, a: Assessment, student: StudentProfile, subject: Subject) -> dict:
    """What a student sees for one assessment, including where they are with it.

    state: not_started | draft | submitted (can still be replaced) | in_evaluation (locked) | feedback_ready
    """
    from app.services.ai.context import resolve_rubric

    sub = _latest_submission(db, a.id, student.id)
    final = db.query(FinalEvaluation).filter(FinalEvaluation.submission_id == sub.id).first() if sub else None
    feedback_ready = bool(final and final.is_published) or bool(
        sub and sub.evaluation and sub.evaluation.approved_feedback and sub.evaluation.approved_feedback.is_published)
    if not sub:
        state = "not_started"
    elif sub.is_draft:
        state = "draft"
    elif feedback_ready:
        state = "feedback_ready"
    elif _evaluation_started(db, sub):
        state = "in_evaluation"
    else:
        state = "submitted"
    can_submit = state in ("not_started", "draft", "submitted")
    return {
        "id": a.id,
        "title": a.title,
        "description": a.description,
        "assessment_type": a.assessment_type,
        "instructions": a.instructions,
        "max_marks": a.max_marks,
        "due_date": a.due_date.isoformat() if a.due_date else None,
        "is_overdue": bool(a.due_date and a.due_date.replace(tzinfo=None) < datetime.utcnow() and state in ("not_started", "draft")),
        "allowed_file_types": a.allowed_file_types,
        "subject_id": (sub.subject_id if sub and sub.subject_id else subject.id) if subject else None,
        "subject_name": subject.name if subject else None,
        "subject_code": subject.code if subject else None,
        # Students see the criteria they will be assessed on (never the answer key)
        "criteria": [{"label": c["label"], "name": c["name"], "max_marks": c["max_marks"], "color": c["color"],
                      "description": c.get("description")} for c in resolve_rubric(db, a)["criteria"]],
        "state": state,
        "can_submit": can_submit,
        "submitted": state in ("submitted", "in_evaluation", "feedback_ready"),
        "submission_status": sub.status.value if sub else None,
        "submission_id": sub.id if sub else None,
        "submission_type": (sub.submission_type or "upload") if sub else None,
        "submitted_at": sub.submitted_at.isoformat() if sub and sub.submitted_at else None,
        "final_score": final.final_total_marks if final and final.is_published else None,
    }


@router.get("/assessments")
def all_my_assessments(db: Session = Depends(get_db), user=Depends(_require_student)):
    """Every active assessment across the student's enrolled subjects (shared assessments once)."""
    student = _get_student_profile(user, db)
    enrollments = db.query(SubjectEnrollment).filter(SubjectEnrollment.student_id == student.id).all()
    seen, out = set(), []
    for e in enrollments:
        if not e.subject or not e.subject.is_active:
            continue
        for a in assessments_for_subject(db, e.subject_id):
            if a.id in seen:
                continue
            seen.add(a.id)
            sub = _latest_submission(db, a.id, student.id)
            subject = e.subject
            if sub and sub.subject_id and sub.subject_id != e.subject_id:
                subject = db.query(Subject).filter(Subject.id == sub.subject_id).first() or e.subject
            out.append(_assessment_card(db, a, student, subject))
    order = {"draft": 0, "not_started": 1, "submitted": 2, "in_evaluation": 3, "feedback_ready": 4}
    far = "9999-12-31"
    out.sort(key=lambda x: (order.get(x["state"], 9), x["due_date"] or far))
    return out


# ─── Submissions ──────────────────────────────────────────────────────────────

@router.post("/assessments/{assessment_id}/submit")
async def submit_assignment(
    assessment_id: int,
    file: UploadFile = File(...),
    subject_id: int = Form(default=None),
    db: Session = Depends(get_db),
    user=Depends(_require_student)
):
    student = _get_student_profile(user, db)

    if not is_allowed_file(file.filename):
        raise HTTPException(400, "File type not allowed. Supported: PDF, DOC/DOCX, PPT/PPTX, TXT, and common image formats.")

    assessment = db.query(Assessment).filter(Assessment.id == assessment_id, Assessment.is_active == True).first()
    if not assessment:
        raise HTTPException(404, "Assessment not found")

    via_subject = _submission_subject_for(db, assessment, student, subject_id)

    # Check for existing submission
    existing = db.query(StudentSubmission).filter(
        StudentSubmission.assessment_id == assessment_id,
        StudentSubmission.student_id == student.id,
    ).first()
    if existing and existing.status == SubmissionStatus.approved:
        raise HTTPException(400, "Your submission has already been approved and evaluated. Re-submission is closed.")
    if _evaluation_started(db, existing):
        raise HTTPException(400, "Your faculty has already started evaluating this submission, so it can no longer be replaced.")

    # Save file
    ext = get_file_extension(file.filename)
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    save_dir = Path(settings.upload_dir) / "submissions" / str(student.id)
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / unique_name

    contents = await file.read()
    with open(save_path, "wb") as f:
        f.write(contents)

    # Extract text
    extraction_status = "success"
    extracted_text = None
    page_count = 0
    try:
        validate_document(str(save_path))
        extracted_text, page_count = extract_text(str(save_path), ext)
        if not extracted_text.strip():
            extraction_status = "empty"
    except Exception as e:
        extraction_status = f"failed: {str(e)}"
        logger.error(f"Text extraction failed for submission: {e}")

    if existing:
        submission = existing
        submission.filename = unique_name
        submission.original_filename = file.filename
        submission.file_type = ext
        submission.file_path = str(save_path)
        submission.file_size = len(contents)
        submission.extracted_text = extracted_text
        submission.extraction_status = extraction_status
        submission.page_count = page_count
        submission.status = SubmissionStatus.pending
        submission.subject_id = via_subject
        # An uploaded file replaces any earlier typed answer or draft — otherwise the evaluator
        # (which reads typed content first) would grade the stale typed text.
        submission.submission_type = "upload"
        submission.typed_content = None
        submission.is_draft = False
    else:
        submission = StudentSubmission(
            student_id=student.id,
            assessment_id=assessment_id,
            filename=unique_name,
            original_filename=file.filename,
            file_type=ext,
            file_path=str(save_path),
            file_size=len(contents),
            extracted_text=extracted_text,
            extraction_status=extraction_status,
            page_count=page_count,
            status=SubmissionStatus.pending,
            subject_id=via_subject,
            submission_version=(
                (db.query(StudentSubmission)
                 .filter(
                     StudentSubmission.student_id == student.id,
                     StudentSubmission.assessment_id == assessment_id,
                 )
                 .order_by(StudentSubmission.submission_version.desc())
                 .first().submission_version + 1)
                if db.query(StudentSubmission).filter(
                    StudentSubmission.student_id == student.id,
                    StudentSubmission.assessment_id == assessment_id,
                ).first()
                else 1
            ),
        )
        db.add(submission)
    db.commit()
    db.refresh(submission)

    result = {
        "message": "Submission received successfully",
        "submission_id": submission.id,
        "extraction_status": extraction_status,
        "file_type": ext,
    }
    return result


@router.post("/assessments/{assessment_id}/submit-typed")
def submit_typed_assignment(
    assessment_id: int,
    data: StudentTypedSubmissionCreate,
    subject_id: int = None,
    db: Session = Depends(get_db),
    user=Depends(_require_student)
):
    """
    Type Submission feature for students.
    Supports draft saving, draft editing, and final submission.
    """
    student = _get_student_profile(user, db)

    assessment = db.query(Assessment).filter(Assessment.id == assessment_id, Assessment.is_active == True).first()
    if not assessment:
        raise HTTPException(404, "Assessment not found")

    via_subject = _submission_subject_for(db, assessment, student, subject_id)

    if not data.typed_content or not data.typed_content.strip():
        raise HTTPException(400, "Submission content cannot be empty.")

    # Check for existing submission
    existing = db.query(StudentSubmission).filter(
        StudentSubmission.assessment_id == assessment_id,
        StudentSubmission.student_id == student.id,
    ).order_by(
        StudentSubmission.submission_version.desc(),
        StudentSubmission.id.desc(),
    ).first()

    if existing and existing.status == SubmissionStatus.approved:
        if not data.is_draft:
            raise HTTPException(400, "Your submission has already been approved and evaluated. Re-submission is closed.")
        # Preserve the approved record and start a new draft version.
        existing = None
    elif _evaluation_started(db, existing):
        raise HTTPException(400, "Your faculty has already started evaluating this submission, so it can no longer be changed.")

    if existing:
        submission = existing
        submission.submission_type = "typed"
        submission.typed_content = data.typed_content.strip()
        submission.extracted_text = data.typed_content.strip()
        submission.filename = "typed_submission.txt"
        submission.original_filename = "Typed Submission"
        submission.file_type = "txt"
        submission.file_path = ""
        submission.file_size = len(data.typed_content.encode("utf-8"))
        submission.extraction_status = "success"
        submission.page_count = max(1, len(data.typed_content.split()) // 300)
        submission.is_draft = data.is_draft
        submission.status = SubmissionStatus.pending
        submission.subject_id = via_subject
    else:
        submission = StudentSubmission(
            student_id=student.id,
            assessment_id=assessment_id,
            submission_type="typed",
            typed_content=data.typed_content.strip(),
            extracted_text=data.typed_content.strip(),
            filename="typed_submission.txt",
            original_filename="Typed Submission",
            file_type="txt",
            file_path="",
            file_size=len(data.typed_content.encode("utf-8")),
            extraction_status="success",
            page_count=max(1, len(data.typed_content.split()) // 300),
            is_draft=data.is_draft,
            status=SubmissionStatus.pending,
            subject_id=via_subject,
            submission_version=(
                (db.query(StudentSubmission)
                 .filter(
                     StudentSubmission.student_id == student.id,
                     StudentSubmission.assessment_id == assessment_id,
                 )
                 .order_by(StudentSubmission.submission_version.desc())
                 .first().submission_version + 1)
                if db.query(StudentSubmission).filter(
                    StudentSubmission.student_id == student.id,
                    StudentSubmission.assessment_id == assessment_id,
                ).first()
                else 1
            ),
        )
        db.add(submission)

    db.commit()
    db.refresh(submission)

    return {
        "message": "Draft saved successfully" if data.is_draft else "Assignment submitted successfully!",
        "submission_id": submission.id,
        "is_draft": submission.is_draft,
        "status": submission.status.value,
    }


@router.get("/assessments/{assessment_id}/my-typed-draft")
def get_my_typed_draft(
    assessment_id: int,
    db: Session = Depends(get_db),
    user=Depends(_require_student)
):
    """Retrieve saved draft or active typed submission content for student editing."""
    student = _get_student_profile(user, db)
    submission = db.query(StudentSubmission).filter(
        StudentSubmission.assessment_id == assessment_id,
        StudentSubmission.student_id == student.id,
    ).order_by(
        StudentSubmission.submission_version.desc(),
        StudentSubmission.submitted_at.desc(),
        StudentSubmission.id.desc(),
    ).first()

    if not submission:
        return {"has_draft": False, "typed_content": "", "is_draft": False}

    return {
        "has_draft": bool(submission.typed_content),
        "typed_content": submission.typed_content or submission.extracted_text or "",
        "is_draft": getattr(submission, "is_draft", False),
        "status": submission.status.value,
        "submitted_at": submission.submitted_at.isoformat(),
    }


@router.get("/submissions")
def my_submissions(db: Session = Depends(get_db), user=Depends(_require_student)):
    student = _get_student_profile(user, db)
    submissions = db.query(StudentSubmission).filter(
        StudentSubmission.student_id == student.id
    ).order_by(StudentSubmission.submitted_at.desc()).all()

    result = []
    for s in submissions:
        has_published_feedback = False
        final_eval = db.query(FinalEvaluation).filter(FinalEvaluation.submission_id == s.id).first()
        if final_eval and final_eval.is_published:
            has_published_feedback = True
        elif s.evaluation and s.evaluation.approved_feedback and s.evaluation.approved_feedback.is_published:
            has_published_feedback = True

        result.append({
            "id": s.id,
            "assessment_title": s.assessment.title if s.assessment else "Unknown",
            "subject_name": (submission_subject(db, s).name if submission_subject(db, s) else "Unknown"),
            "original_filename": s.original_filename,
            "submission_type": s.submission_type or "upload",
            "file_type": s.file_type,
            "status": s.status.value,
            "is_draft": getattr(s, "is_draft", False),
            "submitted_at": s.submitted_at.isoformat(),
            "has_feedback": has_published_feedback,
        })
    return result


# ─── View Results (Unified Report Access) ─────────────────────────────────────

@router.get("/submissions/{submission_id}/feedback")
def get_feedback(submission_id: int, db: Session = Depends(get_db), user=Depends(_require_student)):
    student = _get_student_profile(user, db)
    submission = db.query(StudentSubmission).filter(
        StudentSubmission.id == submission_id,
        StudentSubmission.student_id == student.id
    ).first()
    if not submission:
        raise HTTPException(404, "Submission not found")

    final_eval = db.query(FinalEvaluation).filter(FinalEvaluation.submission_id == submission_id).first()

    # Check publication status
    if final_eval and final_eval.is_published:
        assess = submission.assessment
        max_marks = assess.max_marks if assess else 20.0
        final_marks = final_eval.final_total_marks
        percentage = round((final_marks / max_marks) * 100, 1) if max_marks else 0.0
        faculty_eval = db.query(FacultyEvaluation).filter(
            FacultyEvaluation.submission_id == submission_id
        ).first()

        return {
            "student_name": user.full_name,
            "student_id": student.student_id,
            "program": student.program or "Undergraduate",
            "assessment_title": assess.title if assess else "Assessment",
            "assessment_type": assess.assessment_type or "Standard",
            "assessment_description": assess.description,
            "subject_name": (submission_subject(db, submission).name if submission_subject(db, submission) else "Subject"),
            "submitted_at": submission.submitted_at.isoformat(),
            "original_filename": submission.original_filename,
            "submission_content": submission.typed_content or submission.extracted_text,
            "max_marks": max_marks,
            "final_score": final_marks,
            "final_percentage": percentage,
            # Unified Feedback without exposing separate AI marks or discrepancy
            "overall_feedback": final_eval.unified_overall_feedback,
            "strengths": final_eval.unified_strengths,
            "weaknesses": final_eval.unified_weaknesses,
            "criterion_feedback": final_eval.unified_criterion_feedback or [],
            "improvement_suggestions": final_eval.unified_improvement_suggestions,
            "irrelevant_observations": final_eval.unified_irrelevant_observations or [],
            "final_remarks": final_eval.unified_final_remarks or "Review the feedback carefully to support your growth.",
            "deduction_reasons": faculty_eval.deduction_reasons if faculty_eval else None,
            "approved_at": (final_eval.published_at or final_eval.updated_at).isoformat(),
            # The annotated feedback document (score page, numbered highlighted text, feedback)
            "document": final_eval.feedback_document,
        }

    # Fallback to legacy ApprovedFeedback if present
    if submission.evaluation and submission.evaluation.approved_feedback and submission.evaluation.approved_feedback.is_published:
        af = submission.evaluation.approved_feedback
        assess = submission.assessment
        max_marks = assess.max_marks if assess else 20.0
        faculty_eval = db.query(FacultyEvaluation).filter(
            FacultyEvaluation.submission_id == submission_id
        ).first()
        return {
            "student_name": user.full_name,
            "student_id": student.student_id,
            "program": student.program or "Undergraduate",
            "assessment_title": assess.title if assess else "Assessment",
            "assessment_type": assess.assessment_type or "Standard",
            "assessment_description": assess.description,
            "subject_name": (submission_subject(db, submission).name if submission_subject(db, submission) else "Subject"),
            "submitted_at": submission.submitted_at.isoformat(),
            "original_filename": submission.original_filename,
            "submission_content": submission.typed_content or submission.extracted_text,
            "max_marks": max_marks,
            "final_score": af.final_score,
            "final_percentage": round((af.final_score / max_marks) * 100, 1) if max_marks else 0.0,
            "overall_feedback": af.final_feedback,
            "strengths": submission.evaluation.ai_strengths,
            "weaknesses": submission.evaluation.ai_weaknesses,
            "criterion_feedback": [
                {"criterion_name": cs.criterion_name, "description": cs.justification or ""}
                for cs in submission.evaluation.criterion_scores
            ],
            "improvement_suggestions": submission.evaluation.ai_improvement_suggestions,
            "irrelevant_observations": [],
            "final_remarks": "Feedback verified and approved by faculty.",
            "deduction_reasons": faculty_eval.deduction_reasons if faculty_eval else None,
            "approved_at": af.approved_at.isoformat(),
        }

    return {"message": "No published feedback available yet. Your faculty is reviewing your submission."}


@router.get("/submissions/{submission_id}/feedback.pdf")
def download_feedback_pdf(
    submission_id: int,
    db: Session = Depends(get_db),
    user=Depends(_require_student),
):
    """Download the official unified 10-section academic evaluation report as a PDF."""
    student = _get_student_profile(user, db)
    submission = db.query(StudentSubmission).filter(
        StudentSubmission.id == submission_id,
        StudentSubmission.student_id == student.id,
    ).first()
    if not submission:
        raise HTTPException(404, "Submission not found")

    feedback = get_feedback(submission_id, db, user)
    if feedback.get("message"):
        raise HTTPException(404, feedback["message"])

    if feedback.get("document"):
        from app.services.report.feedback_pdf import render_feedback_pdf
        try:
            pdf_bytes = render_feedback_pdf(feedback["document"])
        except Exception as exc:
            logger.error(f"Feedback PDF rendering failed: {exc}", exc_info=True)
            raise HTTPException(500, "Could not generate the feedback PDF.")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="feedback-{submission_id}.pdf"'},
        )

    try:
        report_data = {
            "student_name": feedback["student_name"],
            "student_id": feedback["student_id"],
            "program": feedback.get("program", "Academic Program"),
            "subject_name": feedback["subject_name"],
            "assessment_title": feedback["assessment_title"],
            "assessment_type": feedback.get("assessment_type", "Standard"),
            "submission_date": feedback["submitted_at"][:10],
            "submission_filename": feedback.get("original_filename"),
            "submission_content": feedback.get("submission_content"),
            "max_marks": feedback["max_marks"],
            "final_score": feedback["final_score"],
            "overall_feedback": feedback.get("overall_feedback"),
            "strengths": feedback.get("strengths"),
            "weaknesses": feedback.get("weaknesses"),
            "criterion_feedback": feedback.get("criterion_feedback", []),
            "improvement_suggestions": feedback.get("improvement_suggestions"),
            "irrelevant_observations": feedback.get("irrelevant_observations", []),
            "final_remarks": feedback.get("final_remarks"),
            "deduction_reasons": feedback.get("deduction_reasons"),
        }
        pdf_bytes = generate_unified_pdf_report(report_data)

        filename = f"evaluation-report-{submission_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as exc:
        logger.error(f"PDF report generation failed: {exc}", exc_info=True)
        raise HTTPException(500, f"PDF report generation failed: {str(exc)}")



# ─── Dashboard ────────────────────────────────────────────────────────────────

@router.get("/dashboard")
def student_dashboard(db: Session = Depends(get_db), user=Depends(_require_student)):
    student = _get_student_profile(user, db)
    enrollments = db.query(SubjectEnrollment).filter(SubjectEnrollment.student_id == student.id).count()
    total_submissions = db.query(StudentSubmission).filter(StudentSubmission.student_id == student.id).count()
    approved = db.query(StudentSubmission).filter(
        StudentSubmission.student_id == student.id,
        StudentSubmission.status == SubmissionStatus.approved
    ).count()
    pending = db.query(StudentSubmission).filter(
        StudentSubmission.student_id == student.id,
        StudentSubmission.status.in_([SubmissionStatus.pending, SubmissionStatus.evaluated])
    ).count()

    return {
        "student_id": student.student_id,
        "full_name": user.full_name,
        "program": student.program,
        "year_of_study": student.year_of_study,
        "enrolled_subjects": enrollments,
        "total_submissions": total_submissions,
        "approved_submissions": approved,
        "pending_submissions": pending,
    }
