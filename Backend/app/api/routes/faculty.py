"""Faculty routes — course management, rubrics, assessments, AI evaluation."""
import os
import uuid
import logging
import json
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_faculty, get_current_user
from app.core.config import get_settings
from app.models.models import (
    User, FacultyProfile, StudentProfile, Subject, CourseProfile,
    CourseDocument, Assessment, MarkingRubric, RubricCriterion,
    StudentSubmission, AIEvaluation, CriterionScore, SupportingEvidence,
    ApprovedFeedback, AuditLog, SubjectFaculty, SubjectEnrollment,
    UserRole, SubmissionStatus, EvaluationStatus
)
from app.schemas.schemas import (
    CourseDocumentOut,
    AssessmentCreate, AssessmentOut,
    RubricCreate, RubricOut,
    SubmissionOut, SubmissionDetailOut,
    EvaluationOut, EvaluationApproveRequest, ApprovedFeedbackOut,
    SubjectOut
)
from app.services.document.processor import extract_text, validate_document, is_allowed_file, get_file_extension
from app.services.rag.pipeline import build_subject_index, retrieve_for_subject
from app.services.ai.evaluator import evaluate_submission, EvaluationInput
from app.services.ai.rubric_scorer import RubricScorer

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/faculty", tags=["Faculty"])


def _get_faculty_profile(user: User, db: Session) -> FacultyProfile:
    if user.role == UserRole.admin:
        return db.query(FacultyProfile).first()  # admin can act as faculty
    profile = db.query(FacultyProfile).filter(FacultyProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(404, "Faculty profile not found")
    return profile


def _log(db, user_id, action, rtype=None, rid=None, details=None):
    db.add(AuditLog(user_id=user_id, action=action, resource_type=rtype, resource_id=rid, details=details))


# ─── Subjects ─────────────────────────────────────────────────────────────────

@router.get("/subjects", response_model=List[SubjectOut])
def my_subjects(db: Session = Depends(get_db), user=Depends(require_faculty)):
    if user.role == UserRole.admin:
        return db.query(Subject).filter(Subject.is_active == True).all()
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
    profile = db.query(CourseProfile).filter(CourseProfile.subject_id == subject_id).first()
    if not profile:
        return []
    return db.query(CourseDocument).filter(CourseDocument.course_profile_id == profile.id).all()


# ─── Assessments ──────────────────────────────────────────────────────────────

@router.post("/assessments", response_model=AssessmentOut)
def create_assessment(data: AssessmentCreate, db: Session = Depends(get_db), user=Depends(require_faculty)):
    subject = db.query(Subject).filter(Subject.id == data.subject_id).first()
    if not subject:
        raise HTTPException(404, "Subject not found")
    assessment = Assessment(**data.model_dump())
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment


@router.get("/subjects/{subject_id}/assessments", response_model=List[AssessmentOut])
def list_assessments(subject_id: int, db: Session = Depends(get_db), user=Depends(require_faculty)):
    return db.query(Assessment).filter(Assessment.subject_id == subject_id, Assessment.is_active == True).all()


@router.put("/assessments/{assessment_id}", response_model=AssessmentOut)
def update_assessment(assessment_id: int, data: AssessmentCreate, db: Session = Depends(get_db), user=Depends(require_faculty)):
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(404, "Assessment not found")
    for field, val in data.model_dump(exclude_none=True).items():
        setattr(assessment, field, val)
    db.commit()
    db.refresh(assessment)
    return assessment


# ─── Rubrics ──────────────────────────────────────────────────────────────────

@router.post("/assessments/{assessment_id}/rubric", response_model=RubricOut)
def create_rubric(assessment_id: int, data: RubricCreate, db: Session = Depends(get_db), user=Depends(require_faculty)):
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(404, "Assessment not found")

    # Validate criteria sum
    criteria_sum = sum(c.max_marks for c in data.criteria)
    if abs(criteria_sum - data.total_marks) > 0.5:
        raise HTTPException(400, f"Criteria marks ({criteria_sum}) must sum to total marks ({data.total_marks})")

    # Remove existing rubric
    existing = db.query(MarkingRubric).filter(MarkingRubric.assessment_id == assessment_id).first()
    if existing:
        db.delete(existing)
        db.flush()

    rubric = MarkingRubric(
        assessment_id=assessment_id,
        description=data.description,
        total_marks=data.total_marks,
    )
    db.add(rubric)
    db.flush()

    for i, c in enumerate(data.criteria):
        criterion = RubricCriterion(
            rubric_id=rubric.id,
            name=c.name,
            description=c.description,
            max_marks=c.max_marks,
            weight=c.weight,
            order_index=i,
        )
        db.add(criterion)

    assessment.max_marks = data.total_marks
    db.commit()
    db.refresh(rubric)
    return rubric


@router.get("/assessments/{assessment_id}/rubric", response_model=RubricOut)
def get_rubric(assessment_id: int, db: Session = Depends(get_db), user=Depends(require_faculty)):
    rubric = db.query(MarkingRubric).filter(MarkingRubric.assessment_id == assessment_id).first()
    if not rubric:
        raise HTTPException(404, "No rubric defined for this assessment")
    return rubric


@router.get("/rubric-templates")
def list_rubric_templates(user=Depends(require_faculty)):
    """Return reusable rubric presets that faculty can adapt per assessment."""
    return [
        {
            "id": "essay",
            "name": "Essay / Literary Analysis",
            "criteria": [
                {"name": "Thesis and argument", "description": "Clear, focused claim supported throughout.", "proportion": 0.25},
                {"name": "Evidence and analysis", "description": "Relevant evidence with meaningful interpretation.", "proportion": 0.30},
                {"name": "Subject knowledge", "description": "Accurate use of course concepts and terminology.", "proportion": 0.20},
                {"name": "Organization", "description": "Logical structure and coherent progression.", "proportion": 0.15},
                {"name": "Language and presentation", "description": "Clarity, grammar, citation, and formatting.", "proportion": 0.10},
            ],
        },
        {
            "id": "technical",
            "name": "Technical Assignment",
            "criteria": [
                {"name": "Conceptual understanding", "description": "Correct understanding of the required concepts.", "proportion": 0.25},
                {"name": "Implementation", "description": "Correctness, completeness, and technical execution.", "proportion": 0.35},
                {"name": "Testing and evidence", "description": "Validation, examples, and supporting evidence.", "proportion": 0.15},
                {"name": "Explanation", "description": "Clear explanation of decisions and results.", "proportion": 0.15},
                {"name": "Presentation", "description": "Readable structure and professional presentation.", "proportion": 0.10},
            ],
        },
        {
            "id": "journal",
            "name": "Reflective Journal",
            "criteria": [
                {"name": "Reflection and insight", "description": "Depth of personal learning and reflection.", "proportion": 0.30},
                {"name": "Connection to course", "description": "Meaningful connection to subject concepts.", "proportion": 0.25},
                {"name": "Evidence of progress", "description": "Specific experiences, examples, or evidence.", "proportion": 0.20},
                {"name": "Critical thinking", "description": "Analysis of challenges, choices, and outcomes.", "proportion": 0.15},
                {"name": "Communication", "description": "Clear, organized, and accurate writing.", "proportion": 0.10},
            ],
        },
    ]


# ─── Student Submissions ──────────────────────────────────────────────────────

@router.get("/subjects/{subject_id}/submissions")
def list_submissions_for_subject(subject_id: int, db: Session = Depends(get_db), user=Depends(require_faculty)):
    assessments = db.query(Assessment).filter(Assessment.subject_id == subject_id).all()
    assessment_ids = [a.id for a in assessments]
    submissions = db.query(StudentSubmission).filter(
        StudentSubmission.assessment_id.in_(assessment_ids)
    ).order_by(StudentSubmission.submitted_at.desc()).all()

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


@router.get("/submissions/{submission_id}")
def get_submission_detail(submission_id: int, db: Session = Depends(get_db), user=Depends(require_faculty)):
    s = db.query(StudentSubmission).filter(StudentSubmission.id == submission_id).first()
    if not s:
        raise HTTPException(404, "Submission not found")

    # If extraction previously failed or is empty, attempt recovery if file exists
    if (not s.extracted_text or not s.extracted_text.strip()) and s.file_path and os.path.exists(s.file_path):
        try:
            from app.services.document.processor import extract_text
            text, pages = extract_text(s.file_path, s.file_type)
            if text and text.strip():
                s.extracted_text = text
                s.page_count = pages
                s.extraction_status = "success"
                db.commit()
                db.refresh(s)
        except Exception as e:
            logger.warning(f"Recovery extraction failed for submission {s.id}: {e}")

    return {
        "id": s.id,
        "student_name": s.student.user.full_name if s.student and s.student.user else "Unknown",
        "student_id_num": s.student.student_id if s.student else None,
        "assessment_title": s.assessment.title if s.assessment else "Unknown",
        "assessment_description": s.assessment.description if s.assessment else None,
        "subject_name": s.assessment.subject.name if s.assessment and s.assessment.subject else "Unknown",
        "assessment_id": s.assessment_id,
        "assessment_max_marks": s.assessment.max_marks if s.assessment else None,
        "original_filename": s.original_filename,
        "file_type": s.file_type,
        "file_size": s.file_size,
        "extracted_text": s.extracted_text,
        "extraction_status": s.extraction_status,
        "status": s.status.value,
        "submitted_at": s.submitted_at.isoformat(),
        "has_evaluation": s.evaluation is not None,
    }


# ─── AI Evaluation ────────────────────────────────────────────────────────────

@router.post("/submissions/{submission_id}/evaluate")
def trigger_evaluation(submission_id: int, db: Session = Depends(get_db), user=Depends(require_faculty)):
    """Trigger AI evaluation for a student submission."""
    submission = db.query(StudentSubmission).filter(StudentSubmission.id == submission_id).first()
    if not submission:
        raise HTTPException(404, "Submission not found")

    # Evaluation is intentionally idempotent. Re-evaluation must not replace
    # AI results or faculty overrides that are already under review/published.
    existing_eval = db.query(AIEvaluation).filter(
        AIEvaluation.submission_id == submission_id
    ).first()
    if existing_eval:
        return {
            "message": "Existing AI evaluation returned unchanged",
            "evaluation_id": existing_eval.id,
            "ai_total_score": existing_eval.ai_total_score,
            "reused_existing": True,
        }

    from app.core.config import get_settings
    cfg = get_settings()

    if not cfg.openai_configured:
        raise HTTPException(503, (
            "OpenAI API key not configured. "
            "Please open Backend/.env and set OPENAI_API_KEY=<your_key>. "
            "Save the file to enable AI evaluation."
        ))

    if not submission.extracted_text or not submission.extracted_text.strip():
        # Attempt recovery if file exists on disk
        if submission.file_path and os.path.exists(submission.file_path):
            try:
                from app.services.document.processor import extract_text
                text, pages = extract_text(submission.file_path, submission.file_type)
                if text and text.strip():
                    submission.extracted_text = text
                    submission.page_count = pages
                    submission.extraction_status = "success"
                    db.commit()
                    db.refresh(submission)
            except Exception as ex:
                logger.error(f"Auto-recovery extraction failed: {ex}")

        if not submission.extracted_text or not submission.extracted_text.strip():
            raise HTTPException(422, "Submission has no extracted text. Cannot evaluate an empty document.")

    assessment = submission.assessment
    subject = assessment.subject if assessment else None
    if not subject:
        raise HTTPException(422, "Could not determine subject for this submission")

    # Get rubric
    rubric = db.query(MarkingRubric).filter(MarkingRubric.assessment_id == assessment.id).first()
    rubric_criteria = []
    using_default_rubric = False
    if rubric and rubric.criteria:
        rubric_criteria = [
            {"name": c.name, "max_marks": c.max_marks, "description": c.description or ""}
            for c in sorted(rubric.criteria, key=lambda x: x.order_index)
        ]
    else:
        rubric_criteria = RubricScorer.build_default_rubric(assessment.max_marks)
        using_default_rubric = True

    # Course profile
    course_profile = db.query(CourseProfile).filter(CourseProfile.subject_id == subject.id).first()
    learning_objectives = None

    # RAG retrieval
    query = f"{assessment.title} {assessment.description or ''} {submission.extracted_text[:200]}"
    rag_results = retrieve_for_subject(subject.id, query, top_k=6, faiss_dir=cfg.faiss_dir)
    course_references = [r["text"] for r in rag_results]

    # Build evaluation input
    numbered_submission = "\n".join(
        f"{line_number}: {line}"
        for line_number, line in enumerate(submission.extracted_text.splitlines(), start=1)
    )
    eval_input = EvaluationInput(
        subject_name=subject.name,
        assessment_title=assessment.title,
        assessment_type=assessment.assessment_type or "assignment",
        assessment_description=assessment.description,
        max_marks=assessment.max_marks,
        student_submission=numbered_submission,
        course_references=course_references,
        learning_objectives=learning_objectives,
        rubric_criteria=rubric_criteria,
        student_name=submission.student.user.full_name if submission.student and submission.student.user else None,
    )

    # Call OpenAI
    try:
        ai_result, tokens_used, duration = evaluate_submission(eval_input)
    except ValueError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        err_msg = str(e)
        logger.error(f"OpenAI evaluation failed: {err_msg}")
        if "credit_balance_exhausted" in err_msg or "insufficient_quota" in err_msg:
            raise HTTPException(503, "AI evaluation service is temporarily unavailable.")
        elif "invalid_api_key" in err_msg or "Incorrect API key" in err_msg:
            raise HTTPException(503, "AI evaluation service is not configured correctly.")
        else:
            raise HTTPException(503, "AI evaluation failed. Please retry.")

    # Validate with rubric scorer
    scorer = RubricScorer(assessment.max_marks, rubric_criteria)
    ai_scores_dict = {cs.criterion_name: cs.score for cs in ai_result.criterion_scores}
    criterion_results, validated_total, scoring_warnings = scorer.validate_and_score(ai_scores_dict)
    if not ai_result.subject_relevant:
        validated_total = 0.0
        scoring_warnings.append("Submission was classified as unrelated to this subject; score set to 0.")

    if scoring_warnings:
        logger.warning(f"Rubric scoring warnings for submission {submission_id}: {scoring_warnings}")

    # Save evaluation
    evaluation = AIEvaluation(
        submission_id=submission_id,
        evaluated_by_id=user.id,
        ai_total_score=validated_total,
        ai_strengths="\n".join(ai_result.strengths),
        ai_weaknesses="\n".join(ai_result.weaknesses),
        ai_missing_concepts="\n".join(ai_result.missing_concepts),
        ai_improvement_suggestions="\n".join(ai_result.improvement_suggestions),
        ai_overall_feedback=ai_result.overall_feedback,
        ai_feedback=(
            f"Subject relevance: {'Related' if ai_result.subject_relevant else 'Unrelated'}.\n"
            f"{ai_result.relevance_explanation}\n\n"
            f"{ai_result.conceptual_understanding_summary}"
        ),
        ai_raw_response=json.dumps(ai_result.model_dump()),
        openai_model_used=cfg.openai_model,
        tokens_used=tokens_used,
        evaluation_duration_seconds=duration,
        status=EvaluationStatus.completed,
    )
    db.add(evaluation)
    db.flush()

    # Save criterion scores
    for cr in criterion_results:
        cs = CriterionScore(
            evaluation_id=evaluation.id,
            criterion_name=cr.name,
            max_marks=cr.max_marks,
            ai_score=cr.clamped_score,
            justification=cr.justification,
        )
        db.add(cs)

    # Save supporting evidence
    for ev in ai_result.supporting_evidence[:10]:
        se = SupportingEvidence(
            evaluation_id=evaluation.id,
            evidence_text=ev.text,
            source=ev.source,
            relevance_note=ev.note,
        )
        db.add(se)

    submission.status = SubmissionStatus.evaluated
    _log(db, user.id, "trigger_ai_evaluation", "submission", submission_id,
         f"Score: {validated_total}/{assessment.max_marks}, tokens: {tokens_used}")
    db.commit()
    db.refresh(evaluation)

    return {
        "message": "AI evaluation completed",
        "evaluation_id": evaluation.id,
        "ai_total_score": validated_total,
        "subject_relevant": ai_result.subject_relevant,
        "relevance_explanation": ai_result.relevance_explanation,
        "max_marks": assessment.max_marks,
        "using_default_rubric": using_default_rubric,
        "rag_references_used": len(course_references),
        "scoring_warnings": scoring_warnings,
        "duration_seconds": round(duration, 2),
    }


@router.get("/submissions/{submission_id}/evaluation", response_model=EvaluationOut)
def get_evaluation(submission_id: int, db: Session = Depends(get_db), user=Depends(require_faculty)):
    evaluation = db.query(AIEvaluation).filter(AIEvaluation.submission_id == submission_id).first()
    if not evaluation:
        raise HTTPException(404, "No evaluation found for this submission")
    result = EvaluationOut.model_validate(evaluation).model_dump()
    try:
        raw = json.loads(evaluation.ai_raw_response or "{}")
        for key in (
            "subject_relevant", "relevance_explanation", "style_feedback",
            "language_errors", "line_feedback", "comparative_analysis_feedback",
            "compared_elements",
        ):
            if key in raw:
                result[key] = raw[key]
    except (TypeError, json.JSONDecodeError):
        logger.warning("Stored evaluation details are not valid structured JSON: %s", evaluation.id)
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

    assessment = evaluation.submission.assessment
    if data.faculty_total_score < 0 or data.faculty_total_score > assessment.max_marks:
        raise HTTPException(400, f"Final score must be between 0 and {assessment.max_marks}.")

    # Update faculty overrides
    evaluation.faculty_total_score = data.faculty_total_score
    evaluation.faculty_feedback = data.faculty_feedback
    evaluation.faculty_notes = data.faculty_notes
    evaluation.status = EvaluationStatus.approved

    # Apply criterion overrides if provided
    if data.criterion_overrides:
        for override in data.criterion_overrides:
            cs = db.query(CriterionScore).filter(CriterionScore.id == override.criterion_score_id).first()
            if cs and cs.evaluation_id == evaluation_id:
                score = override.faculty_score
                if score > cs.max_marks:
                    raise HTTPException(400, f"Score for '{cs.criterion_name}' must be between 0 and {cs.max_marks}.")
                cs.faculty_score = score

    # Create approved feedback record
    existing_af = db.query(ApprovedFeedback).filter(ApprovedFeedback.evaluation_id == evaluation_id).first()
    if existing_af:
        existing_af.final_score = data.faculty_total_score
        existing_af.final_feedback = data.faculty_feedback or evaluation.ai_feedback or evaluation.ai_overall_feedback or ""
        # Once published, keep student visibility while faculty edits the result.
        existing_af.is_published = data.publish_to_student or existing_af.is_published
        existing_af.approved_by_id = user.id
        af = existing_af
    else:
        af = ApprovedFeedback(
            evaluation_id=evaluation_id,
            final_score=data.faculty_total_score,
            final_feedback=data.faculty_feedback or evaluation.ai_feedback or evaluation.ai_overall_feedback or "",
            is_published=data.publish_to_student,
            approved_by_id=user.id,
        )
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
    evaluation.status = EvaluationStatus.rejected
    evaluation.submission.status = SubmissionStatus.rejected
    _log(db, user.id, "reject_evaluation", "evaluation", evaluation_id)
    db.commit()
    return {"message": "Evaluation rejected"}


# ─── Students in Subject ──────────────────────────────────────────────────────

@router.get("/subjects/{subject_id}/students")
def list_enrolled_students(subject_id: int, db: Session = Depends(get_db), user=Depends(require_faculty)):
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
