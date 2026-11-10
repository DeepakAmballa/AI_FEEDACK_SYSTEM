"""SQLAlchemy ORM models for EduEval AI."""
import enum
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey,
    Integer, String, Text, JSON
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


# ─── Assessments ──────────────────────────────────────────────────────────────

class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    assessment_type = Column(String(100))  # assignment, journal, presentation, report
    max_marks = Column(Float, nullable=False, default=20.0)
    due_date = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    subject = relationship("Subject", back_populates="assessments")
    rubric = relationship("MarkingRubric", back_populates="assessment", uselist=False)
    submissions = relationship("StudentSubmission", back_populates="assessment")


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

    student = relationship("StudentProfile", back_populates="submissions")
    assessment = relationship("Assessment", back_populates="submissions")
    evaluation = relationship("AIEvaluation", back_populates="submission", uselist=False)


# ─── AI Evaluations ───────────────────────────────────────────────────────────

class AIEvaluation(Base):
    __tablename__ = "ai_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("student_submissions.id"), unique=True, nullable=False)
    evaluated_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # AI Results
    ai_total_score = Column(Float)
    ai_feedback = Column(Text)
    ai_strengths = Column(Text)
    ai_weaknesses = Column(Text)
    ai_missing_concepts = Column(Text)
    ai_improvement_suggestions = Column(Text)
    ai_overall_feedback = Column(Text)
    ai_raw_response = Column(Text)  # JSON string

    # Faculty overrides
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

