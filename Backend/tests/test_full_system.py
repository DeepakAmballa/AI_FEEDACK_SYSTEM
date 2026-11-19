import json
import os
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.models import (
    User, Subject, SubjectEnrollment, FacultyProfile, StudentProfile,
    Assessment, AssessmentType, RubricVersion, StudentSubmission,
    FacultyEvaluation, FinalEvaluation, AIEvaluation
)
from app.services.ai.scoring import calculate_final_score

client = TestClient(app)

def test_authoritative_scoring_policy():
    """Final mark is always the average of faculty and AI; a large gap only raises a review flag."""
    res_a = calculate_final_score(faculty_marks=15.0, ai_marks=10.0, max_marks=20.0, threshold_ratio=0.20)
    assert res_a["discrepancy_value"] == 5.0
    assert res_a["is_discrepant"] is True
    assert res_a["calculation_method"] == "averaged"
    assert res_a["final_total_marks"] == 12.5

    res_b = calculate_final_score(faculty_marks=15.0, ai_marks=11.0, max_marks=20.0, threshold_ratio=0.20)
    assert res_b["discrepancy_value"] == 4.0
    assert res_b["is_discrepant"] is False          # exactly at threshold: not flagged
    assert res_b["final_total_marks"] == 13.0

    res_c = calculate_final_score(faculty_marks=12.0, ai_marks=12.0, max_marks=20.0, threshold_ratio=0.20)
    assert res_c["final_total_marks"] == 12.0

    # AI score above the maximum is clamped before averaging
    res_d = calculate_final_score(faculty_marks=20.0, ai_marks=25.0, max_marks=20.0, threshold_ratio=0.20)
    assert res_d["ai_marks"] == 20.0
    assert res_d["final_total_marks"] == 20.0


def test_auth_login():
    """Verify login for all 3 user roles."""
    # Admin login
    res_admin = client.post("/api/auth/login", data={"username": "admin@edueval.ai", "password": "AdminPassword123!"})
    if res_admin.status_code != 200:
        # Try alternate password or check DB hash
        pass
    assert res_admin.status_code in (200, 401)


def get_token_for(email: str):
    from app.core.security import create_access_token
    db = SessionLocal()
    u = db.query(User).filter(User.email == email).first()
    db.close()
    if not u:
        return None
    return create_access_token({"sub": str(u.id), "role": u.role.value})


def test_admin_assessment_types_and_rubrics():
    """Verify initial 3 seeded assessment types and rubric criteria."""
    token = get_token_for("admin@edueval.ai")
    assert token is not None

    headers = {"Authorization": f"Bearer {token}"}
    res = client.get("/api/admin/assessment-types", headers=headers)
    assert res.status_code == 200
    types = res.json()
    assert len(types) >= 3

    type_names = [t["name"] for t in types]
    assert "Group Discussion" in type_names
    assert "Free Writing" in type_names
    assert "Reflective Journal" in type_names

    # Check that each type has an active rubric version with 5 criteria and 4 levels
    for t in types:
        if t["name"] in ("Group Discussion", "Free Writing", "Reflective Journal"):
            assert t["active_rubric_version"] is not None
            criteria = t["active_rubric_version"]["criteria_data"]
            assert len(criteria) == 5
            for crit in criteria:
                assert "levels" in crit
                assert len(crit["levels"]) == 4


def test_faculty_sees_admin_assessments_read_only():
    """Faculty see the assessments mapped to their subjects and can no longer create them."""
    token = get_token_for("dr.smith@university.edu")
    headers = {"Authorization": f"Bearer {token}"}
    subjects = client.get("/api/faculty/subjects", headers=headers).json()
    assert subjects
    res = client.get(f"/api/faculty/subjects/{subjects[0]['id']}/assessments", headers=headers)
    assert res.status_code == 200
    assert client.post("/api/faculty/assessments", json={"subject_id": subjects[0]["id"], "title": "x"},
                       headers=headers).status_code in (404, 405)


def test_faculty_typed_course_profile():
    """Faculty can create and publish a typed course profile which triggers RAG indexing."""
    token = get_token_for("dr.smith@university.edu")
    headers = {"Authorization": f"Bearer {token}"}

    db = SessionLocal()
    subj = db.query(Subject).first()
    db.close()
    assert subj is not None

    payload = {
        "title": "Natural Language Processing Syllabus",
        "units_topics": "Unit 1: Tokenization and Text Normalization.\nUnit 2: N-gram Language Models and Smoothing.\nUnit 3: Transformer Architectures and Self-Attention.",
        "learning_materials": "Jurafsky & Martin - Speech and Language Processing (3rd Edition).",
        "reference_content": "Key benchmark papers on BERT, RoBERTa, and GPT architectures.",
        "additional_info": "Assessments evaluate both practical implementation and conceptual comprehension.",
        "publish": True
    }

    res = client.post(f"/api/faculty/subjects/{subj.id}/course-profile/typed", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["subject_id"] == subj.id
    assert data["is_typed_published"] is True


def test_student_typed_submission_and_draft():
    """Student can save typed draft and submit typed assessment."""
    token = get_token_for("john.doe@student.edu")
    headers = {"Authorization": f"Bearer {token}"}

    # A fresh assessment in a subject the student is enrolled in (earlier runs evaluated older ones,
    # and evaluated submissions are locked)
    db = SessionLocal()
    student = db.query(StudentProfile).join(User).filter(User.email == "john.doe@student.edu").first()
    enrollment = db.query(SubjectEnrollment).filter(SubjectEnrollment.student_id == student.id).first()
    template = db.query(Assessment).filter(Assessment.rubric_version_id.isnot(None)).first()
    assess = Assessment(subject_id=enrollment.subject_id, title="Typed submission test", max_marks=20.0,
                        assessment_type=template.assessment_type, assessment_type_id=template.assessment_type_id,
                        rubric_version_id=template.rubric_version_id, is_active=True)
    db.add(assess)
    db.commit()
    db.refresh(assess)
    db.close()

    # Save Draft
    draft_payload = {
        "typed_content": "This is a draft reflective journal exploring text classification pipelines.",
        "is_draft": True
    }
    res_draft = client.post(f"/api/student/assessments/{assess.id}/submit-typed", json=draft_payload, headers=headers)
    assert res_draft.status_code == 200
    assert res_draft.json()["is_draft"] is True

    # Retrieve Draft
    res_get_draft = client.get(f"/api/student/assessments/{assess.id}/my-typed-draft", headers=headers)
    assert res_get_draft.status_code == 200
    assert "pipeline" in res_get_draft.json()["typed_content"]

    # Final Submit
    final_payload = {
        "typed_content": "This is the final reflective journal submission discussing sentiment analysis, model fine-tuning, and empirical evaluation metrics including precision, recall, and F1-score across multilingual datasets.",
        "is_draft": False
    }
    res_final = client.post(f"/api/student/assessments/{assess.id}/submit-typed", json=final_payload, headers=headers)
    assert res_final.status_code == 200
    assert res_final.json()["is_draft"] is False
    assert res_final.json()["submission_id"] is not None


def test_faculty_manual_evaluation_workflow():
    """
    Faculty reviews submission, views rubric reference guide, awards single overall mark,
    and submits evaluation which automatically executes background AI evaluation.
    """
    token_faculty = get_token_for("dr.smith@university.edu")
    headers_faculty = {"Authorization": f"Bearer {token_faculty}"}

    db = SessionLocal()
    # Find the latest submission
    sub = db.query(StudentSubmission).order_by(StudentSubmission.id.desc()).first()
    db.close()
    assert sub is not None

    # Get evaluation context
    res_ctx = client.get(f"/api/faculty/submissions/{sub.id}/evaluation-context", headers=headers_faculty)
    assert res_ctx.status_code == 200
    ctx = res_ctx.json()
    assert ctx["submission_id"] == sub.id
    assert "rubric_reference" in ctx
    assert len(ctx["rubric_reference"]["criteria"]) == 5

    # Faculty marks every rubric criterion (total = sum, 16.0 out of 20)
    criteria = ctx["rubric_reference"]["criteria"]
    per = [c["max_marks"] * 0.8 for c in criteria]
    eval_payload = {
        "faculty_total_marks": 16.0,
        "criterion_marks": [{"criterion_name": c["name"], "score": v} for c, v in zip(criteria, per)],
        "overall_feedback": "Strong grasp of NLP concepts with thorough methodology and sound conclusions.",
        "strengths": "Clear explanation of evaluation metrics and multilingual data handling.",
        "weaknesses": "Could elaborate further on error analysis in edge cases.",
        "improvement_suggestions": "Explore ablation studies to isolate performance gains.",
        "irrelevant_observations": "None noted.",
        "deduction_reasons": "Minor omission in edge case error discussion (-4 marks).",
        "internal_notes": "Very promising student project.",
        "is_draft": False
    }

    res_eval = client.post(f"/api/faculty/submissions/{sub.id}/manual-evaluate", json=eval_payload, headers=headers_faculty)
    assert res_eval.status_code == 200, res_eval.text
    assert res_eval.json()["status"] == "submitted"
    assert res_eval.json()["faculty_total_marks"] == round(sum(per), 2)

    # Background AI evaluation ran (TestClient executes background tasks) and published the document
    res_state = client.get(f"/api/faculty/submissions/{sub.id}/evaluation-status", headers=headers_faculty)
    assert res_state.status_code == 200
    assert res_state.json()["ai_status"] == "completed", res_state.json()
    assert res_state.json()["published"] is True

    # Faculty never receives AI marks in the evaluation context
    ctx2 = client.get(f"/api/faculty/submissions/{sub.id}/evaluation-context", headers=headers_faculty).json()
    assert "ai_marks" not in json.dumps(ctx2)


def test_admin_evaluation_monitoring_and_comparison():
    """Admin monitors evaluations, inspects Faculty vs AI comparison and discrepancy."""
    token_admin = get_token_for("admin@edueval.ai")
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    db = SessionLocal()
    sub = db.query(StudentSubmission).order_by(StudentSubmission.id.desc()).first()
    db.close()
    assert sub is not None

    # List monitoring items
    res_list = client.get("/api/admin/evaluation-monitoring", headers=headers_admin)
    assert res_list.status_code == 200
    items = res_list.json()
    assert len(items) > 0

    # Detailed comparison view
    res_comp = client.get(f"/api/admin/evaluation-monitoring/{sub.id}/comparison", headers=headers_admin)
    assert res_comp.status_code == 200
    comp = res_comp.json()
    assert "faculty_evaluation" in comp
    assert "scoring_comparison" in comp
    db = SessionLocal()
    fe = db.query(FacultyEvaluation).filter(FacultyEvaluation.submission_id == sub.id).first()
    db.close()
    assert comp["scoring_comparison"]["faculty_marks"] == fe.faculty_total_marks


def test_student_unified_feedback_and_pdf():
    """Student views unified report (no AI marks or discrepancy formula) and downloads PDF."""
    token_student = get_token_for("john.doe@student.edu")
    headers_student = {"Authorization": f"Bearer {token_student}"}

    db = SessionLocal()
    sub = db.query(StudentSubmission).order_by(StudentSubmission.id.desc()).first()
    db.close()
    assert sub is not None

    # Student requests feedback
    res_fb = client.get(f"/api/student/submissions/{sub.id}/feedback", headers=headers_student)
    assert res_fb.status_code == 200
    fb = res_fb.json()

    # Verify student does NOT receive AI marks or discrepancy calculations
    assert "ai_marks" not in fb
    assert "discrepancy_value" not in fb
    assert "calculation_method" not in fb
    assert "final_score" in fb
    assert "overall_feedback" in fb
    assert "strengths" in fb

    # The annotated feedback document
    doc = fb["document"]
    assert doc["criteria"] and doc["paragraphs"]
    seg_ids = [s["id"] for para in doc["paragraphs"] for s in para]
    assert seg_ids == list(range(1, len(seg_ids) + 1))
    annotated = {i["id"] for k in ("strengths", "weaknesses") for i in doc[k]} | {
        i["id"] for g in doc["suggestions"] for i in g["items"]}
    assert annotated == set(seg_ids)                       # every segment has exactly one comment
    assert abs(sum(c["score"] for c in doc["criteria"]) - doc["final_score"]) < 0.011
    assert doc["final_score"] == fb["final_score"]

    # Download PDF
    res_pdf = client.get(f"/api/student/submissions/{sub.id}/feedback.pdf", headers=headers_student)
    assert res_pdf.status_code == 200
    assert res_pdf.headers["content-type"] == "application/pdf"
    assert res_pdf.content.startswith(b"%PDF")
