"""SQLAlchemy ORM models for EduEval AI."""
import enum
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey,
    Integer, String, Text, JSON, UniqueConstraint
)
from sqlalchemy.orm import relationship

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


# ─── Enumerations ─────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    admin = "admin"
    faculty = "faculty"
    student = "student"


class SubmissionStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    evaluated = "evaluated"
    approved = "approved"
    rejected = "rejected"


class EvaluationStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    approved = "approved"
    rejected = "rejected"


# ─── Users ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.student)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    faculty_profile = relationship("FacultyProfile", back_populates="user", uselist=False)
    student_profile = relationship("StudentProfile", back_populates="user", uselist=False)
    audit_logs = relationship("AuditLog", back_populates="user")


class FacultyProfile(Base):
    __tablename__ = "faculty_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    department = Column(String(255))
    employee_id = Column(String(100))
    specialization = Column(String(255))
    created_at = Column(DateTime(timezone=True), default=utcnow)

    user = relationship("User", back_populates="faculty_profile")
    subjects = relationship("SubjectFaculty", back_populates="faculty")


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    student_id = Column(String(100), unique=True, nullable=False)
    program = Column(String(255))
    year_of_study = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    user = relationship("User", back_populates="student_profile")
    submissions = relationship("StudentSubmission", back_populates="student")
    enrollments = relationship("SubjectEnrollment", back_populates="student")


# ─── Subjects ─────────────────────────────────────────────────────────────────

class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    faculty_assignments = relationship("SubjectFaculty", back_populates="subject")
    enrollments = relationship("SubjectEnrollment", back_populates="subject")
    course_profile = relationship("CourseProfile", back_populates="subject", uselist=False)
    assessments = relationship("Assessment", back_populates="subject")


class SubjectFaculty(Base):
    __tablename__ = "subject_faculty"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    faculty_id = Column(Integer, ForeignKey("faculty_profiles.id"), nullable=False)
    assigned_at = Column(DateTime(timezone=True), default=utcnow)

    subject = relationship("Subject", back_populates="faculty_assignments")
    faculty = relationship("FacultyProfile", back_populates="subjects")


class SubjectEnrollment(Base):
    __tablename__ = "subject_enrollments"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("student_profiles.id"), nullable=False)
    enrolled_at = Column(DateTime(timezone=True), default=utcnow)

    subject = relationship("Subject", back_populates="enrollments")
    student = relationship("StudentProfile", back_populates="enrollments")


# ─── Course Profile ───────────────────────────────────────────────────────────

class CourseProfile(Base):
    __tablename__ = "course_profiles"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), unique=True, nullable=False)
    description = Column(Text)
    syllabus = Column(Text)
    learning_objectives = Column(Text)
    expected_outcomes = Column(Text)
    important_concepts = Column(Text)
    definitions = Column(Text)
    reference_answers = Column(Text)
    rag_indexed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Added fields for typed course profile
    title = Column(String(255), nullable=True)
    units_topics = Column(JSON, nullable=True)
    learning_materials = Column(Text, nullable=True)
    reference_content = Column(Text, nullable=True)
    additional_info = Column(Text, nullable=True)
    is_typed_published = Column(Boolean, default=False)

    subject = relationship("Subject", back_populates="course_profile")
    documents = relationship("CourseDocument", back_populates="course_profile")
    topics = relationship("CourseTopic", back_populates="course_profile")


class CourseDocument(Base):
    __tablename__ = "course_documents"

    id = Column(Integer, primary_key=True, index=True)
    course_profile_id = Column(Integer, ForeignKey("course_profiles.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_path = Column(String(500), nullable=False)
    extracted_text = Column(Text)
    doc_type = Column(String(100))  # syllabus, notes, reference, etc.
    page_count = Column(Integer)
    is_indexed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    course_profile = relationship("CourseProfile", back_populates="documents")


class CourseTopic(Base):
    __tablename__ = "course_topics"

    id = Column(Integer, primary_key=True, index=True)
    course_profile_id = Column(Integer, ForeignKey("course_profiles.id"), nullable=False)
    unit_number = Column(Integer)
    unit_name = Column(String(255))
    topic_name = Column(String(255), nullable=False)
    subtopics = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    course_profile = relationship("CourseProfile", back_populates="topics")


# ─── Assessment Types & Rubrics (Admin-Managed) ──────────────────────────────

class AssessmentType(Base):
    __tablename__ = "assessment_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    max_marks = Column(Float, default=20.0)
    default_discrepancy_threshold = Column(Float, default=0.20)
    # RTLP linkage: policy section code, category, and how the AI evaluates it
    rtlp_code = Column(String(20), nullable=True)
    category = Column(String(50), nullable=True)
    evaluation_mode = Column(String(30), default="document")  # document | answer_key | observation
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    rubric_versions = relationship("RubricVersion", back_populates="assessment_type", cascade="all, delete-orphan")
    assessments = relationship("Assessment", back_populates="assessment_type_rel")


class RubricVersion(Base):
    __tablename__ = "rubric_versions"

    id = Column(Integer, primary_key=True, index=True)
    assessment_type_id = Column(Integer, ForeignKey("assessment_types.id"), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    total_marks = Column(Float, default=20.0)
    is_active = Column(Boolean, default=True)
    criteria_data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    assessment_type = relationship("AssessmentType", back_populates="rubric_versions")
    assessments = relationship("Assessment", back_populates="rubric_version_rel")
    submissions = relationship("StudentSubmission", back_populates="rubric_version_rel")


# ─── Assessments ──────────────────────────────────────────────────────────────

class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    assessment_type = Column(String(100))  # legacy string name
    max_marks = Column(Float, nullable=False, default=20.0)
    due_date = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    # Dynamic assessment type and rubric linkage
    assessment_type_id = Column(Integer, ForeignKey("assessment_types.id"), nullable=True)
    rubric_version_id = Column(Integer, ForeignKey("rubric_versions.id"), nullable=True)
    instructions = Column(Text, nullable=True)
    start_date = Column(DateTime(timezone=True), nullable=True)
    allowed_file_types = Column(String(255), nullable=True, default="pdf,docx,doc,pptx,ppt,txt,images")
    discrepancy_threshold = Column(Float, default=0.20)
    # Course-profile grounding for the AI evaluator
    course_unit = Column(String(255), nullable=True)       # unit/module of the course profile this assessment covers
    reference_answer = Column(Text, nullable=True)         # model answer or answer key (never shown to students)
    # Admin-authored rubric for this assessment (criteria_data format). Takes precedence over
    # the assessment type's rubric version. Started from an RTLP template and optionally edited.
    rubric_data = Column(JSON, nullable=True)
    rubric_source = Column(String(50), nullable=True)      # e.g. "RTLP 14.3.7" or "custom"
    evaluation_mode = Column(String(30), nullable=True)    # document | answer_key | observation
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    subject = relationship("Subject", back_populates="assessments")
    subject_links = relationship("AssessmentSubject", back_populates="assessment", cascade="all, delete-orphan")
    rubric = relationship("MarkingRubric", back_populates="assessment", uselist=False)
    submissions = relationship("StudentSubmission", back_populates="assessment")
    assessment_type_rel = relationship("AssessmentType", back_populates="assessments")
    rubric_version_rel = relationship("RubricVersion", back_populates="assessments")


class AssessmentSubject(Base):
    """Maps one (shared) assessment to every subject it is offered in."""
    __tablename__ = "assessment_subjects"
    __table_args__ = (UniqueConstraint("assessment_id", "subject_id", name="uq_assessment_subject"),)

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id"), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    assessment = relationship("Assessment", back_populates="subject_links")
    subject = relationship("Subject")


class MarkingRubric(Base):
    __tablename__ = "marking_rubrics"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id"), unique=True, nullable=False)
    description = Column(Text)
    total_marks = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    assessment = relationship("Assessment", back_populates="rubric")
    criteria = relationship("RubricCriterion", back_populates="rubric", cascade="all, delete-orphan")


class RubricCriterion(Base):
    __tablename__ = "rubric_criteria"

    id = Column(Integer, primary_key=True, index=True)
    rubric_id = Column(Integer, ForeignKey("marking_rubrics.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    max_marks = Column(Float, nullable=False)
    weight = Column(Float, default=1.0)
    order_index = Column(Integer, default=0)

    rubric = relationship("MarkingRubric", back_populates="criteria")
    criterion_scores = relationship("CriterionScore", back_populates="criterion")


# ─── Student Submissions ──────────────────────────────────────────────────────

class StudentSubmission(Base):
    __tablename__ = "student_submissions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("student_profiles.id"), nullable=False)
    assessment_id = Column(Integer, ForeignKey("assessments.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    extracted_text = Column(Text)
    extraction_status = Column(String(50), default="pending")
    page_count = Column(Integer, default=1)
    status = Column(Enum(SubmissionStatus), default=SubmissionStatus.pending)
    submitted_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Submission extensions
    submission_type = Column(String(50), default="upload")  # "upload" or "typed"
    typed_content = Column(Text, nullable=True)
    submission_version = Column(Integer, default=1)
    is_draft = Column(Boolean, default=False)
    rubric_version_id = Column(Integer, ForeignKey("rubric_versions.id"), nullable=True)
    # Subject the student submitted through (an assessment can be shared by several subjects)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=True)

    student = relationship("StudentProfile", back_populates="submissions")
    subject = relationship("Subject")
    assessment = relationship("Assessment", back_populates="submissions")
    evaluation = relationship("AIEvaluation", back_populates="submission", uselist=False)
    faculty_evaluation = relationship("FacultyEvaluation", back_populates="submission", uselist=False)
    final_evaluation = relationship("FinalEvaluation", back_populates="submission", uselist=False)
    rubric_version_rel = relationship("RubricVersion", back_populates="submissions")


# ─── AI Evaluations ───────────────────────────────────────────────────────────

class AIEvaluation(Base):
    __tablename__ = "ai_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("student_submissions.id"), unique=True, nullable=False)
    evaluated_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Rubric linkage & structured tracking
    rubric_version_id = Column(Integer, ForeignKey("rubric_versions.id"), nullable=True)
    error_details = Column(Text, nullable=True)
    ai_criterion_scores_json = Column(JSON, nullable=True)
    ai_irrelevant_observations_json = Column(JSON, nullable=True)
    ai_status = Column(String(50), default="pending")  # pending, processing, completed, failed
    segments_json = Column(JSON, nullable=True)      # numbered submission segments [{id, paragraph, text}]
    annotations_json = Column(JSON, nullable=True)   # [{segment_id, criterion_index, type, category, comment}]

    # AI Results
    ai_total_score = Column(Float)
    ai_feedback = Column(Text)
    ai_strengths = Column(Text)
    ai_weaknesses = Column(Text)
    ai_missing_concepts = Column(Text)
    ai_improvement_suggestions = Column(Text)
    ai_overall_feedback = Column(Text)
    ai_raw_response = Column(Text)  # JSON string

    # Faculty overrides (legacy compatibility)
    faculty_total_score = Column(Float)
    faculty_feedback = Column(Text)
    faculty_notes = Column(Text)

    # Status
    status = Column(Enum(EvaluationStatus), default=EvaluationStatus.pending)
    openai_model_used = Column(String(100))
    tokens_used = Column(Integer)
    evaluation_duration_seconds = Column(Float)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    approved_at = Column(DateTime(timezone=True))

    submission = relationship("StudentSubmission", back_populates="evaluation")
    criterion_scores = relationship("CriterionScore", back_populates="evaluation", cascade="all, delete-orphan")
    supporting_evidence = relationship("SupportingEvidence", back_populates="evaluation", cascade="all, delete-orphan")
    approved_feedback = relationship("ApprovedFeedback", back_populates="evaluation", uselist=False)


# ─── Faculty Manual Evaluations (Faculty-First) ───────────────────────────────

class FacultyEvaluation(Base):
    __tablename__ = "faculty_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("student_submissions.id"), unique=True, nullable=False)
    faculty_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    faculty_total_marks = Column(Float, nullable=False)
    overall_feedback = Column(Text)
    strengths = Column(Text)
    weaknesses = Column(Text)
    improvement_suggestions = Column(Text)
    irrelevant_observations = Column(Text)
    deduction_reasons = Column(Text)
    internal_notes = Column(Text)
    criterion_marks = Column(JSON, nullable=True)  # [{criterion_name, max_marks, score}]
    is_draft = Column(Boolean, default=False)
    submission_version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    submission = relationship("StudentSubmission", back_populates="faculty_evaluation")
    faculty = relationship("User")


# ─── Final Authoritative Combined Evaluations ─────────────────────────────────

class FinalEvaluation(Base):
    __tablename__ = "final_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("student_submissions.id"), unique=True, nullable=False)
    faculty_evaluation_id = Column(Integer, ForeignKey("faculty_evaluations.id"), nullable=True)
    ai_evaluation_id = Column(Integer, ForeignKey("ai_evaluations.id"), nullable=True)

    faculty_marks = Column(Float, nullable=False)
    ai_marks = Column(Float, nullable=True)
    discrepancy_value = Column(Float, nullable=True)
    discrepancy_threshold = Column(Float, nullable=False, default=4.0)
    calculation_method = Column(String(100), nullable=False)  # "faculty_retained" or "averaged"
    final_total_marks = Column(Float, nullable=False)

    combined_feedback = Column(JSON, nullable=True)
    unified_overall_feedback = Column(Text, nullable=True)
    unified_strengths = Column(Text, nullable=True)
    unified_weaknesses = Column(Text, nullable=True)
    unified_criterion_feedback = Column(JSON, nullable=True)
    unified_improvement_suggestions = Column(Text, nullable=True)
    unified_irrelevant_observations = Column(JSON, nullable=True)
    unified_final_remarks = Column(Text, nullable=True)
    final_criterion_scores = Column(JSON, nullable=True)  # [{criterion_name, max_marks, faculty, ai, final}]
    feedback_document = Column(JSON, nullable=True)       # payload rendered as the student feedback document

    is_published = Column(Boolean, default=False)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    submission = relationship("StudentSubmission", back_populates="final_evaluation")
    faculty_evaluation = relationship("FacultyEvaluation")
    ai_evaluation = relationship("AIEvaluation")


class CriterionScore(Base):
    __tablename__ = "criterion_scores"

    id = Column(Integer, primary_key=True, index=True)
    evaluation_id = Column(Integer, ForeignKey("ai_evaluations.id"), nullable=False)
    criterion_id = Column(Integer, ForeignKey("rubric_criteria.id"), nullable=True)
    criterion_name = Column(String(255), nullable=False)
    max_marks = Column(Float, nullable=False)
    ai_score = Column(Float, nullable=False)
    faculty_score = Column(Float)
    justification = Column(Text)

    evaluation = relationship("AIEvaluation", back_populates="criterion_scores")
    criterion = relationship("RubricCriterion", back_populates="criterion_scores")


class SupportingEvidence(Base):
    __tablename__ = "supporting_evidence"

    id = Column(Integer, primary_key=True, index=True)
    evaluation_id = Column(Integer, ForeignKey("ai_evaluations.id"), nullable=False)
    evidence_text = Column(Text, nullable=False)
    source = Column(String(100))  # "student_submission" or "course_reference"
    relevance_note = Column(Text)

    evaluation = relationship("AIEvaluation", back_populates="supporting_evidence")


class ApprovedFeedback(Base):
    __tablename__ = "approved_feedback"

    id = Column(Integer, primary_key=True, index=True)
    evaluation_id = Column(Integer, ForeignKey("ai_evaluations.id"), unique=True, nullable=False)
    final_score = Column(Float, nullable=False)
    final_feedback = Column(Text, nullable=False)
    is_published = Column(Boolean, default=False)
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    approved_at = Column(DateTime(timezone=True), default=utcnow)

    evaluation = relationship("AIEvaluation", back_populates="approved_feedback")


# ─── Audit Logs ───────────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(255), nullable=False)
    resource_type = Column(String(100))
    resource_id = Column(Integer)
    details = Column(Text)
    ip_address = Column(String(45))
    created_at = Column(DateTime(timezone=True), default=utcnow)

    user = relationship("User", back_populates="audit_logs")

