"""
AI evaluation engine (OpenAI-compatible API — OpenAI or OpenRouter).

Flow for one submission (runs in the background after the faculty submits their marks):

1. Build the context the AI is grounded on: assessment brief, linked course unit, answer key /
   model answer, the faculty course profile and retrieved course-document passages, and the
   RTLP rubric linked to the assessment (scaled to the assessment's maximum marks).
2. Split the submission into numbered segments (deterministic, see ``segmenter``).
3. Ask the model for an INDEPENDENT rubric evaluation — the faculty marks are never shown to
   the model — with per-criterion marks, an overall feedback paragraph, and one annotation per
   segment (strength / weakness / suggestion, linked to a rubric criterion).
4. Validate everything in Python: criterion marks clamped to their maxima, the total is the sum
   of the criteria, annotations limited to real segment ids, missing segments re-requested once.
5. Final mark = average of faculty and AI marks (``scoring``), per-criterion marks averaged too.
6. Build and store the student feedback document payload, then publish it.

The API key is never hardcoded — it is read from Backend/.env by Settings.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, field_validator

from app.core.config import get_settings

logger = logging.getLogger(__name__)

ANNOTATION_TYPES = ("strength", "weakness", "suggestion")
SUGGESTION_CATEGORIES = ("Content", "Analysis", "Evidence", "Structure", "Style", "Language", "Accuracy", "Referencing")


# ─── Structured response models ──────────────────────────────────────────────

def _first_number(v: Any, default: Optional[float] = None) -> Optional[float]:
    """3 / '3' / '3.5/4' / '[12]' -> number; anything unparseable -> default."""
    if isinstance(v, bool):
        return default
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"-?\d+(?:\.\d+)?", str(v or ""))
    return float(m.group()) if m else default


class CriterionScoreAI(BaseModel):
    criterion_index: Optional[int] = None
    criterion_name: str = ""
    score: float = 0.0
    level: Optional[str] = None
    justification: str = ""

    @field_validator("criterion_index", mode="before")
    @classmethod
    def _idx(cls, v):
        n = _first_number(v)
        return int(n) if n is not None else None

    @field_validator("score", mode="before")
    @classmethod
    def _score(cls, v):
        return _first_number(v, 0.0)

    @field_validator("criterion_name", "level", "justification", mode="before")
    @classmethod
    def _str(cls, v):
        return None if v is None else str(v)


class AnnotationAI(BaseModel):
    segment_id: int
    criterion_index: int = 1
    type: str = "strength"
    category: Optional[str] = None
    comment: str = ""

    @field_validator("segment_id", mode="before")
    @classmethod
    def _seg(cls, v):
        n = _first_number(v)
        return int(n) if n is not None else -1   # -1 is discarded by validation

    @field_validator("criterion_index", mode="before")
    @classmethod
    def _crit(cls, v):
        n = _first_number(v)
        return int(n) if n is not None else 1

    @field_validator("type", "comment", mode="before")
    @classmethod
    def _s(cls, v):
        return "" if v is None else str(v)

    @field_validator("category", mode="before")
    @classmethod
    def _cat(cls, v):
        return None if v in (None, "") else str(v)


class IrrelevantObservationAI(BaseModel):
    excerpt: str
    section_or_page: Optional[str] = "submission"
    why_unrelated: str = ""
    relevant_criterion: str = ""
    score_impact: str = "none"


class EvidenceItem(BaseModel):
    text: str
    source: str = "student_submission"
    note: str = ""


def _as_list(v: Any) -> List[Any]:
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return list(v)
    return [v]


def _to_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return " — ".join(str(x) for x in v.values() if x not in (None, ""))
    if isinstance(v, (list, tuple)):
        return "; ".join(_to_text(x) for x in v)
    return str(v)


class AIEvaluationResponse(BaseModel):
    """The model's JSON, parsed leniently: models sometimes return a string where an object is
    expected (or vice versa), and one malformed item must not discard the whole evaluation."""
    subject_relevant: bool = True
    relevance_explanation: str = ""
    criterion_scores: List[CriterionScoreAI] = Field(default_factory=list)
    overall_feedback: str = ""
    annotations: List[AnnotationAI] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    missing_concepts: List[str] = Field(default_factory=list)
    improvement_suggestions: List[str] = Field(default_factory=list)
    supporting_evidence: List[EvidenceItem] = Field(default_factory=list)
    irrelevant_content_observations: List[IrrelevantObservationAI] = Field(default_factory=list)

    @field_validator("subject_relevant", mode="before")
    @classmethod
    def _bool(cls, v):
        if isinstance(v, str):
            return v.strip().lower() not in ("false", "no", "0", "")
        return True if v is None else v

    @field_validator("relevance_explanation", "overall_feedback", mode="before")
    @classmethod
    def _text(cls, v):
        return _to_text(v)

    @field_validator("strengths", "weaknesses", "missing_concepts", "improvement_suggestions", mode="before")
    @classmethod
    def _text_list(cls, v):
        return [t for t in (_to_text(x).strip() for x in _as_list(v)) if t]

    @field_validator("irrelevant_content_observations", mode="before")
    @classmethod
    def _observations(cls, v):
        out = []
        for x in _as_list(v):
            if isinstance(x, str) and x.strip():
                out.append({"excerpt": x.strip()})
            elif isinstance(x, dict):
                d = {k: _to_text(val) for k, val in x.items() if k in IrrelevantObservationAI.model_fields}
                d.setdefault("excerpt", _to_text(x.get("text") or x.get("quote") or ""))
                if d["excerpt"] or d.get("why_unrelated"):
                    out.append(d)
        return out

    @field_validator("supporting_evidence", mode="before")
    @classmethod
    def _evidence(cls, v):
        out = []
        for x in _as_list(v):
            if isinstance(x, str) and x.strip():
                out.append({"text": x.strip()})
            elif isinstance(x, dict) and _to_text(x.get("text") or x.get("quote")):
                out.append({"text": _to_text(x.get("text") or x.get("quote")),
                            "source": _to_text(x.get("source")) or "student_submission",
                            "note": _to_text(x.get("note"))})
        return out

    @field_validator("criterion_scores", "annotations", mode="before")
    @classmethod
    def _objects_only(cls, v):
        return [x for x in _as_list(v) if isinstance(x, (dict, BaseModel))]


# ─── Model client ─────────────────────────────────────────────────────────────

def _get_openai_client():
    """OpenAI client for OpenAI or OpenRouter (keys starting with sk-or- use OpenRouter)."""
    cfg = get_settings()
    if not cfg.openai_configured:
        raise ValueError(
            "API key is not configured. Open Backend/.env and set OPENAI_API_KEY=<your_key>. "
            "Never hardcode the key or commit it to version control."
        )
    from openai import OpenAI

    base_url = cfg.openai_base_url
    if not base_url and cfg.openai_api_key.startswith("sk-or-"):
        base_url = "https://openrouter.ai/api/v1"
    kwargs: Dict[str, Any] = {"api_key": cfg.openai_api_key, "timeout": 180.0, "max_retries": 2}
    if base_url:
        kwargs["base_url"] = base_url
        kwargs["default_headers"] = {"X-Title": "EduEval AI"}
    return OpenAI(**kwargs)


def _model_name() -> str:
    cfg = get_settings()
    model = cfg.openai_model or "gpt-4o-mini"
    is_openrouter = cfg.openai_api_key.startswith("sk-or-") or "openrouter" in (cfg.openai_base_url or "")
    if is_openrouter and "/" not in model:
        model = f"openai/{model}"
    return model


def _chat_json(system: str, user: str, max_tokens: int) -> Tuple[Dict[str, Any], int]:
    """Call the model and parse a JSON object (one retry on malformed JSON)."""
    client = _get_openai_client()
    model = _model_name()
    last_err: Optional[Exception] = None
    tokens = 0
    for attempt in range(2):
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.2,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        tokens += response.usage.total_tokens if response.usage else 0
        raw = (response.choices[0].message.content or "").strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
        try:
            return json.loads(raw), tokens
        except json.JSONDecodeError as exc:
            last_err = exc
            logger.warning("Model returned invalid JSON (attempt %s): %s", attempt + 1, raw[:300])
    raise ValueError(f"AI returned an invalid response format: {last_err}")


# ─── Prompt ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are a rigorous, fair and encouraging academic examiner at a university that follows the "
    "Reflective Teaching Learning Policy (RTLP). You evaluate one student submission against the "
    "given rubric, grounded ONLY in the course profile, course references and assessment brief provided. "
    "You write feedback addressed to the student in the second person ('you', 'your'), specific to their "
    "own words. You never invent quotations, facts or references. Respond with strictly valid JSON only."
)


def _rubric_block(criteria: List[Dict]) -> str:
    lines = []
    for i, c in enumerate(criteria, start=1):
        lines.append(f"Criterion {i} [{c['label']}] — {c['name']} (maximum {c['max_marks']:g} marks)")
        for lvl in sorted(c.get("levels") or [], key=lambda l: l.get("level", 0), reverse=True):
            band = ""
            if lvl.get("min_marks") is not None and lvl.get("max_marks") is not None:
                lo, hi = float(lvl["min_marks"]), float(lvl["max_marks"])
                band = f" [{lo:g}–{hi:g} marks]" if abs(lo - hi) > 1e-9 else f" [{hi:g} marks]"
            lines.append(f"    • {lvl.get('name')}{band}: {lvl.get('description')}")
        if not c.get("levels") and c.get("description"):
            lines.append(f"    • {c['description']}")
    return "\n".join(lines)


def build_prompt(*, subject_name: str, assessment, rubric: Dict, context: Dict, numbered_text: str,
                 segment_count: int) -> str:
    criteria = rubric["criteria"]
    mode = rubric["evaluation_mode"]
    refs = "\n\n".join(f"[Reference {i} — {r['source']}]\n{r['text'][:1200]}"
                       for i, r in enumerate(context.get("references", [])[:6], start=1)) or "None retrieved."

    mode_rules = ""
    if mode == "answer_key":
        mode_rules = (
            "\nANSWER-KEY MODE: This is an objective quiz. Mark each response strictly against the ANSWER KEY. "
            "Annotate each answer as a strength (correct), weakness (incorrect — state the correct answer briefly) "
            "or suggestion (partially correct). The single criterion score is the total marks earned."
        )
    elif mode == "observation":
        mode_rules = (
            "\nOBSERVATION-TYPE ACTIVITY: This rubric is designed for a live activity. Evaluate only what the "
            "submitted artefact (notes, slides, transcript or report) evidences. Where a criterion cannot be "
            "evidenced from the document, award the mark the evidence supports and say what was not observable."
        )

    return f"""SUBJECT: {subject_name}
ASSESSMENT: {assessment.title}
ASSESSMENT TYPE (RTLP rubric): {rubric['type_name']}{f" — RTLP {rubric['rtlp_code']}" if rubric.get('rtlp_code') else ''}
MAXIMUM MARKS: {assessment.max_marks:g}
QUESTION / BRIEF: {assessment.description or 'Not provided'}
INSTRUCTIONS TO STUDENTS: {assessment.instructions or 'None'}
COURSE UNIT / MODULE ASSESSED: {assessment.course_unit or 'Not specified'}
{f"FOCUS UNIT FROM COURSE PROFILE:{chr(10)}{context['focus_unit']}" if context.get('focus_unit') else ''}
{f"ANSWER KEY / MODEL ANSWER (faculty only — never reveal verbatim):{chr(10)}{assessment.reference_answer}" if assessment.reference_answer else ''}

COURSE PROFILE (written/uploaded by faculty — the academic standard to evaluate against):
{context.get('course_profile') or 'Not provided.'}

COURSE REFERENCE PASSAGES (retrieved from the subject's course documents):
{refs}

RUBRIC (RTLP) — score every criterion using these level descriptors and mark bands:
{_rubric_block(criteria)}
{mode_rules}

STUDENT SUBMISSION — split into {segment_count} numbered segments [id]:
\"\"\"
{numbered_text}
\"\"\"

TASKS
1. Decide whether the submission addresses the assessment and subject (subject_relevant). If it is
   entirely unrelated, set false, explain why, and give 0 for every criterion.
2. For EVERY criterion (in order, criterion_index 1..{len(criteria)}): choose the level whose descriptor
   best matches the evidence, award a mark inside that level's band (decimals such as 2.5 allowed),
   and justify it in 1–2 sentences that reference specific segments, e.g. "(see 4, 11)".
3. overall_feedback: one paragraph of 70–120 words addressed to the student — overall quality, the
   most important strength, the most important limitation, and what would raise the mark.
4. annotations: exactly ONE annotation for EVERY segment id from 1 to {segment_count}, in order:
   - criterion_index: the rubric criterion (1..{len(criteria)}) the segment most relates to;
   - type: "strength" (what works), "weakness" (an error, gap or inaccuracy) or "suggestion"
     (good but improvable — give the concrete improvement);
   - category (suggestions only): one of {", ".join(SUGGESTION_CATEGORIES)};
   - comment: 8–30 words, specific to that segment; quote short phrases in single quotes. No generic praise.
   - Link each annotation to the criterion it genuinely evidences: comments about language, spelling,
     structure, organisation or presentation belong to the criterion covering writing/organisation/
     presentation; comments about ideas belong to understanding/analysis/application criteria. Use every
     criterion somewhere in the document when the text gives evidence for it.
   - Flag EVERY spelling, grammar or terminology error as a weakness and quote it with the correction,
     e.g. "'usefull' should be 'useful'". If the segment is otherwise strong, say so in the same comment.
5. strengths / weaknesses / improvement_suggestions: 3–5 short summary points each.
6. missing_concepts: key course-profile concepts the brief required but the student omitted.
7. irrelevant_content_observations: only genuinely off-topic passages, quoted exactly; else [].

Return JSON exactly in this shape:
{{
  "subject_relevant": true,
  "relevance_explanation": "...",
  "criterion_scores": [{{"criterion_index": 1, "criterion_name": "...", "level": "...", "score": 3.0, "justification": "..."}}],
  "overall_feedback": "...",
  "annotations": [{{"segment_id": 1, "criterion_index": 1, "type": "strength", "category": null, "comment": "..."}}],
  "strengths": ["..."],
  "weaknesses": ["..."],
  "improvement_suggestions": ["..."],
  "missing_concepts": ["..."],
  "supporting_evidence": [{{"text": "exact quote", "source": "student_submission", "note": "..."}}],
  "irrelevant_content_observations": []
}}"""


def _repair_prompt(base_prompt: str, missing: List[int], n_criteria: int) -> str:
    return (
        base_prompt.split("TASKS", 1)[0]
        + f"""TASK
Annotations are missing for these segment ids: {", ".join(map(str, missing))}.
Return ONLY {{"annotations": [...]}} with exactly one annotation for each listed id, using the same rules:
criterion_index 1..{n_criteria}; type strength|weakness|suggestion; category (suggestions only) one of
{", ".join(SUGGESTION_CATEGORIES)}; comment 8–30 words specific to that segment."""
    )


# ─── Validation ───────────────────────────────────────────────────────────────

def _validate_scores(result: AIEvaluationResponse, criteria: List[Dict]) -> List[Dict]:
    by_index = {cs.criterion_index: cs for cs in result.criterion_scores if cs.criterion_index}
    by_name = {cs.criterion_name.strip().lower(): cs for cs in result.criterion_scores if cs.criterion_name}
    validated = []
    for i, c in enumerate(criteria, start=1):
        cs = by_index.get(i) or by_name.get(c["name"].strip().lower())
        cmax = float(c["max_marks"])
        if cs is None:
            # fall back to positional match before giving up
            cs = result.criterion_scores[i - 1] if len(result.criterion_scores) >= i else None
        score = 0.0 if cs is None else max(0.0, min(cmax, float(cs.score)))
        if not result.subject_relevant:
            score = 0.0
        validated.append({
            "criterion_name": c["name"],
            "label": c["label"],
            "max_marks": cmax,
            "score": round(score * 2) / 2 if cmax >= 4 else round(score, 2),  # half-mark precision
            "level": (cs.level if cs else None),
            "justification": (cs.justification if cs else "The model did not return a judgement for this criterion."),
        })
    return validated


def _validate_annotations(raw: List[AnnotationAI], segment_ids: set, n_criteria: int) -> Dict[int, Dict]:
    out: Dict[int, Dict] = {}
    for a in raw:
        if a.segment_id not in segment_ids or a.segment_id in out:
            continue
        kind = (a.type or "").strip().lower()
        kind = kind if kind in ANNOTATION_TYPES else ("weakness" if "weak" in kind else "suggestion" if "sugg" in kind else "strength")
        cat = None
        if kind == "suggestion":
            cat = next((c for c in SUGGESTION_CATEGORIES if c.lower() == (a.category or "").strip().lower()), "Content")
        comment = re.sub(r"\s+", " ", a.comment or "").strip()
        if not comment:
            continue
        out[a.segment_id] = {
            "segment_id": a.segment_id,
            "criterion_index": min(max(int(a.criterion_index or 1), 1), n_criteria) - 1,  # 0-based
            "type": kind,
            "category": cat,
            "comment": comment,
        }
    return out


def evaluate(*, subject_name: str, assessment, rubric: Dict, context: Dict, segments: List[Dict]) -> Dict[str, Any]:
    """Run the AI evaluation and return validated results."""
    from app.services.ai.segmenter import numbered_for_prompt

    criteria = rubric["criteria"]
    if not criteria:
        raise ValueError("No rubric is linked to this assessment; the AI cannot evaluate without criteria.")
    numbered = numbered_for_prompt(segments)
    prompt = build_prompt(subject_name=subject_name, assessment=assessment, rubric=rubric,
                          context=context, numbered_text=numbered, segment_count=len(segments))
    max_tokens = min(14000, 2200 + 70 * len(segments))

    start = time.monotonic()
    data, tokens = _chat_json(SYSTEM_PROMPT, prompt, max_tokens)
    result = AIEvaluationResponse(**data)

    seg_ids = {s["id"] for s in segments}
    annotations = _validate_annotations(result.annotations, seg_ids, len(criteria))
    missing = sorted(seg_ids - set(annotations))
    if missing and len(missing) <= len(seg_ids):
        try:
            extra, t2 = _chat_json(SYSTEM_PROMPT, _repair_prompt(prompt, missing, len(criteria)),
                                   min(8000, 600 + 70 * len(missing)))
            tokens += t2
            more = [AnnotationAI(**a) for a in extra.get("annotations", []) if isinstance(a, dict) and "segment_id" in a]
            for sid, a in _validate_annotations(more, set(missing), len(criteria)).items():
                annotations[sid] = a
        except Exception as exc:
            logger.warning("Annotation repair pass failed: %s", exc)

    scores = _validate_scores(result, criteria)
    total = round(sum(s["score"] for s in scores), 2)
    total = max(0.0, min(float(assessment.max_marks), total))
    return {
        "result": result,
        "criterion_scores": scores,
        "total": total,
        "annotations": [annotations[k] for k in sorted(annotations)],
        "tokens": tokens,
        "duration": time.monotonic() - start,
        "model": _model_name(),
    }


# ─── Background job ───────────────────────────────────────────────────────────

def execute_ai_evaluation_job(submission_id: int, user_id: int, force_ai: bool = False) -> None:
    """Evaluate a submission after the faculty has submitted their marks, then publish the result.

    When a completed AI evaluation already exists (e.g. the faculty edited their marks), the stored
    AI result is reused and only the final marks and document are rebuilt. ``force_ai`` re-runs the
    model (used by the admin "retry" action).
    """
    from app.core.database import SessionLocal
    from app.models.models import (
        StudentSubmission, AIEvaluation, CriterionScore, SupportingEvidence, FacultyEvaluation,
        FinalEvaluation, SubmissionStatus, EvaluationStatus, ApprovedFeedback,
    )
    from app.services.ai.context import resolve_rubric, build_course_context
    from app.services.ai.segmenter import segment_submission
    from app.services.ai.scoring import calculate_final_score, combine_criterion_scores
    from app.services.report.feedback_document import build_feedback_document

    db = SessionLocal()
    try:
        submission = db.query(StudentSubmission).filter(StudentSubmission.id == submission_id).first()
        from app.services.assessments import submission_subject
        subject = submission_subject(db, submission) if submission and submission.assessment else None
        if not submission or not submission.assessment or not subject:
            logger.error("AI job: submission %s (or its assessment/subject) not found", submission_id)
            return
        assessment = submission.assessment

        faculty_eval = db.query(FacultyEvaluation).filter(FacultyEvaluation.submission_id == submission_id).first()
        if not faculty_eval or faculty_eval.is_draft:
            logger.warning("AI job: submission %s has no submitted faculty evaluation yet", submission_id)
            return

        ai_eval = db.query(AIEvaluation).filter(AIEvaluation.submission_id == submission_id).first()
        reuse = bool(
            not force_ai and ai_eval and ai_eval.ai_status == "completed" and ai_eval.segments_json
            and ai_eval.annotations_json is not None and ai_eval.ai_criterion_scores_json and ai_eval.ai_raw_response
        )
        if not ai_eval:
            ai_eval = AIEvaluation(submission_id=submission_id, evaluated_by_id=user_id,
                                   ai_status="processing", status=EvaluationStatus.pending)
            db.add(ai_eval)
        elif not reuse:
            ai_eval.ai_status, ai_eval.error_details = "processing", None
        db.commit()
        db.refresh(ai_eval)

        submission_text = submission.typed_content or submission.extracted_text or ""
        if not submission_text.strip():
            ai_eval.ai_status, ai_eval.error_details = "failed", "Submission content is empty; cannot evaluate."
            db.commit()
            return
        if not reuse and not get_settings().openai_configured:
            ai_eval.ai_status = "failed"
            ai_eval.error_details = ("AI API key not configured. Set OPENAI_API_KEY in Backend/.env, restart the "
                                     "server, then retry from the Admin portal (Evaluation Monitor).")
            db.commit()
            return

        rubric = resolve_rubric(db, assessment, submission)
        if reuse:
            segments = ai_eval.segments_json
            result = AIEvaluationResponse(**json.loads(ai_eval.ai_raw_response))
            out = {"result": result, "criterion_scores": ai_eval.ai_criterion_scores_json,
                   "total": float(ai_eval.ai_total_score or 0.0), "annotations": ai_eval.annotations_json,
                   "tokens": ai_eval.tokens_used or 0, "duration": ai_eval.evaluation_duration_seconds or 0.0,
                   "model": ai_eval.openai_model_used}
        else:
            context = build_course_context(db, assessment, subject, submission_text)
            segments = segment_submission(submission_text)
            out = evaluate(subject_name=subject.name, assessment=assessment, rubric=rubric,
                           context=context, segments=segments)
            result = out["result"]

        # ── store AI evaluation ──
        ai_eval.rubric_version_id = assessment.rubric_version_id or submission.rubric_version_id
        ai_eval.ai_total_score = out["total"]
        ai_eval.ai_feedback = result.relevance_explanation or result.overall_feedback
        ai_eval.ai_overall_feedback = result.overall_feedback
        ai_eval.ai_strengths = "\n".join(result.strengths)
        ai_eval.ai_weaknesses = "\n".join(result.weaknesses)
        ai_eval.ai_missing_concepts = "\n".join(result.missing_concepts)
        ai_eval.ai_improvement_suggestions = "\n".join(result.improvement_suggestions)
        ai_eval.ai_raw_response = json.dumps(result.model_dump())
        ai_eval.ai_criterion_scores_json = out["criterion_scores"]
        ai_eval.ai_irrelevant_observations_json = [o.model_dump() for o in result.irrelevant_content_observations]
        ai_eval.segments_json = segments
        ai_eval.annotations_json = out["annotations"]
        ai_eval.openai_model_used = out["model"]
        ai_eval.tokens_used = out["tokens"]
        ai_eval.evaluation_duration_seconds = round(out["duration"], 2)
        ai_eval.ai_status, ai_eval.status, ai_eval.error_details = "completed", EvaluationStatus.completed, None

        db.query(CriterionScore).filter(CriterionScore.evaluation_id == ai_eval.id).delete()
        for cs in out["criterion_scores"]:
            db.add(CriterionScore(evaluation_id=ai_eval.id, criterion_name=cs["criterion_name"],
                                  max_marks=cs["max_marks"], ai_score=cs["score"], justification=cs["justification"]))
        db.query(SupportingEvidence).filter(SupportingEvidence.evaluation_id == ai_eval.id).delete()
        for ev in result.supporting_evidence[:10]:
            db.add(SupportingEvidence(evaluation_id=ai_eval.id, evidence_text=ev.text, source=ev.source,
                                      relevance_note=ev.note))
        db.flush()

        # ── final mark = average of faculty and AI ──
        scoring = calculate_final_score(faculty_eval.faculty_total_marks, out["total"], assessment.max_marks,
                                        assessment.discrepancy_threshold or 0.20)
        final_criteria = combine_criterion_scores(out["criterion_scores"], faculty_eval.criterion_marks,
                                                  scoring["faculty_marks"], scoring["final_marks"])

        document = build_feedback_document(
            submission=submission, assessment=assessment, rubric=rubric, segments=segments,
            annotations=out["annotations"], final_criteria=final_criteria, final_total=scoring["final_marks"],
            ai_result=result, faculty_eval=faculty_eval, subject=subject,
        )

        final_eval = db.query(FinalEvaluation).filter(FinalEvaluation.submission_id == submission_id).first()
        if not final_eval:
            final_eval = FinalEvaluation(submission_id=submission_id, faculty_marks=scoring["faculty_marks"],
                                         calculation_method=scoring["calculation_method"],
                                         final_total_marks=scoring["final_marks"])
            db.add(final_eval)
        final_eval.faculty_evaluation_id = faculty_eval.id
        final_eval.ai_evaluation_id = ai_eval.id
        final_eval.faculty_marks = scoring["faculty_marks"]
        final_eval.ai_marks = scoring["ai_marks"]
        final_eval.discrepancy_value = scoring["discrepancy_value"]
        final_eval.discrepancy_threshold = scoring["discrepancy_threshold"]
        final_eval.calculation_method = scoring["calculation_method"]
        final_eval.final_total_marks = scoring["final_marks"]
        final_eval.final_criterion_scores = final_criteria
        final_eval.feedback_document = document
        final_eval.unified_overall_feedback = document["overall_feedback"]
        final_eval.unified_strengths = "\n".join(result.strengths)
        final_eval.unified_weaknesses = "\n".join(result.weaknesses)
        final_eval.unified_improvement_suggestions = "\n".join(result.improvement_suggestions)
        final_eval.unified_criterion_feedback = [
            {"criterion_name": c["criterion_name"], "description": c["justification"]} for c in out["criterion_scores"]
        ]
        final_eval.unified_irrelevant_observations = [o.model_dump() for o in result.irrelevant_content_observations]
        final_eval.unified_final_remarks = faculty_eval.overall_feedback or None
        final_eval.is_published = True
        from app.models.models import utcnow
        final_eval.published_at = utcnow()

        legacy = db.query(ApprovedFeedback).filter(ApprovedFeedback.evaluation_id == ai_eval.id).first()
        if not legacy:
            legacy = ApprovedFeedback(evaluation_id=ai_eval.id, final_score=scoring["final_marks"],
                                      final_feedback=document["overall_feedback"], is_published=True,
                                      approved_by_id=user_id)
            db.add(legacy)
        legacy.final_score, legacy.final_feedback, legacy.is_published = scoring["final_marks"], document["overall_feedback"], True

        submission.status = SubmissionStatus.evaluated
        db.commit()
        logger.info("AI evaluation done for submission %s | F=%s AI=%s Final=%s | %s segments, %s annotations",
                    submission_id, scoring["faculty_marks"], scoring["ai_marks"], scoring["final_marks"],
                    len(segments), len(out["annotations"]))
    except Exception as exc:
        db.rollback()
        logger.error("AI evaluation failed for submission %s: %s", submission_id, exc, exc_info=True)
        try:
            ai_eval = db.query(AIEvaluation).filter(AIEvaluation.submission_id == submission_id).first()
            if ai_eval:
                ai_eval.ai_status, ai_eval.error_details = "failed", str(exc)[:2000]
                db.commit()
        except Exception:
            pass
    finally:
        db.close()
