"""Admin creates assessments from RTLP rubrics, maps them to subjects; faculty and students see them."""
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.models import (Assessment, AssessmentSubject, FacultyProfile, StudentProfile, StudentSubmission,
                               Subject, SubjectEnrollment, SubjectFaculty, User)
from app.services.rubrics.library import library
from app.core.security import create_access_token


def get_token_for(email: str) -> str:
    db = SessionLocal()
    u = db.query(User).filter(User.email == email).first()
    db.close()
    return create_access_token({"sub": str(u.id), "role": u.role.value})

client = TestClient(app)


def _h(email):
    return {"Authorization": f"Bearer {get_token_for(email)}"}


def _setup_subjects():
    """Two subjects: dr.smith teaches and john.doe is enrolled in both."""
    db = SessionLocal()
    subjects = db.query(Subject).order_by(Subject.id).limit(2).all()
    fac = db.query(FacultyProfile).join(User).filter(User.email == "dr.smith@university.edu").first()
    stu = db.query(StudentProfile).join(User).filter(User.email == "john.doe@student.edu").first()
    for s in subjects:
        if not db.query(SubjectFaculty).filter_by(subject_id=s.id, faculty_id=fac.id).first():
            db.add(SubjectFaculty(subject_id=s.id, faculty_id=fac.id))
        if not db.query(SubjectEnrollment).filter_by(subject_id=s.id, student_id=stu.id).first():
            db.add(SubjectEnrollment(subject_id=s.id, student_id=stu.id))
    db.commit()
    ids = [s.id for s in subjects]
    db.close()
    return ids


def _payload(subject_ids, **extra):
    tpl = next(t for t in library() if t["code"] == "14.3.7")  # Reflective Essay, 5 x 8 = 40
    return {
        "title": "Reflective Essay — Week 6",
        "description": "Reflect on what you learned about synchronization this week.",
        "subject_ids": subject_ids,
        "template_code": tpl["code"],
        "rubric": [{"name": c["name"], "max_marks": c["max_marks"], "description": c["description"],
                    "levels": [{"name": l["name"], "description": l["description"],
                                "min_marks": l["min_marks"], "max_marks": l["max_marks"]} for l in c["levels"]]}
                   for c in tpl["criteria"]],
        **extra,
    }


def test_admin_assessment_lifecycle():
    sids = _setup_subjects()
    assert len(sids) == 2
    admin = _h("admin@edueval.ai")

    # Templates come from the RTLP library
    templates = client.get("/api/admin/rubric-templates", headers=admin).json()
    assert any(t["code"] == "14.3.7" for t in templates)

    # Create from the RTLP template, mapped to both subjects
    res = client.post("/api/admin/assessments", json=_payload(sids), headers=admin)
    assert res.status_code == 200, res.text
    a = res.json()
    assert a["max_marks"] == 40 and a["rubric_source"] == "RTLP 14.3.7"
    assert sorted(a["subject_ids"]) == sorted(sids)

    # Edited rubric is marked as such; criteria re-weighting changes the total
    edited = _payload(sids)
    edited["rubric"][0]["levels"][0]["description"] = "Exceptional conceptual depth"
    res = client.put(f"/api/admin/assessments/{a['id']}", json=edited, headers=admin)
    assert res.status_code == 200 and res.json()["rubric_source"] == "RTLP 14.3.7 (edited)"

    # Faculty of both subjects see it read-only; students see it with the rubric criteria
    for sid in sids:
        fac = client.get(f"/api/faculty/subjects/{sid}/assessments", headers=_h("dr.smith@university.edu")).json()
        item = next(x for x in fac if x["id"] == a["id"])
        assert len(item["criteria"]) == 5
        stu = client.get(f"/api/student/subjects/{sid}/assessments", headers=_h("john.doe@student.edu")).json()
        item = next(x for x in stu if x["id"] == a["id"])
        assert len(item["criteria"]) == 5 and "reference_answer" not in item

    # The student's Assessments tab lists the shared assessment once, not started
    mine = client.get("/api/student/assessments", headers=_h("john.doe@student.edu")).json()
    entries = [x for x in mine if x["id"] == a["id"]]
    assert len(entries) == 1 and entries[0]["state"] == "not_started" and entries[0]["can_submit"]

    # A draft is not a submission
    client.post(f"/api/student/assessments/{a['id']}/submit-typed?subject_id={sids[1]}",
                json={"typed_content": "Early draft.", "is_draft": True}, headers=_h("john.doe@student.edu"))
    entry = next(x for x in client.get("/api/student/assessments", headers=_h("john.doe@student.edu")).json() if x["id"] == a["id"])
    assert entry["state"] == "draft" and entry["submitted"] is False

    # Student submits through the second subject; the submission remembers it
    res = client.post(f"/api/student/assessments/{a['id']}/submit-typed?subject_id={sids[1]}",
                      json={"typed_content": "Semaphores prevent races. Deadlock needs four conditions.", "is_draft": False},
                      headers=_h("john.doe@student.edu"))
    assert res.status_code == 200, res.text
    db = SessionLocal()
    sub = db.query(StudentSubmission).filter(StudentSubmission.id == res.json()["submission_id"]).first()
    assert sub.subject_id == sids[1]
    db.close()

    entry = next(x for x in client.get("/api/student/assessments", headers=_h("john.doe@student.edu")).json() if x["id"] == a["id"])
    assert entry["state"] == "submitted" and entry["subject_id"] == sids[1]

    # Replacing the typed answer with a file makes the file the submission (not the stale typed text)
    res = client.post(f"/api/student/assessments/{a['id']}/submit", headers=_h("john.doe@student.edu"),
                      files={"file": ("answer.txt", b"Uploaded answer about deadlock prevention.", "text/plain")},
                      data={"subject_id": str(sids[1])})
    assert res.status_code == 200, res.text
    db = SessionLocal()
    sub = db.query(StudentSubmission).filter(StudentSubmission.id == sub.id).first()
    assert sub.submission_type == "upload" and sub.typed_content is None and sub.is_draft is False
    assert "Uploaded answer" in (sub.extracted_text or "")
    db.close()

    # That subject cannot be unmapped any more
    res = client.put(f"/api/admin/assessments/{a['id']}", json=_payload([sids[0]]), headers=admin)
    assert res.status_code == 400 and "cannot be unmapped" in res.json()["detail"]

    # Faculty evaluation context uses the admin rubric
    ctx = client.get(f"/api/faculty/submissions/{sub.id}/evaluation-context", headers=_h("dr.smith@university.edu")).json()
    assert ctx["rubric_reference"]["criteria"][0]["levels"][0]["description"] == "Exceptional conceptual depth"

    # Faculty marks it → the submission locks; the (fake) AI publishes feedback
    marks = [{"criterion_name": c["name"], "score": c["max_marks"] / 2} for c in ctx["rubric_reference"]["criteria"]]
    res = client.post(f"/api/faculty/submissions/{sub.id}/manual-evaluate", headers=_h("dr.smith@university.edu"),
                      json={"faculty_total_marks": 0, "criterion_marks": marks, "overall_feedback": "Fair attempt.", "is_draft": False})
    assert res.status_code == 200, res.text
    entry = next(x for x in client.get("/api/student/assessments", headers=_h("john.doe@student.edu")).json() if x["id"] == a["id"])
    assert entry["state"] == "feedback_ready" and entry["can_submit"] is False and entry["final_score"] is not None
    res = client.post(f"/api/student/assessments/{a['id']}/submit-typed?subject_id={sids[1]}",
                      json={"typed_content": "Changed after marking", "is_draft": False}, headers=_h("john.doe@student.edu"))
    assert res.status_code == 400

    # Deactivate hides it from students
    assert client.delete(f"/api/admin/assessments/{a['id']}", headers=admin).status_code == 200
    stu = client.get(f"/api/student/subjects/{sids[0]}/assessments", headers=_h("john.doe@student.edu")).json()
    assert all(x["id"] != a["id"] for x in stu)


def test_admin_assessment_validation_and_roles():
    sids = _setup_subjects()
    admin = _h("admin@edueval.ai")
    bad = _payload(sids)
    bad["rubric"][0]["levels"][0]["max_marks"] = 99           # band above criterion maximum
    assert client.post("/api/admin/assessments", json=bad, headers=admin).status_code == 400
    quiz = _payload(sids, evaluation_mode="answer_key")         # answer key required
    assert client.post("/api/admin/assessments", json=quiz, headers=admin).status_code == 400
    assert client.post("/api/admin/assessments", json=_payload([]), headers=admin).status_code == 422
    # Only admins can create assessments or read the admin list
    for email in ("dr.smith@university.edu", "john.doe@student.edu"):
        assert client.post("/api/admin/assessments", json=_payload(sids), headers=_h(email)).status_code == 403
