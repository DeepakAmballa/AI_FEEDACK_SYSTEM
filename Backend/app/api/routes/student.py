"""Student routes — submissions, results, subject views."""
import os
import uuid
import logging
import json
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.config import get_settings
from app.models.models import (
    User, StudentProfile, Subject, Assessment, StudentSubmission,
    AIEvaluation, ApprovedFeedback, SubjectEnrollment,
    UserRole, SubmissionStatus
)
from app.schemas.schemas import SubmissionOut, AssessmentOut, SubjectOut
from app.services.document.processor import extract_text, validate_document, is_allowed_file, get_file_extension

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/student", tags=["Student"])


def _get_student_profile(user: User, db: Session) -> StudentProfile:
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(404, "Student profile not found")
    return profile


def _require_student(user: User = Depends(get_current_user)) -> User:
    if user.role not in (UserRole.student, UserRole.admin):
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

    assessments = db.query(Assessment).filter(
        Assessment.subject_id == subject_id,
        Assessment.is_active == True
    ).all()

    result = []
    for a in assessments:
        # Check if student already submitted
        sub = db.query(StudentSubmission).filter(
            StudentSubmission.assessment_id == a.id,
            StudentSubmission.student_id == student.id,
        ).first()
        result.append({
            "id": a.id,
            "title": a.title,
            "description": a.description,
            "assessment_type": a.assessment_type,
            "max_marks": a.max_marks,
            "due_date": a.due_date.isoformat() if a.due_date else None,
            "submitted": sub is not None,
            "submission_status": sub.status.value if sub else None,
        })
    return result


# ─── Submissions ──────────────────────────────────────────────────────────────

@router.post("/assessments/{assessment_id}/submit")
async def submit_assignment(
    assessment_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(_require_student)
):
    student = _get_student_profile(user, db)

    if not is_allowed_file(file.filename):
        raise HTTPException(400, "File type not allowed. Supported: PDF, DOC/DOCX, PPT/PPTX, TXT, and common image formats.")

    assessment = db.query(Assessment).filter(Assessment.id == assessment_id, Assessment.is_active == True).first()
    if not assessment:
        raise HTTPException(404, "Assessment not found")

    # Check enrollment
    enrollment = db.query(SubjectEnrollment).filter(
        SubjectEnrollment.subject_id == assessment.subject_id,
        SubjectEnrollment.student_id == student.id,
    ).first()
    if not enrollment and user.role != UserRole.admin:
        raise HTTPException(403, "You are not enrolled in this subject")

    # Check for existing submission
    existing = db.query(StudentSubmission).filter(
        StudentSubmission.assessment_id == assessment_id,
        StudentSubmission.student_id == student.id,
    ).first()
    if existing and existing.status == SubmissionStatus.approved:
        raise HTTPException(400, "Your submission has already been approved and evaluated. Re-submission is closed.")

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


@router.get("/submissions")
def my_submissions(db: Session = Depends(get_db), user=Depends(_require_student)):
    student = _get_student_profile(user, db)
    submissions = db.query(StudentSubmission).filter(
        StudentSubmission.student_id == student.id
    ).order_by(StudentSubmission.submitted_at.desc()).all()

    result = []
    for s in submissions:
        result.append({
            "id": s.id,
            "assessment_title": s.assessment.title if s.assessment else "Unknown",
            "subject_name": s.assessment.subject.name if s.assessment and s.assessment.subject else "Unknown",
            "original_filename": s.original_filename,
            "file_type": s.file_type,
            "status": s.status.value,
            "submitted_at": s.submitted_at.isoformat(),
            "has_feedback": s.evaluation is not None and s.evaluation.approved_feedback is not None,
        })
    return result


# ─── View Results ─────────────────────────────────────────────────────────────

@router.get("/submissions/{submission_id}/feedback")
def get_feedback(submission_id: int, db: Session = Depends(get_db), user=Depends(_require_student)):
    student = _get_student_profile(user, db)
    submission = db.query(StudentSubmission).filter(
        StudentSubmission.id == submission_id,
        StudentSubmission.student_id == student.id
    ).first()
    if not submission:
        raise HTTPException(404, "Submission not found")

    if not submission.evaluation or not submission.evaluation.approved_feedback:
        return {"message": "No approved feedback available yet. Please wait for faculty review."}

    af = submission.evaluation.approved_feedback
    if not af.is_published:
        return {"message": "Feedback has been approved but not yet published. Please wait."}

    evaluation = submission.evaluation
    criterion_scores = []
    for cs in evaluation.criterion_scores:
        criterion_scores.append({
            "criterion_name": cs.criterion_name,
            "max_marks": cs.max_marks,
            "score": cs.faculty_score if cs.faculty_score is not None else cs.ai_score,
        })

    result = {
        "student_name": user.full_name,
        "assessment_title": submission.assessment.title if submission.assessment else "Unknown",
        "assessment_description": submission.assessment.description if submission.assessment else None,
        "subject_name": submission.assessment.subject.name if submission.assessment and submission.assessment.subject else "Unknown",
        "submitted_at": submission.submitted_at.isoformat(),
        "max_marks": submission.assessment.max_marks if submission.assessment else None,
        "final_score": af.final_score,
        "final_feedback": af.final_feedback,
        "approved_at": af.approved_at.isoformat(),
        "criterion_scores": criterion_scores,
        "strengths": evaluation.ai_strengths,
        "weaknesses": evaluation.ai_weaknesses,
        "improvement_suggestions": evaluation.ai_improvement_suggestions,
        "missing_concepts": evaluation.ai_missing_concepts,
        "subject_relevance": evaluation.ai_feedback,
    }
    try:
        raw = json.loads(evaluation.ai_raw_response or "{}")
        result.update({
            key: raw[key]
            for key in (
                "subject_relevant", "relevance_explanation", "style_feedback",
                "language_errors", "line_feedback", "comparative_analysis_feedback",
                "compared_elements",
            )
            if key in raw
        })
    except (TypeError, json.JSONDecodeError):
        logger.warning("Stored evaluation details are not valid structured JSON: %s", evaluation.id)
    return result


@router.get("/submissions/{submission_id}/feedback.pdf")
def download_feedback_pdf(
    submission_id: int,
    db: Session = Depends(get_db),
    user=Depends(_require_student),
):
    """Return a downloadable PDF for a published student evaluation report."""
    student = _get_student_profile(user, db)
    submission = db.query(StudentSubmission).filter(
        StudentSubmission.id == submission_id,
        StudentSubmission.student_id == student.id,
    ).first()
    if not submission or not submission.evaluation or not submission.evaluation.approved_feedback:
        raise HTTPException(404, "Published feedback not found")
    feedback = get_feedback(submission_id, db, user)
    if feedback.get("message"):
        raise HTTPException(404, feedback["message"])

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        from io import BytesIO
        from xml.sax.saxutils import escape

        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
            topMargin=16 * mm, bottomMargin=16 * mm,
        )
        styles = getSampleStyleSheet()
        body = ParagraphStyle("ReportBody", parent=styles["BodyText"], leading=15, spaceAfter=6)
        small = ParagraphStyle("ReportSmall", parent=body, fontSize=9, textColor=colors.HexColor("#475569"))
        story = [
            Paragraph("EduEval AI Evaluation Report", styles["Title"]),
            Paragraph(f"<b>Student:</b> {feedback['student_name']}", body),
            Paragraph(f"<b>Assessment:</b> {feedback['assessment_title']}", body),
            Paragraph(f"<b>Subject:</b> {feedback['subject_name']}", body),
        ]
        if feedback.get("assessment_description"):
            story.append(Paragraph(f"<b>Question / brief:</b> {feedback['assessment_description']}", body))
        story.extend([
            Paragraph(
                f"<b>Final score:</b> {feedback['final_score']} / {feedback['max_marks']}",
                body,
            ),
            Spacer(1, 6),
        ])
        rows = [["Criterion", "Score", "Maximum"]]
        rows.extend([
            [item["criterion_name"], str(item["score"]), str(item["max_marks"])]
            for item in feedback.get("criterion_scores", [])
        ])
        if len(rows) > 1:
            table = Table(rows, colWidths=[110 * mm, 25 * mm, 25 * mm], repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]))
            story.extend([table, Spacer(1, 10)])

        sections = [
            ("Faculty feedback", feedback.get("final_feedback")),
            ("Strengths", feedback.get("strengths")),
            ("Weaknesses", feedback.get("weaknesses")),
            ("Improvement suggestions", feedback.get("improvement_suggestions")),
            ("Missing concepts", feedback.get("missing_concepts")),
            ("Relevance explanation", feedback.get("relevance_explanation")),
            ("Comparative analysis", feedback.get("comparative_analysis_feedback")),
        ]
        for title, text in sections:
            if text:
                story.extend([Paragraph(title, styles["Heading2"]), Paragraph(escape(str(text)), body)])
        if feedback.get("style_feedback"):
            story.extend([Paragraph("Style feedback", styles["Heading2"])])
            story.extend(Paragraph(f"• {escape(str(item))}", body) for item in feedback["style_feedback"])
        if feedback.get("language_errors"):
            story.extend([Paragraph("Language and proofreading", styles["Heading2"])])
            story.extend(Paragraph(f"• {escape(str(item))}", body) for item in feedback["language_errors"])
        if feedback.get("line_feedback"):
            story.append(Paragraph("Line-level notes", styles["Heading2"]))
            for item in feedback["line_feedback"]:
                story.append(Paragraph(
                    f"Line {item.get('line_number', '?')} ({item.get('category', 'note')}): "
                    f"{escape(str(item.get('comment', '')))}",
                    small,
                ))
        document.build(story)
        filename = f"evaluation-report-{submission_id}.pdf"
        return Response(
            content=buffer.getvalue(),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ImportError as exc:
        logger.error("PDF report dependency unavailable: %s", exc)
        raise HTTPException(503, "PDF report generation is unavailable on this server.") from exc


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
