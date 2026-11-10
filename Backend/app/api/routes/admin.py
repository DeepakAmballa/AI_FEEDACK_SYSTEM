"""Admin routes — user management, stats, audit logs."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin
from app.core.security import get_password_hash
from app.models.models import (
    User, FacultyProfile, StudentProfile, Subject,
    StudentSubmission, AIEvaluation, AuditLog, UserRole,
    SubjectFaculty, SubjectEnrollment
)
from app.schemas.schemas import (
    UserOut, UserUpdate, FacultyCreateFull, StudentCreateFull,
    SubjectCreate, SubjectOut, SubjectUpdate,
    AdminStatsOut, AuditLogOut
)

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
            "subject": s.assessment.subject.name if s.assessment and s.assessment.subject else "Unknown",
            "status": s.status.value,
            "submitted_at": s.submitted_at.isoformat(),
        })
    return result

