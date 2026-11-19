"""Faculty routes — course management, rubrics, assessments, faculty-first evaluation."""
import os
import uuid
import logging
import json
import mimetypes
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_faculty, get_current_user
from app.core.config import get_settings
from app.models.models import (
    User, FacultyProfile, StudentProfile, Subject, CourseProfile,
    CourseDocument, Assessment, MarkingRubric, RubricCriterion,
    StudentSubmission, AIEvaluation, CriterionScore, SupportingEvidence,
    ApprovedFeedback, AuditLog, SubjectFaculty, SubjectEnrollment,
    AssessmentType, RubricVersion, FacultyEvaluation, FinalEvaluation,
    UserRole, SubmissionStatus, EvaluationStatus
)
from app.schemas.schemas import (
    CourseDocumentOut,
    AssessmentOut,
    SubmissionOut, SubmissionDetailOut,
    EvaluationOut, EvaluationApproveRequest, ApprovedFeedbackOut,
    SubjectOut, CourseProfileTypedCreate, CourseProfileOut,
    FacultyEvaluationSubmitRequest, FacultyEvaluationOut
)
from app.services.document.processor import extract_text, validate_document, is_allowed_file, get_file_extension
from app.services.rag.pipeline import build_subject_index, retrieve_for_subject
from app.services.ai.evaluator import execute_ai_evaluation_job
from app.services.ai.context import resolve_rubric
from app.services.assessments import (
    assessments_for_subject, submissions_for_subject, submission_subject_id, submission_subject, subject_ids_of,
)

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/faculty", tags=["Faculty"])


def _get_faculty_profile(user: User, db: Session) -> FacultyProfile:
    profile = db.query(FacultyProfile).filter(FacultyProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(404, "Faculty profile not found")
    return profile


def _assert_subject_access(db: Session, user: User, subject_id: int) -> Subject:
    """Faculty may only work with subjects the admin assigned to them."""
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(404, "Subject not found")
    profile = _get_faculty_profile(user, db)
    assigned = db.query(SubjectFaculty).filter(
        SubjectFaculty.subject_id == subject_id, SubjectFaculty.faculty_id == profile.id
    ).first()
    if not assigned:
        raise HTTPException(403, "You are not assigned to this subject")
    return subject


def _owned_submission(db: Session, user: User, submission_id: int) -> StudentSubmission:
    """A submission belongs to the subject it was made through; only that subject's faculty may see it."""
    sub = db.query(StudentSubmission).filter(StudentSubmission.id == submission_id).first()
    if not sub or not sub.assessment:
        raise HTTPException(404, "Submission not found")
    _assert_subject_access(db, user, submission_subject_id(sub))
    return sub


def _log(db, user_id, action, rtype=None, rid=None, details=None):
    db.add(AuditLog(user_id=user_id, action=action, resource_type=rtype, resource_id=rid, details=details))


# ─── Subjects ─────────────────────────────────────────────────────────────────

@router.get("/subjects", response_model=List[SubjectOut])
def my_subjects(db: Session = Depends(get_db), user=Depends(require_faculty)):
    profile = _get_faculty_profile(user, db)
    assignments = db.query(SubjectFaculty).filter(SubjectFaculty.faculty_id == profile.id).all()
    subject_ids = [a.subject_id for a in assignments]
    return db.query(Subject).filter(Subject.id.in_(subject_ids), Subject.is_active == True).all()


# ─── Course Documents ─────────────────────────────────────────────────────────

@router.post("/subjects/{subject_id}/course-documents", response_model=CourseDocumentOut)
async def upload_course_document(
    subject_id: int,
    doc_type: str = Form(default="reference"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_faculty)
):
    _assert_subject_access(db, user, subject_id)
    if not is_allowed_file(file.filename):
        raise HTTPException(400, "File type not allowed. Supported: PDF, DOC/DOCX, PPT/PPTX, TXT, and common image formats.")

    course_profile = db.query(CourseProfile).filter(CourseProfile.subject_id == subject_id).first()
    if not course_profile:
        course_profile = CourseProfile(subject_id=subject_id, description=f"Course materials")
        db.add(course_profile)
        db.commit()
        db.refresh(course_profile)

    # Save file
    ext = get_file_extension(file.filename)
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    save_dir = Path(settings.upload_dir) / "course_docs" / str(subject_id)
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / unique_name

    contents = await file.read()
    with open(save_path, "wb") as f:
        f.write(contents)

    # Extract text
    try:
        validate_document(str(save_path))
        extracted_text, page_count = extract_text(str(save_path), ext)
    except Exception as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(422, f"Document processing failed: {str(e)}")

    if not extracted_text.strip():
        save_path.unlink(missing_ok=True)
        raise HTTPException(422, "Document appears empty or unreadable")

    doc = CourseDocument(
        course_profile_id=course_profile.id,
        filename=unique_name,
        original_filename=file.filename,
        file_type=ext,
        file_path=str(save_path),
        extracted_text=extracted_text,
        doc_type=doc_type,
        page_count=page_count,
        is_indexed=False,
    )
    db.add(doc)
    course_profile.rag_indexed = False
    _log(db, user.id, "upload_course_doc", "course_document", subject_id, file.filename)
    db.commit()
    db.refresh(doc)
    return doc


@router.post("/subjects/{subject_id}/build-index")
def build_rag_index(subject_id: int, db: Session = Depends(get_db), user=Depends(require_faculty)):
    """Build/rebuild the FAISS RAG index for a subject."""
    _assert_subject_access(db, user, subject_id)
    course_profile = db.query(CourseProfile).filter(CourseProfile.subject_id == subject_id).first()
    if not course_profile:
        course_profile = CourseProfile(subject_id=subject_id, description=f"Course materials")
        db.add(course_profile)
        db.commit()
        db.refresh(course_profile)

    documents = db.query(CourseDocument).filter(
        CourseDocument.course_profile_id == course_profile.id,
        CourseDocument.extracted_text.isnot(None)
    ).all()

    if not documents:
        raise HTTPException(400, "No course documents to index")

    doc_list = []
    for doc in documents:
        if doc.extracted_text and doc.extracted_text.strip():
            doc_list.append({
                "text": doc.extracted_text,
                "source_name": doc.original_filename,
                "doc_id": doc.id,
                "doc_type": doc.doc_type or "reference",
            })

    chunk_count = build_subject_index(subject_id, doc_list, settings.faiss_dir)

    course_profile.rag_indexed = True
    for doc in documents:
        doc.is_indexed = True
    _log(db, user.id, "build_rag_index", "subject", subject_id, f"{chunk_count} chunks")
    db.commit()

    return {"message": f"RAG index built successfully: {chunk_count} chunks indexed"}


@router.get("/subjects/{subject_id}/course-documents", response_model=List[CourseDocumentOut])
def list_course_documents(subject_id: int, db: Session = Depends(get_db), user=Depends(require_faculty)):
    _assert_subject_access(db, user, subject_id)
    profile = db.query(CourseProfile).filter(CourseProfile.subject_id == subject_id).first()
    if not profile:
        return []
    return db.query(CourseDocument).filter(CourseDocument.course_profile_id == profile.id).all()


# ─── Course Profiles (Upload + Typed) ─────────────────────────────────────────

@router.get("/subjects/{subject_id}/course-profile", response_model=CourseProfileOut)
def get_course_profile(subject_id: int, db: Session = Depends(get_db), user=Depends(require_faculty)):
    """Retrieve full course profile including typed syllabus, units, and learning objectives."""
    _assert_subject_access(db, user, subject_id)
    profile = db.query(CourseProfile).filter(CourseProfile.subject_id == subject_id).first()
    if not profile:
        profile = CourseProfile(subject_id=subject_id, description="Course materials")
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


@router.post("/subjects/{subject_id}/course-profile/typed", response_model=CourseProfileOut)
def save_typed_course_profile(
    subject_id: int,
    data: CourseProfileTypedCreate,
    db: Session = Depends(get_db),
    user=Depends(require_faculty)
):
    """
    Save or publish a typed course profile.
    When published, content is embedded and indexed in the subject FAISS RAG index.
    """
    _assert_subject_access(db, user, subject_id)
    profile = db.query(CourseProfile).filter(CourseProfile.subject_id == subject_id).first()
    if not profile:
        profile = CourseProfile(subject_id=subject_id)
        db.add(profile)
        db.flush()

    profile.title = data.title
    profile.description = data.description
    profile.syllabus = data.syllabus
    profile.learning_objectives = data.learning_objectives
    profile.expected_outcomes = data.expected_outcomes
    profile.units_topics = data.units_topics
    profile.reference_content = data.reference_content
    profile.learning_materials = data.learning_materials
    profile.additional_info = data.additional_info
    profile.is_typed_published = data.publish_requested

    if data.publish_requested:
        sections = [
            f"Course Title: {data.title or ''}",
            f"Course Description: {data.description or ''}",
            f"Syllabus: {data.syllabus or ''}",
            f"Learning Objectives: {data.learning_objectives or ''}",
            f"Expected Outcomes: {data.expected_outcomes or ''}",
            f"Reference Content: {data.reference_content or ''}",
            f"Learning Materials: {data.learning_materials or ''}",
            f"Additional Academic Info: {data.additional_info or ''}",
        ]
        if data.units_topics:
            sections.append(f"Units and Topics: {json.dumps(data.units_topics)}")

        full_profile_text = "\n\n".join(s for s in sections if s.strip())

        doc_list = [{
            "text": full_profile_text,
            "source_name": f"Typed Course Profile - {data.title or 'Subject ' + str(subject_id)}",
            "doc_id": profile.id,
            "doc_type": "syllabus",
        }]

        docs = db.query(CourseDocument).filter(
            CourseDocument.course_profile_id == profile.id,
            CourseDocument.extracted_text.isnot(None)
        ).all()
        for d in docs:
            if d.extracted_text and d.extracted_text.strip():
                doc_list.append({
                    "text": d.extracted_text,
                    "source_name": d.original_filename,
                    "doc_id": d.id,
                    "doc_type": d.doc_type or "reference",
                })

        chunk_count = build_subject_index(subject_id, doc_list, settings.faiss_dir)
        profile.rag_indexed = True
        _log(db, user.id, "publish_typed_course_profile", "course_profile", profile.id, f"{chunk_count} chunks indexed")

    db.commit()
    db.refresh(profile)
    return profile


# ─── Assessments & Assessment Types ───────────────────────────────────────────

# ─── Assessments (created and maintained by the admin; read-only for faculty) ──

@router.get("/subjects/{subject_id}/assessments")
def list_assessments(subject_id: int, db: Session = Depends(get_db), user=Depends(require_faculty)):
    """Assessments the admin mapped to this subject, with their rubric for reference."""
    _assert_subject_access(db, user, subject_id)
    out = []
    for a in assessments_for_subject(db, subject_id):
        rubric = resolve_rubric(db, a)
        subs = [s for s in submissions_for_subject(db, subject_id) if s.assessment_id == a.id and not s.is_draft]
        out.append({
            "id": a.id,
            "title": a.title,
            "description": a.description,
            "instructions": a.instructions,
            "assessment_type": a.assessment_type,
            "rubric_source": a.rubric_source,
            "evaluation_mode": rubric["evaluation_mode"],
            "max_marks": a.max_marks,
            "due_date": a.due_date.isoformat() if a.due_date else None,
            "course_unit": a.course_unit,
            "has_answer_key": bool(a.reference_answer),
            "shared_with": [sid for sid in subject_ids_of(db, a) if sid != subject_id],
            "criteria": [{"label": c["label"], "name": c["name"], "max_marks": c["max_marks"], "color": c["color"],
                          "levels": c.get("levels", [])} for c in rubric["criteria"]],
            "submission_count": len(subs),
            "rubric_version_id": a.rubric_version_id,
            "is_active": a.is_active,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })
    return out


# ─── Student Submissions ──────────────────────────────────────────────────────

@router.get("/subjects/{subject_id}/submissions")
def list_submissions_for_subject(subject_id: int, db: Session = Depends(get_db), user=Depends(require_faculty)):
    _assert_subject_access(db, user, subject_id)
    submissions = [s for s in submissions_for_subject(db, subject_id) if not s.is_draft]

    result = []
    for s in submissions:
        result.append({
            "id": s.id,
            "student_name": s.student.user.full_name if s.student and s.student.user else "Unknown",
            "student_id": s.student.student_id if s.student else None,
            "assessment_title": s.assessment.title if s.assessment else "Unknown",
            "assessment_id": s.assessment_id,
            "original_filename": s.original_filename,
            "file_type": s.file_type,
            "status": s.status.value,
            "submitted_at": s.submitted_at.isoformat(),
            "has_evaluation": s.evaluation is not None,
        })
    return result


def _recover_text(db: Session, sub: StudentSubmission) -> None:
    """Re-extract text when an earlier extraction failed but the file is still present."""
    if (not sub.extracted_text or not sub.extracted_text.strip()) and sub.file_path and os.path.exists(sub.file_path):
        try:
            text, pages = extract_text(sub.file_path, sub.file_type)
            if text and text.strip():
                sub.extracted_text, sub.page_count, sub.extraction_status = text, pages, "success"
                db.commit()
                db.refresh(sub)
        except Exception as e:
            logger.warning(f"Recovery extraction failed for submission {sub.id}: {e}")


@router.get("/submissions/{submission_id}")
def get_submission_detail(submission_id: int, db: Session = Depends(get_db), user=Depends(require_faculty)):
    s = _owned_submission(db, user, submission_id)
    _recover_text(db, s)
    return {
        "id": s.id,
        "student_name": s.student.user.full_name if s.student and s.student.user else "Unknown",
        "student_id_num": s.student.student_id if s.student else None,
        "assessment_title": s.assessment.title,
        "assessment_description": s.assessment.description,
        "subject_name": (submission_subject(db, s).name if submission_subject(db, s) else "Unknown"),
        "assessment_id": s.assessment_id,
        "assessment_max_marks": s.assessment.max_marks,
        "original_filename": s.original_filename,
        "file_type": s.file_type,
        "file_size": s.file_size,
        "extracted_text": s.extracted_text,
        "extraction_status": s.extraction_status,
        "status": s.status.value,
        "submitted_at": s.submitted_at.isoformat(),
        "has_evaluation": s.evaluation is not None,
    }


@router.get("/submissions/{submission_id}/file")
def get_submission_file(
    submission_id: int,
    download: bool = Query(default=False),
    db: Session = Depends(get_db),
    user=Depends(require_faculty),
):
    """View or download the original file submitted by a student."""
    from fastapi.responses import FileResponse

    submission = _owned_submission(db, user, submission_id)
    if not submission.file_path or not os.path.isfile(submission.file_path):
        raise HTTPException(404, "Submitted file is no longer available")
    media_type = mimetypes.guess_type(submission.original_filename or submission.file_path)[0] or "application/octet-stream"
    return FileResponse(
        submission.file_path,
        media_type=media_type,
        filename=submission.original_filename or "student-submission",
        content_disposition_type="attachment" if download else "inline",
    )


# ─── Faculty evaluation (faculty marks first, then the AI evaluates independently) ──

def _evaluation_state(db: Session, submission_id: int) -> dict:
    """Progress of the AI step and publication — never exposes the AI marks to faculty."""
    ai = db.query(AIEvaluation).filter(AIEvaluation.submission_id == submission_id).first()
    final = db.query(FinalEvaluation).filter(FinalEvaluation.submission_id == submission_id).first()
    return {
        "ai_status": ai.ai_status if ai else "not_started",
        "ai_error": ai.error_details if ai and ai.ai_status == "failed" else None,
        "published": bool(final and final.is_published and final.feedback_document),
        "published_at": final.published_at.isoformat() if final and final.published_at else None,
    }


@router.get("/submissions/{submission_id}/evaluation-context")
def get_submission_evaluation_context(
    submission_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_faculty),
):
    """Submission content, assessment brief, the RTLP rubric (scaled to the assessment's marks)
    and the faculty member's saved evaluation."""
    sub = _owned_submission(db, user, submission_id)
    _recover_text(db, sub)
    assess, stud = sub.assessment, sub.student
    rubric = resolve_rubric(db, assess, sub)
    faculty_eval = db.query(FacultyEvaluation).filter(FacultyEvaluation.submission_id == submission_id).first()

    return {
        "submission_id": sub.id,
        "student_name": stud.user.full_name if stud and stud.user else "Unknown",
        "student_id": stud.student_id if stud else "",
        "subject_name": (submission_subject(db, sub).name if submission_subject(db, sub) else "Unknown"),
        "assessment_id": assess.id,
        "assessment_title": assess.title,
        "assessment_type": rubric["type_name"],
        "rtlp_code": rubric["rtlp_code"],
        "evaluation_mode": rubric["evaluation_mode"],
        "assessment_description": assess.description,
        "instructions": assess.instructions,
        "course_unit": assess.course_unit,
        "has_answer_key": bool(assess.reference_answer),
        "max_marks": assess.max_marks,
        "submission_type": sub.submission_type or "upload",
        "original_filename": sub.original_filename,
        "submitted_at": sub.submitted_at.isoformat(),
        "submission_text": sub.typed_content or sub.extracted_text or "",
        "rubric_reference": {
            "version": rubric["version"],
            "total_marks": assess.max_marks,
            "criteria": rubric["criteria"],
        } if rubric["criteria"] else None,
        "faculty_evaluation": {
            "id": faculty_eval.id,
            "faculty_total_marks": faculty_eval.faculty_total_marks,
            "criterion_marks": faculty_eval.criterion_marks or [],
            "overall_feedback": faculty_eval.overall_feedback,
            "strengths": faculty_eval.strengths,
            "weaknesses": faculty_eval.weaknesses,
            "improvement_suggestions": faculty_eval.improvement_suggestions,
            "irrelevant_observations": faculty_eval.irrelevant_observations,
            "deduction_reasons": faculty_eval.deduction_reasons,
            "internal_notes": faculty_eval.internal_notes,
            "is_draft": faculty_eval.is_draft,
        } if faculty_eval else None,
        "evaluation_state": _evaluation_state(db, submission_id),
    }


@router.post("/submissions/{submission_id}/manual-evaluate")
@router.post("/submissions/{submission_id}/evaluate")
def submit_faculty_evaluation(
    submission_id: int,
    data: FacultyEvaluationSubmitRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(require_faculty),
):
    """
    Faculty marks the submission against every rubric criterion (the total is the sum).
    Submitting (is_draft=False) starts the independent AI evaluation in the background; the
    student's final mark is the average of the faculty and AI marks.
    """
    sub = _owned_submission(db, user, submission_id)
    assess = sub.assessment
    rubric = resolve_rubric(db, assess, sub)
    criteria = rubric["criteria"]

    marks = None
    total = float(data.faculty_total_marks)
    if criteria and data.criterion_marks is not None:
        given = {m.criterion_name.strip().lower(): m.score for m in data.criterion_marks}
        marks = []
        for c in criteria:
            score = given.get(c["name"].strip().lower())
            if score is None:
                if data.is_draft:
                    continue
                raise HTTPException(400, f"Enter a mark for '{c['name']}'.")
            if score < 0 or score > float(c["max_marks"]) + 1e-9:
                raise HTTPException(400, f"'{c['name']}' must be between 0 and {c['max_marks']:g}.")
            marks.append({"criterion_name": c["name"], "max_marks": float(c["max_marks"]), "score": round(float(score), 2)})
        if len(marks) == len(criteria):
            total = round(sum(m["score"] for m in marks), 2)
    elif criteria and not data.is_draft:
        raise HTTPException(400, "Mark every rubric criterion before submitting.")

    if total < 0 or total > assess.max_marks + 1e-9:
        raise HTTPException(400, f"Total marks must be between 0 and {assess.max_marks:g}.")
    if not data.is_draft and not (data.overall_feedback or "").strip():
        raise HTTPException(400, "Overall feedback is required before submitting.")

    faculty_eval = db.query(FacultyEvaluation).filter(FacultyEvaluation.submission_id == submission_id).first()
    if not faculty_eval:
        faculty_eval = FacultyEvaluation(submission_id=submission_id, faculty_id=user.id, faculty_total_marks=total)
        db.add(faculty_eval)
    faculty_eval.faculty_id = user.id
    faculty_eval.faculty_total_marks = total
    faculty_eval.criterion_marks = marks
    faculty_eval.overall_feedback = data.overall_feedback
    faculty_eval.strengths = data.strengths
    faculty_eval.weaknesses = data.weaknesses
    faculty_eval.improvement_suggestions = data.improvement_suggestions
    faculty_eval.irrelevant_observations = data.irrelevant_observations
    faculty_eval.deduction_reasons = data.deduction_reasons
    faculty_eval.internal_notes = data.internal_notes
    faculty_eval.is_draft = data.is_draft

    _log(db, user.id, "faculty_eval_draft" if data.is_draft else "faculty_eval_submitted",
         "submission", submission_id, f"Mark: {total}/{assess.max_marks}")
    db.commit()

    if data.is_draft:
        return {"message": "Draft saved.", "status": "draft", "faculty_total_marks": total}
    background_tasks.add_task(execute_ai_evaluation_job, submission_id, user.id)
    return {
        "message": "Evaluation submitted. The AI evaluation is running; the student's feedback document is "
                   "published automatically when it finishes.",
        "status": "submitted",
        "faculty_total_marks": total,
    }


@router.get("/submissions/{submission_id}/faculty-evaluation")
def get_faculty_evaluation(submission_id: int, db: Session = Depends(get_db), user=Depends(require_faculty)):
    _owned_submission(db, user, submission_id)
    fe = db.query(FacultyEvaluation).filter(FacultyEvaluation.submission_id == submission_id).first()
    if not fe:
        raise HTTPException(404, "Faculty evaluation not found")
    return {
        "id": fe.id,
        "submission_id": fe.submission_id,
        "faculty_total_marks": fe.faculty_total_marks,
        "criterion_marks": fe.criterion_marks or [],
        "overall_feedback": fe.overall_feedback,
        "strengths": fe.strengths,
        "weaknesses": fe.weaknesses,
        "improvement_suggestions": fe.improvement_suggestions,
        "irrelevant_observations": fe.irrelevant_observations,
        "deduction_reasons": fe.deduction_reasons,
        "internal_notes": fe.internal_notes,
        "is_draft": fe.is_draft,
        "updated_at": fe.updated_at.isoformat() if fe.updated_at else None,
    }


@router.get("/submissions/{submission_id}/evaluation-status")
def get_evaluation_status(submission_id: int, db: Session = Depends(get_db), user=Depends(require_faculty)):
    _owned_submission(db, user, submission_id)
    return _evaluation_state(db, submission_id)


@router.get("/submissions/{submission_id}/feedback-document")
def get_published_feedback_document(submission_id: int, db: Session = Depends(get_db), user=Depends(require_faculty)):
    """The feedback document exactly as the student sees it (available once published)."""
    _owned_submission(db, user, submission_id)
    final = db.query(FinalEvaluation).filter(FinalEvaluation.submission_id == submission_id).first()
    if not final or not final.is_published or not final.feedback_document:
        raise HTTPException(404, "The feedback document has not been published yet.")
    return final.feedback_document


@router.get("/submissions/{submission_id}/feedback.pdf")
def download_published_feedback_pdf(submission_id: int, db: Session = Depends(get_db), user=Depends(require_faculty)):
    from fastapi.responses import Response
    from app.services.report.feedback_pdf import render_feedback_pdf

    document = get_published_feedback_document(submission_id, db, user)
    return Response(content=render_feedback_pdf(document), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="feedback-{submission_id}.pdf"'})


@router.get("/submissions/{submission_id}/evaluation", response_model=EvaluationOut)
def get_evaluation(submission_id: int, db: Session = Depends(get_db), user=Depends(require_faculty)):
    _owned_submission(db, user, submission_id)
    evaluation = db.query(AIEvaluation).filter(AIEvaluation.submission_id == submission_id).first()
    if not evaluation:
        raise HTTPException(404, "No evaluation found for this submission")
    result = EvaluationOut.model_validate(evaluation).model_dump()
    for field in ("openai_model_used", "tokens_used", "evaluation_duration_seconds"):
        result.pop(field, None)
    return result


@router.put("/evaluations/{evaluation_id}/approve", response_model=ApprovedFeedbackOut)
def approve_evaluation(
    evaluation_id: int,
    data: EvaluationApproveRequest,
    db: Session = Depends(get_db),
    user=Depends(require_faculty)
):
    evaluation = db.query(AIEvaluation).filter(AIEvaluation.id == evaluation_id).first()
    if not evaluation:
        raise HTTPException(404, "Evaluation not found")
    _owned_submission(db, user, evaluation.submission_id)

    assessment = evaluation.submission.assessment
    if data.faculty_total_score < 0 or data.faculty_total_score > assessment.max_marks:
        raise HTTPException(400, f"Final score must be between 0 and {assessment.max_marks}.")

    evaluation.faculty_total_score = data.faculty_total_score
    evaluation.faculty_feedback = data.faculty_feedback
    evaluation.faculty_notes = data.faculty_notes
    evaluation.status = EvaluationStatus.approved

    if data.criterion_overrides:
        for override in data.criterion_overrides:
            cs = db.query(CriterionScore).filter(CriterionScore.id == override.criterion_score_id).first()
            if cs and cs.evaluation_id == evaluation_id:
                if override.faculty_score > cs.max_marks:
                    raise HTTPException(400, f"Score for '{cs.criterion_name}' must be between 0 and {cs.max_marks}.")
                cs.faculty_score = override.faculty_score

    af = db.query(ApprovedFeedback).filter(ApprovedFeedback.evaluation_id == evaluation_id).first()
    feedback_text = data.faculty_feedback or evaluation.ai_feedback or evaluation.ai_overall_feedback or ""
    if af:
        af.final_score = data.faculty_total_score
        af.final_feedback = feedback_text
        af.is_published = data.publish_to_student or af.is_published
        af.approved_by_id = user.id
    else:
        af = ApprovedFeedback(evaluation_id=evaluation_id, final_score=data.faculty_total_score,
                              final_feedback=feedback_text, is_published=data.publish_to_student,
                              approved_by_id=user.id)
        db.add(af)

    evaluation.submission.status = SubmissionStatus.approved
    _log(db, user.id, "approve_evaluation", "evaluation", evaluation_id,
         f"Final score: {data.faculty_total_score}, published: {data.publish_to_student}")
    db.commit()
    db.refresh(af)
    return af


@router.put("/evaluations/{evaluation_id}/reject")
def reject_evaluation(evaluation_id: int, db: Session = Depends(get_db), user=Depends(require_faculty)):
    evaluation = db.query(AIEvaluation).filter(AIEvaluation.id == evaluation_id).first()
    if not evaluation:
        raise HTTPException(404, "Evaluation not found")
    _owned_submission(db, user, evaluation.submission_id)
    evaluation.status = EvaluationStatus.rejected
    evaluation.submission.status = SubmissionStatus.rejected
    _log(db, user.id, "reject_evaluation", "evaluation", evaluation_id)
    db.commit()
    return {"message": "Evaluation rejected"}


# ─── Students in Subject ──────────────────────────────────────────────────────

@router.get("/subjects/{subject_id}/students")
def list_enrolled_students(subject_id: int, db: Session = Depends(get_db), user=Depends(require_faculty)):
    _assert_subject_access(db, user, subject_id)
    enrollments = db.query(SubjectEnrollment).filter(SubjectEnrollment.subject_id == subject_id).all()
    result = []
    for e in enrollments:
        sp = e.student
        if sp and sp.user:
            result.append({
                "user_id": sp.user_id,
                "full_name": sp.user.full_name,
                "email": sp.user.email,
                "student_id": sp.student_id,
                "program": sp.program,
            })
    return result
