"""Pydantic schemas for request/response validation."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator
from app.models.models import UserRole, SubmissionStatus, EvaluationStatus


# ─── Token ────────────────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str
    user_id: int


class TokenData(BaseModel):
    user_id: Optional[int] = None
    role: Optional[str] = None


# ─── User ─────────────────────────────────────────────────────────────────────

class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole


class UserCreate(UserBase):
    password: str = Field(min_length=6)


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class UserOut(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Faculty Profile ──────────────────────────────────────────────────────────

class FacultyProfileCreate(BaseModel):
    department: Optional[str] = None
    employee_id: Optional[str] = None
    specialization: Optional[str] = None


class FacultyProfileOut(FacultyProfileCreate):
    id: int
    user_id: int

    model_config = {"from_attributes": True}


class FacultyCreateFull(UserCreate):
    department: Optional[str] = None
    employee_id: Optional[str] = None
    specialization: Optional[str] = None


# ─── Student Profile ──────────────────────────────────────────────────────────

class StudentProfileCreate(BaseModel):
    student_id: str
    program: Optional[str] = None
    year_of_study: Optional[int] = None


class StudentProfileOut(StudentProfileCreate):
    id: int
    user_id: int

    model_config = {"from_attributes": True}


class StudentCreateFull(UserCreate):
    student_id: str
    program: Optional[str] = None
    year_of_study: Optional[int] = None


# ─── Subject ──────────────────────────────────────────────────────────────────

class SubjectCreate(BaseModel):
    name: str
    code: str
    description: Optional[str] = None


class SubjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class SubjectOut(BaseModel):
    id: int
    name: str
    code: str
    description: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CourseDocumentOut(BaseModel):
    id: int
    course_profile_id: int
    original_filename: str
    file_type: str
    doc_type: Optional[str]
    page_count: Optional[int]
    is_indexed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Assessment ───────────────────────────────────────────────────────────────

class AssessmentCreate(BaseModel):
    subject_id: int
    title: str
    description: Optional[str] = None
    assessment_type: Optional[str] = "assignment"
    max_marks: float = 20.0
    due_date: Optional[datetime] = None


class AssessmentOut(BaseModel):
    id: int
    subject_id: int
    title: str
    description: Optional[str]
    assessment_type: Optional[str]
    max_marks: float
    due_date: Optional[datetime]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Rubric ───────────────────────────────────────────────────────────────────

class RubricCriterionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    max_marks: float
    weight: float = 1.0
    order_index: int = 0


class RubricCreate(BaseModel):
    description: Optional[str] = None
    total_marks: float
    criteria: List[RubricCriterionCreate]

    @field_validator("criteria")
    @classmethod
    def validate_criteria_sum(cls, criteria, info):
        total = sum(c.max_marks for c in criteria)
        # Allow small floating point differences
        return criteria


class RubricCriterionOut(RubricCriterionCreate):
    id: int
    rubric_id: int

    model_config = {"from_attributes": True}


class RubricOut(BaseModel):
    id: int
    assessment_id: int
    description: Optional[str]
    total_marks: float
    criteria: List[RubricCriterionOut]
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Student Submissions ──────────────────────────────────────────────────────

class SubmissionOut(BaseModel):
    id: int
    assessment_id: int
    filename: str
    original_filename: str
    file_type: str
    file_size: Optional[int]
    extraction_status: str
    status: SubmissionStatus
    submitted_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SubmissionDetailOut(SubmissionOut):
    extracted_text: Optional[str]

    model_config = {"from_attributes": True}


# ─── AI Evaluation ────────────────────────────────────────────────────────────

class CriterionScoreOut(BaseModel):
    id: int
    criterion_name: str
    max_marks: float
    ai_score: float
    faculty_score: Optional[float]
    justification: Optional[str]

    model_config = {"from_attributes": True}


class CriterionScoreOverride(BaseModel):
    criterion_score_id: int
    faculty_score: float = Field(ge=0)


class SupportingEvidenceOut(BaseModel):
    id: int
    evidence_text: str
    source: Optional[str]
    relevance_note: Optional[str]

    model_config = {"from_attributes": True}


class EvaluationOut(BaseModel):
    id: int
    submission_id: int
    ai_total_score: Optional[float]
    ai_feedback: Optional[str]
    ai_strengths: Optional[str]
    ai_weaknesses: Optional[str]
    ai_missing_concepts: Optional[str]
    ai_improvement_suggestions: Optional[str]
    ai_overall_feedback: Optional[str]
    faculty_total_score: Optional[float]
    faculty_feedback: Optional[str]
    faculty_notes: Optional[str]
    status: EvaluationStatus
    created_at: datetime
    updated_at: datetime
    criterion_scores: List[CriterionScoreOut] = []
    supporting_evidence: List[SupportingEvidenceOut] = []

    model_config = {"from_attributes": True}


class EvaluationApproveRequest(BaseModel):
    faculty_total_score: float = Field(ge=0)
    faculty_feedback: Optional[str] = None
    faculty_notes: Optional[str] = None
    criterion_overrides: Optional[List[CriterionScoreOverride]] = None
    publish_to_student: bool = False


class ApprovedFeedbackOut(BaseModel):
    id: int
    evaluation_id: int
    final_score: float
    final_feedback: str
    is_published: bool
    approved_at: datetime

    model_config = {"from_attributes": True}


# ─── Dashboard Stats ──────────────────────────────────────────────────────────

class AdminStatsOut(BaseModel):
    total_students: int
    total_faculty: int
    total_subjects: int
    total_submissions: int
    total_evaluations: int
    pending_evaluations: int
    approved_evaluations: int


class AuditLogOut(BaseModel):
    id: int
    user_id: Optional[int]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[int]
    details: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
