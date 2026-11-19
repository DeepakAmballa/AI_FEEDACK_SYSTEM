"""Evaluation context: everything the AI evaluator is grounded on.

* the assessment (question/brief, instructions, the course unit it covers, answer key/model answer)
* the subject's course profile written or uploaded by faculty (syllabus, objectives, outcomes,
  units & topics, reference content) — the unit linked to the assessment is given priority
* passages retrieved from the subject's indexed course documents (RAG)
* the RTLP rubric linked to the assessment, scaled to the assessment's maximum marks
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.services.rubrics.library import scale_criteria

logger = logging.getLogger(__name__)

# Criterion colours used on the annotated feedback document (same palette as the reference
# feedback document); each has a light tint used for the text highlight.
CRITERION_COLORS = ["#0184c7", "#9333ea", "#ec4899", "#16a34a", "#ea580c", "#0d9488", "#ca8a04", "#4f46e5"]
CRITERION_TINTS = {
    "#0184c7": "#e0f2fe", "#9333ea": "#f0e6ff", "#ec4899": "#fdf2f8", "#16a34a": "#f0fdf4",
    "#ea580c": "#fff7ed", "#0d9488": "#ccfbf1", "#ca8a04": "#fef9c3", "#4f46e5": "#e0e7ff",
}


def criterion_label(index: int) -> str:
    """0 -> 'A', 1 -> 'B', ... ."""
    return chr(ord("A") + index) if index < 26 else f"C{index + 1}"


def resolve_rubric(db, assessment, submission=None) -> Dict[str, Any]:
    """Return {criteria (scaled), evaluation_mode, type_name, rtlp_code, version}."""
    from app.models.models import RubricVersion, AssessmentType

    criteria: List[Dict] = []
    version = None
    rv_id = assessment.rubric_version_id or (submission.rubric_version_id if submission else None)
    if assessment.rubric_data:  # admin-authored rubric stored on the assessment
        criteria = assessment.rubric_data
    elif rv_id:
        rv = db.query(RubricVersion).filter(RubricVersion.id == rv_id).first()
        if rv and rv.criteria_data:
            criteria = rv.criteria_data
            version = rv.version
    if not criteria and assessment.rubric and assessment.rubric.criteria:
        criteria = [
            {"name": c.name, "max_marks": c.max_marks, "description": c.description or "", "levels": []}
            for c in sorted(assessment.rubric.criteria, key=lambda c: c.order_index or 0)
        ]

    atype = None
    if assessment.assessment_type_id:
        atype = db.query(AssessmentType).filter(AssessmentType.id == assessment.assessment_type_id).first()

    scaled = scale_criteria(criteria, assessment.max_marks)
    for i, c in enumerate(scaled):
        c["label"] = criterion_label(i)
        c["color"] = CRITERION_COLORS[i % len(CRITERION_COLORS)]
    rtlp_code = atype.rtlp_code if atype else None
    if assessment.rubric_source and assessment.rubric_source.startswith("RTLP "):
        rtlp_code = assessment.rubric_source[5:]
    return {
        "criteria": scaled,
        "evaluation_mode": assessment.evaluation_mode or (atype.evaluation_mode if atype and atype.evaluation_mode else "document"),
        "type_name": atype.name if atype else (assessment.assessment_type or "Assessment"),
        "rtlp_code": rtlp_code,
        "version": version,
    }


def _units_text(units: Any, focus: Optional[str]) -> tuple[str, str]:
    """Format units_topics JSON; return (focus_unit_text, all_units_text)."""
    if not units:
        return "", ""
    if isinstance(units, str):
        try:
            units = json.loads(units)
        except (TypeError, ValueError):
            return "", units
    lines, focus_lines = [], []
    for u in units if isinstance(units, list) else []:
        if not isinstance(u, dict):
            lines.append(str(u))
            continue
        name = u.get("unit_name") or u.get("name") or u.get("title") or ""
        num = u.get("unit_number") or u.get("number") or ""
        topics = u.get("topics") or u.get("topic_list") or []
        if isinstance(topics, list):
            topics = "; ".join(t if isinstance(t, str) else (t.get("name") or t.get("topic_name") or "") for t in topics)
        detail = u.get("description") or u.get("content") or ""
        line = f"Unit {num}: {name}".strip(": ") + (f" — Topics: {topics}" if topics else "") + (f"\n  {detail}" if detail else "")
        lines.append(line)
        if focus and focus.strip().lower() in f"unit {num} {name}".lower():
            focus_lines.append(line)
    return "\n".join(focus_lines), "\n".join(lines)


def build_course_context(db, assessment, subject, submission_text: str) -> Dict[str, Any]:
    from app.models.models import CourseProfile, CourseTopic

    profile = db.query(CourseProfile).filter(CourseProfile.subject_id == subject.id).first()
    sections: List[str] = []
    focus_unit = ""
    if profile:
        focus_unit, all_units = _units_text(profile.units_topics, assessment.course_unit)
        topics = db.query(CourseTopic).filter(CourseTopic.course_profile_id == profile.id).all()
        if topics:
            t_lines = [f"Unit {t.unit_number or ''} {t.unit_name or ''}: {t.topic_name}"
                       + (f" ({t.subtopics})" if t.subtopics else "") for t in topics]
            all_units = "\n".join(filter(None, [all_units, *t_lines]))
            if assessment.course_unit:
                f = [l for l in t_lines if assessment.course_unit.lower() in l.lower()]
                focus_unit = "\n".join(filter(None, [focus_unit, *f]))
        for label, value in [
            ("Course title", profile.title),
            ("Course description", profile.description),
            ("Syllabus", profile.syllabus),
            ("Learning objectives", profile.learning_objectives),
            ("Expected course outcomes", profile.expected_outcomes),
            ("Units and topics", all_units),
            ("Important concepts", profile.important_concepts),
            ("Definitions", profile.definitions),
            ("Reference content", profile.reference_content),
            ("Reference answers", profile.reference_answers),
            ("Learning materials", profile.learning_materials),
            ("Additional academic information", profile.additional_info),
        ]:
            if value and str(value).strip():
                sections.append(f"{label}:\n{str(value).strip()}")

    references: List[Dict[str, str]] = []
    try:
        from app.services.rag.pipeline import retrieve_for_subject
        query = " ".join(filter(None, [
            assessment.title, assessment.description, assessment.course_unit, focus_unit[:300], submission_text[:600],
        ]))
        for r in retrieve_for_subject(subject.id, query, top_k=6, faiss_dir=get_settings().faiss_dir) or []:
            references.append({"source": r.get("source") or r.get("source_name") or "Course document", "text": r["text"]})
    except Exception as exc:  # index missing / embeddings unavailable — evaluation still proceeds
        logger.warning("RAG retrieval unavailable for subject %s: %s", subject.id, exc)

    return {
        "course_profile": "\n\n".join(sections),
        "focus_unit": focus_unit,
        "references": references,
    }
