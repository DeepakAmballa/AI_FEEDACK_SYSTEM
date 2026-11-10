"""
OpenAI AI Evaluation Engine
Uses the official OpenAI Python SDK with environment-based configuration.
API key is NEVER hardcoded — loaded from Backend/.env by Settings.
"""
import json
import logging
import time
from typing import List, Dict, Optional, Any

from pydantic import BaseModel, Field

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ─── Pydantic Models for structured OpenAI response ──────────────────────────

class CriterionScoreAI(BaseModel):
    criterion_name: str
    score: float
    justification: str


class EvidenceItem(BaseModel):
    text: str
    source: str = "student_submission"
    note: str = ""


class LineFeedback(BaseModel):
    line_number: int
    category: str
    comment: str
    suggested_revision: Optional[str] = None


class AIEvaluationResponse(BaseModel):
    subject_relevant: bool = True
    relevance_explanation: str = ""
    criterion_scores: List[CriterionScoreAI]
    total_estimated_score: float
    strengths: List[str]
    weaknesses: List[str]
    missing_concepts: List[str]
    improvement_suggestions: List[str]
    overall_feedback: str
    supporting_evidence: List[EvidenceItem]
    conceptual_understanding_summary: str
    style_feedback: List[str] = []
    language_errors: List[str] = []
    line_feedback: List[LineFeedback] = []
    comparative_analysis_feedback: str = ""
    compared_elements: List[str] = []


class EvaluationInput(BaseModel):
    subject_name: str
    assessment_title: str
    assessment_type: str
    assessment_description: Optional[str] = None
    max_marks: float
    student_submission: str
    course_references: List[str] = []
    learning_objectives: Optional[str] = None
    rubric_criteria: List[Dict] = []  # [{name, max_marks, description}]
    student_name: Optional[str] = None


# ─── AI Engine ────────────────────────────────────────────────────────────────

def _get_openai_client():
    """Get OpenAI client — supports both official OpenAI and OpenRouter."""
    cfg = get_settings()
    if not cfg.openai_configured:
        raise ValueError(
            "API key is not configured. "
            "Please open Backend/.env and set OPENAI_API_KEY=<your_key>. "
            "Never hardcode the key or commit it to version control."
        )
    from openai import OpenAI

    base_url = cfg.openai_base_url
    # Auto-detect OpenRouter keys (start with sk-or-)
    if not base_url and cfg.openai_api_key.startswith("sk-or-"):
        base_url = "https://openrouter.ai/api/v1"

    kwargs = {"api_key": cfg.openai_api_key}
    if base_url:
        kwargs["base_url"] = base_url
        kwargs["default_headers"] = {
            "HTTP-Referer": "http://localhost:5173",
            "X-Title": "EduEval AI",
        }
    return OpenAI(**kwargs)


def build_evaluation_prompt(inp: EvaluationInput) -> str:
    """Build the structured prompt for academic evaluation."""
    rubric_text = ""
    if inp.rubric_criteria:
        lines = []
        for c in inp.rubric_criteria:
            lines.append(f"  - {c['name']}: {c['max_marks']} marks")
            if c.get("description"):
                lines.append(f"    Description: {c['description']}")
        rubric_text = "MARKING RUBRIC:\n" + "\n".join(lines)
    else:
        rubric_text = "MARKING RUBRIC: Faculty has not defined specific criteria. Use standard academic criteria."

    references_text = ""
    if inp.course_references:
        ref_parts = []
        for i, ref in enumerate(inp.course_references[:6], 1):  # limit to top 6
            ref_parts.append(f"[Reference {i}]: {ref[:800]}")
        references_text = "\nCOURSE REFERENCE MATERIAL:\n" + "\n\n".join(ref_parts)
    else:
        references_text = "\nCOURSE REFERENCE MATERIAL: No course reference material was retrieved."

    objectives_text = ""
    if inp.learning_objectives:
        objectives_text = f"\nLEARNING OBJECTIVES:\n{inp.learning_objectives}"

    prompt = f"""You are an expert academic evaluator for the subject: {inp.subject_name}.

ASSESSMENT: {inp.assessment_title} ({inp.assessment_type})
MAXIMUM MARKS: {inp.max_marks}
QUESTION / BRIEF: {inp.assessment_description or "Not provided"}
{objectives_text}

{rubric_text}
{references_text}

STUDENT SUBMISSION:
{inp.student_submission[:3000]}

EVALUATION INSTRUCTIONS:
1. First decide whether the submission is materially related to the named subject, assessment, and course reference material.
2. Set subject_relevant to false when the submission is about a different subject or unrelated topic.
3. If subject_relevant is false, explain why in relevance_explanation, award zero or only minimal marks for genuinely relevant content, and clearly state this in overall_feedback and weaknesses.
4. Evaluate the student's ACTUAL UNDERSTANDING, not just keyword matching.
5. Provide criterion-wise scores that sum to no more than {inp.max_marks}, with a specific justification for every criterion.
6. Quote specific text from the submission as supporting evidence.
7. Identify concepts the student demonstrated well (strengths).
8. Identify gaps, errors, or missing concepts (weaknesses).
9. List important concepts that were absent from the submission.
10. Provide personalized, constructive improvement suggestions.
11. Compare the submission only against the supplied subject reference material.
12. If the assessment asks for comparison, explicitly state whether the submission compares the required works/topics and explain what is missing.
13. Review style, grammar, spelling, capitalization, syntax, terminology, and proofreading.
14. Use line numbers from the supplied submission when reporting line feedback. Do not invent line numbers.
15. Do NOT invent supporting evidence. Only quote what is actually present.
16. All scores must be between 0 and their criterion maximum.

REQUIRED JSON OUTPUT FORMAT:
{{
  "subject_relevant": true,
  "relevance_explanation": "...",
  "criterion_scores": [
    {{"criterion_name": "...", "score": 0.0, "justification": "..."}}
  ],
  "total_estimated_score": 0.0,
  "strengths": ["...", "..."],
  "weaknesses": ["...", "..."],
  "missing_concepts": ["...", "..."],
  "improvement_suggestions": ["...", "..."],
  "overall_feedback": "...",
  "supporting_evidence": [
    {{"text": "exact quote from submission", "source": "student_submission", "note": "demonstrates X"}}
  ],
  "conceptual_understanding_summary": "..."
  ,"style_feedback": ["..."],
  "language_errors": ["Line 2: ..."],
  "line_feedback": [
    {{"line_number": 2, "category": "style", "comment": "...", "suggested_revision": "..."}}
  ],
  "comparative_analysis_feedback": "...",
  "compared_elements": ["..."]
}}

Return ONLY valid JSON. No markdown. No extra text."""

    return prompt


def evaluate_submission(inp: EvaluationInput) -> tuple[AIEvaluationResponse, int, float]:
    """
    Call OpenAI API to evaluate a student submission.

    Returns:
        (AIEvaluationResponse, tokens_used, duration_seconds)

    Raises:
        ValueError: for config errors or invalid responses
        Exception: for API errors (caller should handle)
    """
    cfg = get_settings()
    client = _get_openai_client()
    model = cfg.openai_model or "gpt-4o-mini"
    is_openrouter = cfg.openai_api_key.startswith("sk-or-") or (
        bool(cfg.openai_base_url) and "openrouter" in (cfg.openai_base_url or "")
    )
    if is_openrouter and "/" not in model:
        model = f"openai/{model}"

    prompt = build_evaluation_prompt(inp)

    start = time.monotonic()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional academic evaluator. "
                        "Always respond with valid JSON only. "
                        "Never fabricate quotes or evidence."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        duration = time.monotonic() - start
        logger.error(f"OpenAI API error after {duration:.1f}s: {e}")
        raise

    duration = time.monotonic() - start
    tokens_used = response.usage.total_tokens if response.usage else 0
    raw_text = response.choices[0].message.content

    try:
        raw_dict = json.loads(raw_text)
        result = AIEvaluationResponse(**raw_dict)
    except Exception as e:
        logger.error(f"Failed to parse OpenAI response: {e}\nRaw: {raw_text[:500]}")
        raise ValueError(f"OpenAI returned an invalid response format: {str(e)}")

    logger.info(
        f"AI evaluation completed in {duration:.1f}s | "
        f"model={model} | tokens={tokens_used} | "
        f"score={result.total_estimated_score}/{inp.max_marks}"
    )

    return result, tokens_used, duration
