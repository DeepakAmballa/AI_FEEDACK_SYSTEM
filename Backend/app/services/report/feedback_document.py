"""The student feedback document payload.

One JSON structure drives both the student's web view and the downloadable PDF, so the two
always match. Layout (modelled on the reference essay-feedback document):

  page 1   Score header · student name · date · one row per rubric criterion (colour dot,
           label + name, achieved level, final mark)
  page 2+  The assessment question with [max marks], then the student's own text split into
           numbered segments, each highlighted in the colour of the criterion it relates to
  last     Overall feedback · Feedback: Strengths / Weaknesses (numbered by segment) ·
           Suggestions grouped by category
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.ai.scoring import performance_level

DOCUMENT_VERSION = 1


def _fmt(n: float) -> str:
    return f"{n:.2f}".rstrip("0").rstrip(".") if n is not None else "0"


def build_feedback_document(
    *,
    submission,
    assessment,
    rubric: Dict[str, Any],
    segments: List[Dict],
    annotations: List[Dict],
    final_criteria: List[Dict],
    final_total: float,
    ai_result,
    faculty_eval=None,
    subject=None,
) -> Dict[str, Any]:
    criteria_defs = rubric["criteria"]
    colors = [c["color"] for c in criteria_defs]

    criteria_rows = []
    for i, c in enumerate(criteria_defs):
        fc = final_criteria[i] if i < len(final_criteria) else {"final": 0.0}
        lvl = performance_level(float(fc["final"]), c) or {}
        criteria_rows.append({
            "index": i,
            "label": c["label"],
            "name": c["name"],
            "color": c["color"],
            "score": round(float(fc["final"]), 2),
            "score_display": _fmt(float(fc["final"])),
            "max_marks": float(c["max_marks"]),
            "max_display": _fmt(float(c["max_marks"])),
            "level": lvl.get("name"),
            "level_description": lvl.get("description"),
        })

    ann_by_seg = {a["segment_id"]: a for a in annotations}
    paragraphs: List[List[Dict]] = []
    current_par = None
    for s in segments:
        a = ann_by_seg.get(s["id"])
        item = {
            "id": s["id"],
            "text": s["text"],
            "criterion_index": a["criterion_index"] if a else None,
            "color": colors[a["criterion_index"]] if a else None,
            "type": a["type"] if a else None,
        }
        if s["paragraph"] != current_par:
            paragraphs.append([])
            current_par = s["paragraph"]
        paragraphs[-1].append(item)

    def items(kind: str) -> List[Dict]:
        return [
            {"id": a["segment_id"], "color": colors[a["criterion_index"]], "criterion_index": a["criterion_index"],
             "comment": a["comment"]}
            for a in annotations if a["type"] == kind
        ]

    suggestion_groups: Dict[str, List[Dict]] = {}
    for a in annotations:
        if a["type"] == "suggestion":
            suggestion_groups.setdefault(a.get("category") or "Content", []).append(
                {"id": a["segment_id"], "color": colors[a["criterion_index"]],
                 "criterion_index": a["criterion_index"], "comment": a["comment"]})

    student = submission.student
    published = getattr(submission, "updated_at", None) or submission.submitted_at
    faculty_comments = None
    if faculty_eval is not None:
        parts = [p for p in [faculty_eval.overall_feedback] if p and p.strip()]
        faculty_comments = "\n\n".join(parts) or None

    return {
        "version": DOCUMENT_VERSION,
        "brand": "EduEval AI",
        "student_name": student.user.full_name if student and student.user else "Student",
        "student_id": student.student_id if student else None,
        "date": published.isoformat() if published else None,
        "subject_name": (subject or assessment.subject).name if (subject or assessment.subject) else None,
        "assessment_title": assessment.title,
        "assessment_type": rubric.get("type_name"),
        "rtlp_code": rubric.get("rtlp_code"),
        "question": (assessment.description or assessment.title or "").strip(),
        "max_marks": float(assessment.max_marks),
        "max_display": _fmt(float(assessment.max_marks)),
        "final_score": round(float(final_total), 2),
        "score_display": _fmt(float(final_total)),
        "criteria": criteria_rows,
        "paragraphs": paragraphs,
        "overall_feedback": (ai_result.overall_feedback or "").strip(),
        "faculty_comments": faculty_comments,
        "strengths": items("strength"),
        "weaknesses": items("weakness"),
        "suggestions": [{"category": k, "items": v} for k, v in suggestion_groups.items()],
        "missing_concepts": list(ai_result.missing_concepts or []),
        "subject_relevant": bool(ai_result.subject_relevant),
        "relevance_explanation": ai_result.relevance_explanation if not ai_result.subject_relevant else None,
    }
