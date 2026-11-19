"""Admin routes — user management, assessment & rubric management, AI evaluation monitoring, stats, audit logs."""
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin
from app.core.security import get_password_hash
from app.models.models import (
    User, FacultyProfile, StudentProfile, Subject,
    StudentSubmission, AIEvaluation, AuditLog, UserRole,
    SubjectFaculty, SubjectEnrollment, Assessment,
    AssessmentType, RubricVersion, FacultyEvaluation,
    FinalEvaluation, CriterionScore, ApprovedFeedback,
    SubmissionStatus, EvaluationStatus
)
from app.schemas.schemas import (
    UserOut, UserUpdate, FacultyCreateFull, StudentCreateFull,
    SubjectCreate, SubjectOut, SubjectUpdate,
    AdminStatsOut, AuditLogOut,
    AssessmentTypeCreate, AssessmentTypeUpdate, AssessmentTypeOut,
    RubricVersionCreate, RubricVersionOut,
    AdminEvaluationListItem, AdminComparisonDetail
)
from app.services.ai.evaluator import execute_ai_evaluation_job
from app.services.assessments import submission_subject

router = APIRouter(prefix="/api/admin", tags=["Admin"])


def _log_action(db: Session, user_id: int, action: str, resource_type: str = None, resource_id: int = None, details: str = None):
    log = AuditLog(user_id=user_id, action=action, resource_type=resource_type, resource_id=resource_id, details=details)
    db.add(log)


# ─── Dashboard Stats ──────────────────────────────────────────────────────────

@router.get("/stats", response_model=AdminStatsOut)
def get_stats(db: Session = Depends(get_db), admin=Depends(require_admin)):
    return AdminStatsOut(
        total_students=db.query(StudentProfile).count(),
        total_faculty=db.query(FacultyProfile).count(),
        total_subjects=db.query(Subject).count(),
        total_submissions=db.query(StudentSubmission).count(),
        total_evaluations=db.query(AIEvaluation).count(),
        pending_evaluations=db.query(AIEvaluation).filter(AIEvaluation.status == "pending").count(),
        approved_evaluations=db.query(AIEvaluation).filter(AIEvaluation.status == "approved").count(),
    )


# ─── Faculty Management ───────────────────────────────────────────────────────

@router.get("/faculty", response_model=List[UserOut])
def list_faculty(db: Session = Depends(get_db), admin=Depends(require_admin)):
    return db.query(User).filter(User.role == UserRole.faculty).all()


@router.post("/faculty", response_model=UserOut)
def create_faculty(data: FacultyCreateFull, db: Session = Depends(get_db), admin=Depends(require_admin)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(400, "Email already registered")
    user = User(
        email=data.email,
        full_name=data.full_name,
        hashed_password=get_password_hash(data.password),
        role=UserRole.faculty,
    )
    db.add(user)
    db.flush()
    profile = FacultyProfile(
        user_id=user.id,
        department=data.department,
        employee_id=data.employee_id,
        specialization=data.specialization,
    )
    db.add(profile)
    _log_action(db, admin.id, "create_faculty", "user", user.id, f"Created faculty: {user.email}")
    db.commit()
    db.refresh(user)
    return user


@router.put("/faculty/{user_id}", response_model=UserOut)
def update_faculty(user_id: int, data: UserUpdate, db: Session = Depends(get_db), admin=Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id, User.role == UserRole.faculty).first()
    if not user:
        raise HTTPException(404, "Faculty not found")
    if data.full_name:
        user.full_name = data.full_name
    if data.email:
        user.email = data.email
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.password:
        user.hashed_password = get_password_hash(data.password)
    _log_action(db, admin.id, "update_faculty", "user", user_id)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/faculty/{user_id}")
def delete_faculty(user_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id, User.role == UserRole.faculty).first()
    if not user:
        raise HTTPException(404, "Faculty not found")
    user.is_active = False
    _log_action(db, admin.id, "deactivate_faculty", "user", user_id)
    db.commit()
    return {"message": "Faculty deactivated"}


# ─── Student Management ───────────────────────────────────────────────────────

@router.get("/students", response_model=List[UserOut])
def list_students(db: Session = Depends(get_db), admin=Depends(require_admin)):
    return db.query(User).filter(User.role == UserRole.student).all()


@router.post("/students", response_model=UserOut)
def create_student(data: StudentCreateFull, db: Session = Depends(get_db), admin=Depends(require_admin)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(400, "Email already registered")
    if db.query(StudentProfile).filter(StudentProfile.student_id == data.student_id).first():
        raise HTTPException(400, "Student ID already exists")
    user = User(
        email=data.email,
        full_name=data.full_name,
        hashed_password=get_password_hash(data.password),
        role=UserRole.student,
    )
    db.add(user)
    db.flush()
    profile = StudentProfile(
        user_id=user.id,
        student_id=data.student_id,
        program=data.program,
        year_of_study=data.year_of_study,
    )
    db.add(profile)
    _log_action(db, admin.id, "create_student", "user", user.id, f"Student ID: {data.student_id}")
    db.commit()
    db.refresh(user)
    return user


@router.put("/students/{user_id}", response_model=UserOut)
def update_student(user_id: int, data: UserUpdate, db: Session = Depends(get_db), admin=Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id, User.role == UserRole.student).first()
    if not user:
        raise HTTPException(404, "Student not found")
    if data.full_name:
        user.full_name = data.full_name
    if data.email:
        user.email = data.email
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.password:
        user.hashed_password = get_password_hash(data.password)
    db.commit()
    db.refresh(user)
    return user


# ─── Subject Management ───────────────────────────────────────────────────────

@router.get("/subjects", response_model=List[SubjectOut])
def list_subjects(db: Session = Depends(get_db), admin=Depends(require_admin)):
    return db.query(Subject).all()


@router.post("/subjects", response_model=SubjectOut)
def create_subject(data: SubjectCreate, db: Session = Depends(get_db), admin=Depends(require_admin)):
    if db.query(Subject).filter(Subject.code == data.code).first():
        raise HTTPException(400, f"Subject code '{data.code}' already exists")
    subject = Subject(**data.model_dump())
    db.add(subject)
    _log_action(db, admin.id, "create_subject", "subject", None, f"Code: {data.code}")
    db.commit()
    db.refresh(subject)
    return subject


@router.put("/subjects/{subject_id}", response_model=SubjectOut)
def update_subject(subject_id: int, data: SubjectUpdate, db: Session = Depends(get_db), admin=Depends(require_admin)):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(404, "Subject not found")
    for field, val in data.model_dump(exclude_none=True).items():
        setattr(subject, field, val)
    db.commit()
    db.refresh(subject)
    return subject


@router.post("/subjects/{subject_id}/assign-faculty/{faculty_user_id}")
def assign_faculty_to_subject(subject_id: int, faculty_user_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(404, "Subject not found")
    faculty = db.query(FacultyProfile).filter(FacultyProfile.user_id == faculty_user_id).first()
    if not faculty:
        raise HTTPException(404, "Faculty not found")
    existing = db.query(SubjectFaculty).filter(
        SubjectFaculty.subject_id == subject_id,
        SubjectFaculty.faculty_id == faculty.id
    ).first()
    if existing:
        raise HTTPException(400, "Faculty already assigned to this subject")
    assignment = SubjectFaculty(subject_id=subject_id, faculty_id=faculty.id)
    db.add(assignment)
    db.commit()
    return {"message": "Faculty assigned successfully"}


@router.post("/subjects/{subject_id}/enroll-student/{student_user_id}")
def enroll_student(subject_id: int, student_user_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(404, "Subject not found")
    student = db.query(StudentProfile).filter(StudentProfile.user_id == student_user_id).first()
    if not student:
        raise HTTPException(404, "Student not found")
    existing = db.query(SubjectEnrollment).filter(
        SubjectEnrollment.subject_id == subject_id,
        SubjectEnrollment.student_id == student.id
    ).first()
    if existing:
        raise HTTPException(400, "Student already enrolled")
    enrollment = SubjectEnrollment(subject_id=subject_id, student_id=student.id)
    db.add(enrollment)
    db.commit()
    return {"message": "Student enrolled successfully"}


# ─── Audit Logs ───────────────────────────────────────────────────────────────

@router.get("/audit-logs", response_model=List[AuditLogOut])
def get_audit_logs(
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db),
    admin=Depends(require_admin)
):
    return db.query(AuditLog).order_by(AuditLog.created_at.desc()).offset(skip).limit(limit).all()


# ─── Submissions Overview ─────────────────────────────────────────────────────

@router.get("/submissions")
def all_submissions(db: Session = Depends(get_db), admin=Depends(require_admin)):
    submissions = db.query(StudentSubmission).order_by(StudentSubmission.submitted_at.desc()).limit(200).all()
    result = []
    for s in submissions:
        result.append({
            "id": s.id,
            "student_name": s.student.user.full_name if s.student and s.student.user else "Unknown",
            "student_id": s.student.student_id if s.student else None,
            "assessment_title": s.assessment.title if s.assessment else "Unknown",
            "subject": (submission_subject(db, s).name if s.assessment and submission_subject(db, s) else "Unknown"),
            "status": s.status.value,
            "submitted_at": s.submitted_at.isoformat(),
        })
    return result


# ─── Assessment Type & Rubric Management (Admin) ──────────────────────────────

@router.get("/assessment-types", response_model=List[AssessmentTypeOut])
def list_assessment_types(db: Session = Depends(get_db), admin=Depends(require_admin)):
    """List all assessment types including their active rubric version and all historical versions."""
    types = db.query(AssessmentType).order_by(AssessmentType.id.asc()).all()
    result = []
    for atype in types:
        versions = db.query(RubricVersion).filter(
            RubricVersion.assessment_type_id == atype.id
        ).order_by(RubricVersion.version.desc()).all()

        active_rv = next((v for v in versions if v.is_active), versions[0] if versions else None)

        out_versions = [
            RubricVersionOut(
                id=v.id,
                assessment_type_id=v.assessment_type_id,
                version=v.version,
                total_marks=v.total_marks,
                is_active=v.is_active,
                criteria_data=v.criteria_data,
                created_at=v.created_at,
            )
            for v in versions
        ]
        out_active = (
            RubricVersionOut(
                id=active_rv.id,
                assessment_type_id=active_rv.assessment_type_id,
                version=active_rv.version,
                total_marks=active_rv.total_marks,
                is_active=active_rv.is_active,
                criteria_data=active_rv.criteria_data,
                created_at=active_rv.created_at,
            )
            if active_rv
            else None
        )

        result.append(
            AssessmentTypeOut(
                id=atype.id,
                name=atype.name,
                description=atype.description,
                is_active=atype.is_active,
                max_marks=atype.max_marks,
                default_discrepancy_threshold=atype.default_discrepancy_threshold,
                created_at=atype.created_at,
                updated_at=atype.updated_at,
                active_rubric=out_active,
                active_rubric_version=out_active,
                rubric_versions=out_versions,
            )
        )
    return result


@router.post("/assessment-types", response_model=AssessmentTypeOut)
def create_assessment_type(
    data: AssessmentTypeCreate,
    db: Session = Depends(get_db),
    admin=Depends(require_admin)
):
    """Create a new dynamic assessment type with initial 5 criteria and performance levels."""
    existing = db.query(AssessmentType).filter(AssessmentType.name == data.name.strip()).first()
    if existing:
        raise HTTPException(400, f"Assessment type '{data.name}' already exists.")

    criteria_dict_list = [c.model_dump() for c in data.criteria]

    atype = AssessmentType(
        name=data.name.strip(),
        description=data.description,
        max_marks=data.max_marks,
        default_discrepancy_threshold=data.default_discrepancy_threshold,
        is_active=True,
    )
    db.add(atype)
    db.flush()

    rubric_v1 = RubricVersion(
        assessment_type_id=atype.id,
        version=1,
        total_marks=data.max_marks,
        is_active=True,
        criteria_data=criteria_dict_list,
    )
    db.add(rubric_v1)
    _log_action(db, admin.id, "create_assessment_type", "assessment_type", atype.id, f"Created {atype.name}")
    db.commit()
    db.refresh(atype)
    db.refresh(rubric_v1)

    rv_out = RubricVersionOut(
        id=rubric_v1.id,
        assessment_type_id=rubric_v1.assessment_type_id,
        version=rubric_v1.version,
        total_marks=rubric_v1.total_marks,
        is_active=rubric_v1.is_active,
        criteria_data=rubric_v1.criteria_data,
        created_at=rubric_v1.created_at,
    )
    return AssessmentTypeOut(
        id=atype.id,
        name=atype.name,
        description=atype.description,
        is_active=atype.is_active,
        max_marks=atype.max_marks,
        default_discrepancy_threshold=atype.default_discrepancy_threshold,
        created_at=atype.created_at,
        updated_at=atype.updated_at,
        active_rubric=rv_out,
        active_rubric_version=rv_out,
        rubric_versions=[rv_out],
    )


@router.put("/assessment-types/{type_id}", response_model=AssessmentTypeOut)
def update_assessment_type(
    type_id: int,
    data: AssessmentTypeUpdate,
    db: Session = Depends(get_db),
    admin=Depends(require_admin)
):
    """Edit assessment details, activate/deactivate, and configure discrepancy threshold."""
    atype = db.query(AssessmentType).filter(AssessmentType.id == type_id).first()
    if not atype:
        raise HTTPException(404, "Assessment type not found")

    for field, val in data.model_dump(exclude_none=True).items():
        setattr(atype, field, val)

    _log_action(db, admin.id, "update_assessment_type", "assessment_type", type_id, f"Updated {atype.name}")
    db.commit()
    db.refresh(atype)

    versions = db.query(RubricVersion).filter(RubricVersion.assessment_type_id == atype.id).order_by(RubricVersion.version.desc()).all()
    active_rv = next((v for v in versions if v.is_active), versions[0] if versions else None)
    out_versions = [
        RubricVersionOut(
            id=v.id,
            assessment_type_id=v.assessment_type_id,
            version=v.version,
            total_marks=v.total_marks,
            is_active=v.is_active,
            criteria_data=v.criteria_data,
            created_at=v.created_at,
        )
        for v in versions
    ]
    out_active = (
        RubricVersionOut(
            id=active_rv.id,
            assessment_type_id=active_rv.assessment_type_id,
            version=active_rv.version,
            total_marks=active_rv.total_marks,
            is_active=active_rv.is_active,
            criteria_data=active_rv.criteria_data,
            created_at=active_rv.created_at,
        )
        if active_rv
        else None
    )

    return AssessmentTypeOut(
        id=atype.id,
        name=atype.name,
        description=atype.description,
        is_active=atype.is_active,
        max_marks=atype.max_marks,
        default_discrepancy_threshold=atype.default_discrepancy_threshold,
        created_at=atype.created_at,
        updated_at=atype.updated_at,
        active_rubric=out_active,
        active_rubric_version=out_active,
        rubric_versions=out_versions,
    )


@router.post("/assessment-types/{type_id}/rubric-versions", response_model=RubricVersionOut)
def create_rubric_version(
    type_id: int,
    data: RubricVersionCreate,
    db: Session = Depends(get_db),
    admin=Depends(require_admin)
):
    """Create a new rubric version for an assessment type, preserving historical versions."""
    atype = db.query(AssessmentType).filter(AssessmentType.id == type_id).first()
    if not atype:
        raise HTTPException(404, "Assessment type not found")

    existing_versions = db.query(RubricVersion).filter(RubricVersion.assessment_type_id == type_id).all()
    new_version_num = max([v.version for v in existing_versions], default=0) + 1

    # Deactivate previous versions
    for v in existing_versions:
        v.is_active = False

    criteria_dict_list = [c.model_dump() for c in data.criteria]
    new_rv = RubricVersion(
        assessment_type_id=type_id,
        version=new_version_num,
        total_marks=data.total_marks,
        is_active=True,
        criteria_data=criteria_dict_list,
    )
    db.add(new_rv)
    _log_action(db, admin.id, "create_rubric_version", "rubric_version", None, f"Created v{new_version_num} for {atype.name}")
    db.commit()
    db.refresh(new_rv)

    return RubricVersionOut(
        id=new_rv.id,
        assessment_type_id=new_rv.assessment_type_id,
        version=new_rv.version,
        total_marks=new_rv.total_marks,
        is_active=new_rv.is_active,
        criteria_data=new_rv.criteria_data,
        created_at=new_rv.created_at,
    )


# ─── Evaluation Monitoring & AI Comparison (Admin-Only) ───────────────────────

@router.get("/evaluation-monitoring", response_model=List[AdminEvaluationListItem])
def list_evaluations_monitoring(
    subject_id: Optional[int] = Query(None),
    faculty_id: Optional[int] = Query(None),
    student_id: Optional[int] = Query(None),
    assessment_id: Optional[int] = Query(None),
    assessment_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    admin=Depends(require_admin)
):
    """Admin-only comprehensive evaluation monitor across faculty and AI workflows."""
    query = db.query(StudentSubmission).join(Assessment).order_by(StudentSubmission.submitted_at.desc())

    if subject_id:
        query = query.filter(Assessment.subject_id == subject_id)
    if assessment_id:
        query = query.filter(StudentSubmission.assessment_id == assessment_id)
    if student_id:
        query = query.filter(StudentSubmission.student_id == student_id)
    if assessment_type:
        query = query.filter(Assessment.assessment_type.ilike(f"%{assessment_type}%"))

    submissions = query.all()
    results = []

    for sub in submissions:
        assess = sub.assessment
        stud = sub.student
        subj = submission_subject(db, sub) if assess else None

        # Find faculty name
        faculty_name = "Assigned Faculty"
        if subj:
            sf = db.query(SubjectFaculty).filter(SubjectFaculty.subject_id == subj.id).first()
            if sf and sf.faculty and sf.faculty.user:
                faculty_name = sf.faculty.user.full_name

        faculty_eval = db.query(FacultyEvaluation).filter(FacultyEvaluation.submission_id == sub.id).first()
        ai_eval = db.query(AIEvaluation).filter(AIEvaluation.submission_id == sub.id).first()
        final_eval = db.query(FinalEvaluation).filter(FinalEvaluation.submission_id == sub.id).first()

        faculty_status = "Not Evaluated"
        faculty_marks = None
        if faculty_eval:
            faculty_status = "Draft" if faculty_eval.is_draft else "Completed"
            faculty_marks = faculty_eval.faculty_total_marks

        ai_status = "Not Started"
        ai_marks = None
        error_details = None
        if ai_eval:
            ai_status = ai_eval.ai_status.capitalize() if ai_eval.ai_status else "Completed"
            ai_marks = ai_eval.ai_total_score
            error_details = ai_eval.error_details

        discrepancy_val = final_eval.discrepancy_value if final_eval else None
        threshold_val = final_eval.discrepancy_threshold if final_eval else (assess.discrepancy_threshold * assess.max_marks if assess else 4.0)
        calc_method = final_eval.calculation_method if final_eval else None
        final_marks = final_eval.final_total_marks if final_eval else None
        is_published = final_eval.is_published if final_eval else False

        # Status filter check
        if status:
            if status == "faculty_pending" and faculty_status != "Not Evaluated":
                continue
            if status == "ai_failed" and ai_status != "Failed":
                continue
            if status == "completed" and (faculty_status != "Completed" or ai_status != "Completed"):
                continue

        results.append(
            AdminEvaluationListItem(
                submission_id=sub.id,
                student_name=stud.user.full_name if stud and stud.user else "Unknown",
                student_id_str=stud.student_id if stud else "",
                subject_name=subj.name if subj else "Unknown",
                faculty_name=faculty_name,
                assessment_title=assess.title if assess else "Unknown",
                assessment_type=assess.assessment_type or "Standard",
                submission_date=sub.submitted_at,
                submission_type=sub.submission_type or "upload",
                faculty_status=faculty_status,
                faculty_marks=faculty_marks,
                ai_status=ai_status,
                ai_marks=ai_marks,
                discrepancy_value=discrepancy_val,
                discrepancy_threshold=threshold_val,
                calculation_method=calc_method,
                final_marks=final_marks,
                max_marks=assess.max_marks if assess else 20.0,
                is_published=is_published,
                error_details=error_details,
            )
        )

    return results


@router.get("/evaluation-monitoring/{submission_id}", response_model=AdminComparisonDetail)
@router.get("/evaluation-monitoring/{submission_id}/comparison", response_model=AdminComparisonDetail)
def get_evaluation_comparison_detail(
    submission_id: int,
    db: Session = Depends(get_db),
    admin=Depends(require_admin)
):
    """Admin-only side-by-side comparison between faculty marks and AI marks with discrepancy breakdown."""
    sub = db.query(StudentSubmission).filter(StudentSubmission.id == submission_id).first()
    if not sub:
        raise HTTPException(404, "Submission not found")

    assess = sub.assessment
    stud = sub.student
    subj = submission_subject(db, sub) if assess else None

    faculty_name = "Faculty"
    if subj:
        sf = db.query(SubjectFaculty).filter(SubjectFaculty.subject_id == subj.id).first()
        if sf and sf.faculty and sf.faculty.user:
            faculty_name = sf.faculty.user.full_name

    faculty_eval = db.query(FacultyEvaluation).filter(FacultyEvaluation.submission_id == sub.id).first()
    ai_eval = db.query(AIEvaluation).filter(AIEvaluation.submission_id == sub.id).first()
    final_eval = db.query(FinalEvaluation).filter(FinalEvaluation.submission_id == sub.id).first()

    # Rubric info
    rv = None
    if assess.rubric_version_id:
        rv = db.query(RubricVersion).filter(RubricVersion.id == assess.rubric_version_id).first()

    # Parse AI criterion scores
    ai_criterion_scores = []
    if ai_eval:
        if ai_eval.ai_criterion_scores_json:
            ai_criterion_scores = ai_eval.ai_criterion_scores_json
        elif ai_eval.criterion_scores:
            ai_criterion_scores = [
                {
                    "criterion_name": cs.criterion_name,
                    "max_marks": cs.max_marks,
                    "score": cs.ai_score,
                    "justification": cs.justification,
                }
                for cs in ai_eval.criterion_scores
            ]

    # Parse AI evidence
    ai_evidence = []
    if ai_eval and ai_eval.supporting_evidence:
        ai_evidence = [
            {"text": se.evidence_text, "source": se.source, "note": se.relevance_note}
            for se in ai_eval.supporting_evidence
        ]

    return AdminComparisonDetail(
        submission_id=sub.id,
        student_name=stud.user.full_name if stud and stud.user else "Unknown",
        student_id_str=stud.student_id if stud else "",
        subject_name=subj.name if subj else "Unknown",
        faculty_name=faculty_name,
        assessment_title=assess.title if assess else "Unknown",
        assessment_type=assess.assessment_type or "Standard",
        assessment_description=assess.description,
        instructions=assess.instructions,
        max_marks=assess.max_marks if assess else 20.0,
        submission_date=sub.submitted_at,
        submission_text=sub.extracted_text or sub.typed_content,
        original_filename=sub.original_filename,
        submission_type=sub.submission_type or "upload",
        rubric_version_id=rv.id if rv else None,
        rubric_version_num=rv.version if rv else None,
        rubric_criteria=rv.criteria_data if rv else None,
        # Faculty
        faculty_status="Draft" if (faculty_eval and faculty_eval.is_draft) else ("Completed" if faculty_eval else "Not Evaluated"),
        faculty_marks=faculty_eval.faculty_total_marks if faculty_eval else None,
        faculty_feedback=faculty_eval.overall_feedback if faculty_eval else None,
        faculty_strengths=faculty_eval.strengths if faculty_eval else None,
        faculty_weaknesses=faculty_eval.weaknesses if faculty_eval else None,
        faculty_suggestions=faculty_eval.improvement_suggestions if faculty_eval else None,
        faculty_irrelevant=faculty_eval.irrelevant_observations if faculty_eval else None,
        faculty_deductions=faculty_eval.deduction_reasons if faculty_eval else None,
        faculty_notes=faculty_eval.internal_notes if faculty_eval else None,
        faculty_evaluated_at=faculty_eval.updated_at if faculty_eval else None,
        # AI
        ai_status=ai_eval.ai_status.capitalize() if (ai_eval and ai_eval.ai_status) else "Not Started",
        ai_marks=ai_eval.ai_total_score if ai_eval else None,
        ai_criterion_scores=ai_criterion_scores,
        ai_overall_feedback=ai_eval.ai_overall_feedback if ai_eval else None,
        ai_strengths=ai_eval.ai_strengths if ai_eval else None,
        ai_weaknesses=ai_eval.ai_weaknesses if ai_eval else None,
        ai_suggestions=ai_eval.ai_improvement_suggestions if ai_eval else None,
        ai_evidence=ai_evidence,
        ai_irrelevant_observations=ai_eval.ai_irrelevant_observations_json if ai_eval else None,
        ai_error_details=ai_eval.error_details if ai_eval else None,
        ai_duration_seconds=ai_eval.evaluation_duration_seconds if ai_eval else None,
        ai_model_used=ai_eval.openai_model_used if ai_eval else None,
        ai_tokens_used=ai_eval.tokens_used if ai_eval else None,
        # Final Score
        discrepancy_value=final_eval.discrepancy_value if final_eval else None,
        discrepancy_threshold=final_eval.discrepancy_threshold if final_eval else (assess.discrepancy_threshold * assess.max_marks if assess else 4.0),
        calculation_method=final_eval.calculation_method if final_eval else None,
        final_marks=final_eval.final_total_marks if final_eval else None,
        is_published=final_eval.is_published if final_eval else False,
        faculty_evaluation={
            "marks": faculty_eval.faculty_total_marks,
            "feedback": faculty_eval.overall_feedback,
            "status": "Draft" if faculty_eval.is_draft else "Completed",
        } if faculty_eval else None,
        ai_evaluation={
            "marks": ai_eval.ai_total_score,
            "status": ai_eval.ai_status if ai_eval else "Not Started",
        } if ai_eval else None,
        scoring_comparison={
            "faculty_marks": faculty_eval.faculty_total_marks if faculty_eval else None,
            "ai_marks": ai_eval.ai_total_score if ai_eval else None,
            "discrepancy": final_eval.discrepancy_value if final_eval else None,
            "final_marks": final_eval.final_total_marks if final_eval else None,
        },
    )


@router.post("/evaluation-monitoring/{submission_id}/retry")
def retry_failed_ai_evaluation(
    submission_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    admin=Depends(require_admin)
):
    """Admin-only safe retry of failed AI evaluation without duplicating evaluation records."""
    sub = db.query(StudentSubmission).filter(StudentSubmission.id == submission_id).first()
    if not sub:
        raise HTTPException(404, "Submission not found")

    faculty_eval = db.query(FacultyEvaluation).filter(FacultyEvaluation.submission_id == submission_id).first()
    if not faculty_eval:
        raise HTTPException(400, "Faculty manual evaluation must be submitted before AI evaluation can be executed.")

    _log_action(db, admin.id, "retry_ai_evaluation", "submission", submission_id, "Triggered AI evaluation retry")
    db.commit()

    background_tasks.add_task(execute_ai_evaluation_job, submission_id, admin.id, True)
    return {"message": "AI evaluation retry has been scheduled in the background."}


@router.put("/evaluation-monitoring/{submission_id}/publish")
def toggle_evaluation_publication(
    submission_id: int,
    publish: bool = Query(default=True),
    db: Session = Depends(get_db),
    admin=Depends(require_admin)
):
    """Admin publish/unpublish control for final evaluations."""
    final_eval = db.query(FinalEvaluation).filter(FinalEvaluation.submission_id == submission_id).first()
    if not final_eval:
        raise HTTPException(404, "Final evaluation not found or not yet ready for publication")

    final_eval.is_published = publish
    if publish:
        final_eval.published_at = datetime.utcnow()

    # Sync legacy approved feedback
    ai_eval = db.query(AIEvaluation).filter(AIEvaluation.submission_id == submission_id).first()
    if ai_eval and ai_eval.approved_feedback:
        ai_eval.approved_feedback.is_published = publish

    _log_action(db, admin.id, "publish_evaluation" if publish else "unpublish_evaluation", "submission", submission_id)
    db.commit()
    return {"message": f"Evaluation {'published to student' if publish else 'hidden from student'} successfully."}


@router.get("/evaluation-monitoring/{submission_id}/feedback.pdf")
def admin_feedback_pdf(submission_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    """The student's annotated feedback document as a PDF (admin oversight)."""
    from fastapi.responses import Response
    from app.services.report.feedback_pdf import render_feedback_pdf

    final_eval = db.query(FinalEvaluation).filter(FinalEvaluation.submission_id == submission_id).first()
    if not final_eval or not final_eval.feedback_document:
        raise HTTPException(404, "No feedback document has been generated for this submission yet.")
    return Response(content=render_feedback_pdf(final_eval.feedback_document), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="feedback-{submission_id}.pdf"'})
