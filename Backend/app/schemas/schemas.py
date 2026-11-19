"""Pydantic schemas for request/response validation."""
from datetime import datetime
from typing import List, Optional, Any, Dict
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
    assessment_type_id: Optional[int] = None
    assessment_type: Optional[str] = "assignment"
    max_marks: float = 20.0
    due_date: Optional[datetime] = None
    instructions: Optional[str] = None
    start_date: Optional[datetime] = None
    allowed_file_types: Optional[str] = "pdf,docx,doc,pptx,ppt,txt,images"
    course_unit: Optional[str] = None
    reference_answer: Optional[str] = None


class AssessmentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    max_marks: Optional[float] = Field(default=None, gt=0)
    due_date: Optional[datetime] = None
    instructions: Optional[str] = None
    start_date: Optional[datetime] = None
    allowed_file_types: Optional[str] = None
    course_unit: Optional[str] = None
    reference_answer: Optional[str] = None
    is_active: Optional[bool] = None


class AssessmentOut(BaseModel):
    id: int
    subject_id: int
    title: str
    description: Optional[str]
    assessment_type: Optional[str]
    assessment_type_id: Optional[int] = None
    rubric_version_id: Optional[int] = None
    max_marks: float
    due_date: Optional[datetime]
    instructions: Optional[str] = None
    start_date: Optional[datetime] = None
    allowed_file_types: Optional[str] = None
    course_unit: Optional[str] = None
    reference_answer: Optional[str] = None
    is_active: bool
    created_at: datetime
    rubric_criteria: Optional[Any] = None

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


# ─── Assessment Types & Rubrics (Admin) ───────────────────────────────────────

class PerformanceLevelSchema(BaseModel):
    level: int = Field(ge=1, le=4)
    name: str  # Excellent, Good, Average, Needs Improvement
    description: str


class RubricCriterionDetailSchema(BaseModel):
    name: str
    max_marks: float = 4.0
    description: Optional[str] = None
    levels: List[PerformanceLevelSchema]


class AssessmentTypeCreate(BaseModel):
    name: str
    description: Optional[str] = None
    max_marks: float = 20.0
    default_discrepancy_threshold: float = 0.20
    criteria: List[RubricCriterionDetailSchema]


class AssessmentTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    max_marks: Optional[float] = None
    default_discrepancy_threshold: Optional[float] = None


class RubricVersionCreate(BaseModel):
    total_marks: float = 20.0
    criteria: List[RubricCriterionDetailSchema]


class RubricVersionOut(BaseModel):
    id: int
    assessment_type_id: int
    version: int
    total_marks: float
    is_active: bool
    criteria_data: Any
    created_at: datetime

    model_config = {"from_attributes": True}


class AssessmentTypeOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    is_active: bool
    max_marks: float
    default_discrepancy_threshold: float
    rtlp_code: Optional[str] = None
    category: Optional[str] = None
    evaluation_mode: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    active_rubric: Optional[RubricVersionOut] = None
    active_rubric_version: Optional[RubricVersionOut] = None
    rubric_versions: List[RubricVersionOut] = []

    model_config = {"from_attributes": True}


# ─── Student Typed Submission ─────────────────────────────────────────────────

class StudentTypedSubmissionCreate(BaseModel):
    typed_content: str
    is_draft: bool = False


# ─── Faculty Manual Evaluation (Faculty-First) ─────────────────────────────────

class FacultyCriterionMark(BaseModel):
    criterion_name: str
    score: float = Field(ge=0)


class FacultyEvaluationSubmitRequest(BaseModel):
    faculty_total_marks: float = Field(ge=0)
    criterion_marks: Optional[List[FacultyCriterionMark]] = None
    overall_feedback: Optional[str] = None
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    improvement_suggestions: Optional[str] = None
    irrelevant_observations: Optional[str] = None
    deduction_reasons: Optional[str] = None
    internal_notes: Optional[str] = None
    is_draft: bool = False


class FacultyEvaluationOut(BaseModel):
    id: int
    submission_id: int
    faculty_id: int
    faculty_total_marks: float
    overall_feedback: Optional[str]
    strengths: Optional[str]
    weaknesses: Optional[str]
    improvement_suggestions: Optional[str]
    irrelevant_observations: Optional[str]
    deduction_reasons: Optional[str]
    internal_notes: Optional[str]
    is_draft: bool
    submission_version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Admin Evaluation Monitoring & Comparison ─────────────────────────────────

class AdminEvaluationListItem(BaseModel):
    submission_id: int
    student_name: str
    student_id_str: str
    subject_name: str
    faculty_name: str
    assessment_title: str
    assessment_type: str
    submission_date: datetime
    submission_type: str
    faculty_status: str
    faculty_marks: Optional[float] = None
    ai_status: str
    ai_marks: Optional[float] = None
    discrepancy_value: Optional[float] = None
    discrepancy_threshold: Optional[float] = None
    calculation_method: Optional[str] = None
    final_marks: Optional[float] = None
    max_marks: float
    is_published: bool
    error_details: Optional[str] = None


class AdminComparisonDetail(BaseModel):
    submission_id: int
    student_name: str
    student_id_str: str
    subject_name: str
    faculty_name: str
    assessment_title: str
    assessment_type: str
    assessment_description: Optional[str] = None
    instructions: Optional[str] = None
    max_marks: float
    submission_date: datetime
    submission_text: Optional[str] = None
    original_filename: Optional[str] = None
    submission_type: str
    # Rubric info
    rubric_version_id: Optional[int] = None
    rubric_version_num: Optional[int] = None
    rubric_criteria: Optional[Any] = None
    # Faculty evaluation
    faculty_status: str
    faculty_marks: Optional[float] = None
    faculty_feedback: Optional[str] = None
    faculty_strengths: Optional[str] = None
    faculty_weaknesses: Optional[str] = None
    faculty_suggestions: Optional[str] = None
    faculty_irrelevant: Optional[str] = None
    faculty_deductions: Optional[str] = None
    faculty_notes: Optional[str] = None
    faculty_evaluated_at: Optional[datetime] = None
    # AI evaluation
    ai_status: str
    ai_marks: Optional[float] = None
    ai_criterion_scores: Optional[List[Dict[str, Any]]] = None
    ai_overall_feedback: Optional[str] = None
    ai_strengths: Optional[str] = None
    ai_weaknesses: Optional[str] = None
    ai_suggestions: Optional[str] = None
    ai_evidence: Optional[List[Dict[str, Any]]] = None
    ai_irrelevant_observations: Optional[List[Dict[str, Any]]] = None
    ai_error_details: Optional[str] = None
    ai_duration_seconds: Optional[float] = None
    ai_model_used: Optional[str] = None
    ai_tokens_used: Optional[int] = None
    # Final calculation
    discrepancy_value: Optional[float] = None
    discrepancy_threshold: Optional[float] = None
    calculation_method: Optional[str] = None
    final_marks: Optional[float] = None
    is_published: bool
    faculty_evaluation: Optional[Dict[str, Any]] = None
    ai_evaluation: Optional[Dict[str, Any]] = None
    scoring_comparison: Optional[Dict[str, Any]] = None


# ─── Course Profile Typed ─────────────────────────────────────────────────────

class CourseProfileTypedCreate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    syllabus: Optional[str] = None
    units_topics: Optional[Any] = None
    learning_objectives: Optional[str] = None
    expected_outcomes: Optional[str] = None
    reference_content: Optional[str] = None
    learning_materials: Optional[str] = None
    additional_info: Optional[str] = None
    is_published: bool = False
    publish: Optional[bool] = None

    @property
    def publish_requested(self) -> bool:
        return self.is_published if self.publish is None else self.publish


class CourseProfileOut(BaseModel):
    id: int
    subject_id: int
    title: Optional[str]
    description: Optional[str]
    syllabus: Optional[str]
    learning_objectives: Optional[str]
    expected_outcomes: Optional[str]
    units_topics: Optional[Any]
    reference_content: Optional[str]
    learning_materials: Optional[str]
    additional_info: Optional[str]
    is_typed_published: bool
    rag_indexed: bool

    model_config = {"from_attributes": True}
