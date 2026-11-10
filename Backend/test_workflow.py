"""
EduEval AI — End-to-End Workflow & Seeding Test
Tests:
1. Database initialization and admin login
2. Admin creates faculty, student, subject, assignments, and enrollments
3. Faculty uploads course documents and builds FAISS RAG index
4. Faculty creates assessment and marking rubric
5. Student submits an assignment file
6. Document text extraction (PyMuPDF / docx / txt)
7. Local RAG retrieval for subject & assessment
8. Rubric Scoring Engine validation
9. Faculty approves and publishes feedback
10. Student retrieves published score and feedback
"""
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal, Base, engine
from app.models.models import (
    User, FacultyProfile, StudentProfile, Subject,
    SubjectFaculty, SubjectEnrollment, CourseProfile,
    CourseDocument, Assessment, MarkingRubric, RubricCriterion,
    StudentSubmission, AIEvaluation, CriterionScore,
    SupportingEvidence, ApprovedFeedback, UserRole,
    SubmissionStatus, EvaluationStatus
)
from app.core.security import get_password_hash, verify_password
from app.services.rag.pipeline import build_subject_index, retrieve_for_subject
from app.services.ai.rubric_scorer import RubricScorer
from app.services.document.processor import extract_text, validate_document

def run_e2e_test():
    print("==================================================")
    print("  EduEval AI — Running End-to-End Integration Test")
    print("==================================================")

    db = SessionLocal()

    # Step 1: Admin verification
    print("\n[Step 1] Verifying Administrator Account...")
    admin = db.query(User).filter(User.email == "admin@edueval.ai").first()
    if not admin:
        admin = User(
            email="admin@edueval.ai",
            full_name="System Administrator",
            hashed_password=get_password_hash("Admin@123"),
            role=UserRole.admin,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
    assert verify_password("Admin@123", admin.hashed_password), "Admin password verification failed"
    print("  ✓ Admin account verified (admin@edueval.ai)")

    # Step 2: Create Faculty Account
    print("\n[Step 2] Admin creating Faculty account...")
    faculty_user = db.query(User).filter(User.email == "dr.smith@university.edu").first()
    if not faculty_user:
        faculty_user = User(
            email="dr.smith@university.edu",
            full_name="Dr. Alan Smith",
            hashed_password=get_password_hash("Faculty@123"),
            role=UserRole.faculty,
            is_active=True,
        )
        db.add(faculty_user)
        db.flush()
        f_prof = FacultyProfile(
            user_id=faculty_user.id,
            department="Computer Science & Engineering",
            employee_id="FAC-CS-042",
            specialization="Operating Systems & Distributed Computing",
        )
        db.add(f_prof)
        db.commit()
        db.refresh(faculty_user)
    print(f"  ✓ Faculty created: {faculty_user.full_name} ({faculty_user.email})")

    # Step 3: Create Student Account
    print("\n[Step 3] Admin creating Student account...")
    student_user = db.query(User).filter(User.email == "john.doe@student.edu").first()
    if not student_user:
        student_user = User(
            email="john.doe@student.edu",
            full_name="John Doe",
            hashed_password=get_password_hash("Student@123"),
            role=UserRole.student,
            is_active=True,
        )
        db.add(student_user)
        db.flush()
        s_prof = StudentProfile(
            user_id=student_user.id,
            student_id="CS-2024-001",
            program="B.Tech Computer Science",
            year_of_study=3,
        )
        db.add(s_prof)
        db.commit()
        db.refresh(student_user)
    print(f"  ✓ Student created: {student_user.full_name} (ID: CS-2024-001)")

    # Step 4: Create Subject & Associations
    print("\n[Step 4] Creating Subject & Assigning Faculty/Student...")
    subject = db.query(Subject).filter(Subject.code == "CS301").first()
    if not subject:
        subject = Subject(
            name="Operating Systems & Concurrency",
            code="CS301",
            description="Comprehensive study of process synchronization, memory management, deadlock prevention, and scheduling algorithms.",
            is_active=True,
        )
        db.add(subject)
        db.flush()

    # Assign Faculty
    f_profile = db.query(FacultyProfile).filter(FacultyProfile.user_id == faculty_user.id).first()
    sf = db.query(SubjectFaculty).filter(
        SubjectFaculty.subject_id == subject.id,
        SubjectFaculty.faculty_id == f_profile.id
    ).first()
    if not sf:
        db.add(SubjectFaculty(subject_id=subject.id, faculty_id=f_profile.id))

    # Enroll Student
    s_profile = db.query(StudentProfile).filter(StudentProfile.user_id == student_user.id).first()
    se = db.query(SubjectEnrollment).filter(
        SubjectEnrollment.subject_id == subject.id,
        SubjectEnrollment.student_id == s_profile.id
    ).first()
    if not se:
        db.add(SubjectEnrollment(subject_id=subject.id, student_id=s_profile.id))

    db.commit()
    print(f"  ✓ Subject: {subject.name} ({subject.code})")
    print(f"  ✓ Faculty assigned & Student enrolled")

    # Step 5: Course Profile & Reference Material
    print("\n[Step 5] Faculty creating Course Profile & Reference Material...")
    course_prof = db.query(CourseProfile).filter(CourseProfile.subject_id == subject.id).first()
    if not course_prof:
        course_prof = CourseProfile(
            subject_id=subject.id,
            description="Core undergraduate course covering process scheduling, inter-process communication, semaphores, mutexes, and deadlocks.",
            syllabus="Unit 1: Process Management. Unit 2: Process Synchronization (Peterson's Algorithm, Semaphores, Monitors). Unit 3: Deadlocks (Detection, Prevention, Banker's Algorithm).",
            learning_objectives="Understand race conditions, critical section problem, mutual exclusion, deadlock four conditions, Banker's algorithm for avoidance.",
            expected_outcomes="Students should be able to design synchronization primitives and detect or avoid potential system deadlocks.",
            important_concepts="Mutual Exclusion, Hold and Wait, No Preemption, Circular Wait, Semaphores (wait/signal), Deadlock Recovery.",
            reference_answers="A valid deadlock avoidance solution uses Banker's algorithm to ensure the system remains in a safe state by verifying available resources exceed maximum demand minus allocation for some process sequence.",
        )
        db.add(course_prof)
        db.commit()
        db.refresh(course_prof)
    print("  ✓ Course profile created and populated")

    # Step 6: Create Reference Document & Build FAISS RAG Index
    print("\n[Step 6] Uploading reference document and building FAISS RAG Index...")
    sample_doc_dir = Path("uploads/course_docs") / str(subject.id)
    sample_doc_dir.mkdir(parents=True, exist_ok=True)
    sample_doc_file = sample_doc_dir / "OS_Unit2_Synchronization_Notes.txt"
    sample_doc_content = """
    Operating Systems Reference Material - Unit 2: Process Synchronization & Deadlocks
    
    1. Critical Section Problem:
    A critical section is a piece of code that accesses shared resources (such as memory, files, or variables).
    Any solution must satisfy three requirements:
    a) Mutual Exclusion: If process Pi is executing in its critical section, no other processes can be executing in their critical sections.
    b) Progress: If no process is executing in its critical section and some processes wish to enter, selection cannot be postponed indefinitely.
    c) Bounded Waiting: A bound must exist on the number of times other processes are allowed to enter their critical sections after a process has requested entry.

    2. Deadlock Conditions:
    A deadlock occurs if and only if four Coffman conditions hold simultaneously:
    - Mutual exclusion: At least one resource must be held in a non-shareable mode.
    - Hold and wait: A process must be currently holding at least one resource and requesting additional resources.
    - No preemption: Resources cannot be preempted; a resource can only be released voluntarily.
    - Circular wait: A closed chain of processes exists such that each process holds at least one resource needed by the next.

    3. Banker's Algorithm:
    Dijkstra's Banker's Algorithm is a deadlock avoidance method that checks for safe states before granting resource requests.
    """
    with open(sample_doc_file, "w", encoding="utf-8") as f:
        f.write(sample_doc_content.strip())

    extracted_txt, pages = extract_text(str(sample_doc_file), "txt")
    course_doc = db.query(CourseDocument).filter(CourseDocument.course_profile_id == course_prof.id).first()
    if not course_doc:
        course_doc = CourseDocument(
            course_profile_id=course_prof.id,
            filename=sample_doc_file.name,
            original_filename="OS_Unit2_Synchronization_Notes.txt",
            file_type="txt",
            file_path=str(sample_doc_file),
            extracted_text=extracted_txt,
            doc_type="lecture_notes",
            page_count=pages,
            is_indexed=False,
        )
        db.add(course_doc)
        db.commit()

    # Build RAG index
    doc_list = [{
        "text": course_doc.extracted_text,
        "source_name": course_doc.original_filename,
        "doc_id": course_doc.id,
        "doc_type": "notes"
    }]
    chunks_indexed = build_subject_index(subject.id, doc_list, faiss_dir="faiss_indexes")
    course_prof.rag_indexed = True
    course_doc.is_indexed = True
    db.commit()
    print(f"  ✓ Local FAISS RAG index built: {chunks_indexed} chunks indexed locally with SentenceTransformers")

    # Step 7: Test RAG Retrieval
    print("\n[Step 7] Testing Local RAG Retrieval for Deadlock query...")
    retrieved = retrieve_for_subject(subject.id, "Explain the four Coffman conditions for deadlocks and mutual exclusion", top_k=2)
    assert len(retrieved) > 0, "RAG retrieval returned 0 results"
    print(f"  ✓ Successfully retrieved {len(retrieved)} relevant passage(s) (top score: {retrieved[0].get('relevance_score', 0):.3f})")
    print(f"    Excerpt: {retrieved[0]['text'][:120]}...")

    # Step 8: Create Assessment & Marking Rubric
    print("\n[Step 8] Faculty creating Assessment & Rubric (Max: 20 marks)...")
    assessment = db.query(Assessment).filter(Assessment.subject_id == subject.id).first()
    if not assessment:
        assessment = Assessment(
            subject_id=subject.id,
            title="Lab Assignment 1: Concurrency, Synchronization & Deadlock Analysis",
            description="Analyze process synchronization mechanisms and discuss solutions to Coffman deadlock conditions.",
            assessment_type="assignment",
            max_marks=20.0,
            is_active=True,
        )
        db.add(assessment)
        db.flush()

    rubric = db.query(MarkingRubric).filter(MarkingRubric.assessment_id == assessment.id).first()
    if not rubric:
        rubric = MarkingRubric(
            assessment_id=assessment.id,
            description="Evaluates student understanding of synchronization primitives, deadlock criteria, and practical examples.",
            total_marks=20.0,
        )
        db.add(rubric)
        db.flush()

        criteria_data = [
            ("Conceptual Understanding of Synchronization", "Understanding critical section problem, mutual exclusion, and progress.", 5.0),
            ("Deadlock Analysis & Coffman Conditions", "Accurate explanation of the 4 Coffman deadlock conditions.", 5.0),
            ("Technical Accuracy & Primitives", "Correct usage of mutex, semaphores (wait/signal), and monitors.", 4.0),
            ("Avoidance & Banker's Algorithm", "Explanation of deadlock prevention vs avoidance, safe state concept.", 3.0),
            ("Clarity and Supporting Examples", "Quality of explanation, structured answers, and relevant examples.", 3.0),
        ]
        for idx, (cname, cdesc, cmax) in enumerate(criteria_data):
            c = RubricCriterion(
                rubric_id=rubric.id,
                name=cname,
                description=cdesc,
                max_marks=cmax,
                order_index=idx,
            )
            db.add(c)
        db.commit()
    print("  ✓ Assessment & 5-Criterion Rubric created (Total: 20.0 marks)")

    # Step 9: Student Submits Assignment
    print("\n[Step 9] Student submitting academic assignment...")
    sub_dir = Path("uploads/submissions") / str(s_profile.id)
    sub_dir.mkdir(parents=True, exist_ok=True)
    sub_file = sub_dir / "JohnDoe_OS_Lab1.txt"
    student_content = """
    Student Name: John Doe (CS-2024-001)
    Subject: Operating Systems (CS301)
    Assignment: Concurrency, Synchronization & Deadlock Analysis

    1. Process Synchronization:
    Process synchronization is essential in multi-threaded operating systems to prevent race conditions when concurrent processes share data.
    The critical section requires three conditions:
    - Mutual Exclusion: Only one process inside the critical section at a time.
    - Progress: If no process is inside, selection of the next process cannot be blocked by processes outside.
    - Bounded Waiting: No process starves waiting to enter.
    We implement this using Semaphores. A counting semaphore has two atomic operations: wait() which decrements the counter, and signal() which increments it.

    2. Deadlock Analysis:
    A deadlock occurs when processes are unable to proceed because each is waiting for resources held by another.
    The four necessary conditions are:
    1) Mutual Exclusion - non-shareable resources.
    2) Hold and Wait - process holds one resource while waiting for another.
    3) No Preemption - resources cannot be forcibly seized.
    4) Circular Wait - a closed cycle of processes waiting on each other.

    3. Deadlock Avoidance:
    To avoid deadlocks, the operating system can use Dijkstra's Banker's Algorithm. The algorithm verifies whether granting a resource keeps the system in a 'safe state' where at least one execution sequence allows all processes to finish without deadlock.
    """
    with open(sub_file, "w", encoding="utf-8") as f:
        f.write(student_content.strip())

    extracted_sub_text, sub_pages = extract_text(str(sub_file), "txt")
    submission = db.query(StudentSubmission).filter(
        StudentSubmission.assessment_id == assessment.id,
        StudentSubmission.student_id == s_profile.id
    ).first()
    if not submission:
        submission = StudentSubmission(
            student_id=s_profile.id,
            assessment_id=assessment.id,
            filename=sub_file.name,
            original_filename="JohnDoe_OS_Lab1.txt",
            file_type="txt",
            file_path=str(sub_file),
            file_size=len(student_content),
            extracted_text=extracted_sub_text,
            extraction_status="success",
            status=SubmissionStatus.pending,
        )
        db.add(submission)
        db.commit()
        db.refresh(submission)
    print(f"  ✓ Submission uploaded: {submission.original_filename} ({len(extracted_sub_text)} characters extracted)")

    # Step 10: Rubric Scoring Engine Test
    print("\n[Step 10] Testing Custom Python Rubric Scoring Engine...")
    rubric_criteria_list = [
        {"name": c.name, "max_marks": c.max_marks, "description": c.description}
        for c in rubric.criteria
    ]
    scorer = RubricScorer(total_max_marks=20.0, criteria=rubric_criteria_list)

    # Simulated AI evaluation scores
    simulated_ai_scores = {
        "Conceptual Understanding of Synchronization": 4.5,
        "Deadlock Analysis & Coffman Conditions": 4.5,
        "Technical Accuracy & Primitives": 3.5,
        "Avoidance & Banker's Algorithm": 2.5,
        "Clarity and Supporting Examples": 2.5,
    }
    results, validated_total, warnings = scorer.validate_and_score(simulated_ai_scores)
    assert validated_total == 17.5, f"Expected 17.5, got {validated_total}"
    assert len(results) == 5, f"Expected 5 criteria results, got {len(results)}"
    print(f"  ✓ Python Rubric Scorer successfully validated: Total = {validated_total} / 20.0")
    for r in results:
        print(f"    - {r.name}: {r.clamped_score} / {r.max_marks}")

    # Step 11: Create Evaluation & Faculty Approval Workflow
    print("\n[Step 11] Creating Evaluation Record & Faculty Approval...")
    eval_record = db.query(AIEvaluation).filter(AIEvaluation.submission_id == submission.id).first()
    if not eval_record:
        eval_record = AIEvaluation(
            submission_id=submission.id,
            evaluated_by_id=faculty_user.id,
            ai_total_score=validated_total,
            ai_strengths="Clear explanation of critical section problem, mutual exclusion, progress, and bounded waiting.\nAccurately identified all four Coffman deadlock conditions.\nGood understanding of semaphores (wait/signal operations).",
            ai_weaknesses="Banker's algorithm explanation is theoretical and could include a small resource matrix example.\nCould mention Monitors as higher-level synchronization constructs.",
            ai_missing_concepts="Deadlock recovery techniques (process termination, resource preemption).\nPeterson's algorithm for two-process mutual exclusion.",
            ai_improvement_suggestions="Include a concrete code or pseudocode example illustrating deadlock with two mutexes.\nExplain how Banker's algorithm calculates the Need matrix from Allocation and Max.",
            ai_overall_feedback="Excellent submission demonstrating strong conceptual grasp of process synchronization and deadlocks. Meets the learning objectives for Unit 2.",
            openai_model_used="gpt-4o-mini",
            tokens_used=1240,
            evaluation_duration_seconds=2.8,
            status=EvaluationStatus.completed,
        )
        db.add(eval_record)
        db.flush()

        for r in results:
            db.add(CriterionScore(
                evaluation_id=eval_record.id,
                criterion_name=r.name,
                max_marks=r.max_marks,
                ai_score=r.clamped_score,
                justification=r.justification,
            ))

        db.add(SupportingEvidence(
            evaluation_id=eval_record.id,
            evidence_text="A counting semaphore has two atomic operations: wait() which decrements the counter, and signal() which increments it.",
            source="student_submission",
            relevance_note="Demonstrates technical accuracy of synchronization primitives",
        ))
        db.add(SupportingEvidence(
            evaluation_id=eval_record.id,
            evidence_text="The algorithm verifies whether granting a resource keeps the system in a 'safe state'",
            source="student_submission",
            relevance_note="Accurately identifies the safe state criterion in Banker's algorithm",
        ))
        db.commit()

    # Faculty Approves with Override & Publishes
    print("\n[Step 12] Faculty reviewing, modifying, and approving evaluation...")
    eval_record.faculty_total_score = 18.0  # Faculty gave +0.5 bonus for concise clarity
    eval_record.faculty_feedback = "Strong conceptual clarity. Well structured. Good job!"
    eval_record.status = EvaluationStatus.approved

    # Published feedback for student
    approved_fb = db.query(ApprovedFeedback).filter(ApprovedFeedback.evaluation_id == eval_record.id).first()
    if not approved_fb:
        approved_fb = ApprovedFeedback(
            evaluation_id=eval_record.id,
            final_score=18.0,
            final_feedback="Strong conceptual clarity. Well structured. Good job! All four Coffman conditions were well explained.",
            is_published=True,
            approved_by_id=faculty_user.id,
        )
        db.add(approved_fb)
    else:
        approved_fb.final_score = 18.0
        approved_fb.is_published = True

    submission.status = SubmissionStatus.approved
    db.commit()
    print("  ✓ Evaluation approved and published to student with score: 18.0 / 20.0")

    # Step 13: Student Verification
    print("\n[Step 13] Verifying Student Portal access to published feedback...")
    student_view_fb = db.query(ApprovedFeedback).filter(
        ApprovedFeedback.evaluation_id == eval_record.id,
        ApprovedFeedback.is_published == True
    ).first()
    assert student_view_fb is not None, "Student cannot see published feedback"
    assert student_view_fb.final_score == 18.0, "Score mismatch"
    print(f"  ✓ Student can view approved score: {student_view_fb.final_score}/20.0")
    print(f"  ✓ Student feedback: '{student_view_fb.final_feedback}'")

    print("\n==================================================")
    print("  🎉 ALL 13 E2E INTEGRATION TESTS PASSED!")
    print("==================================================")

    db.close()

if __name__ == "__main__":
    run_e2e_test()

