"""
Custom Python Rubric Scoring Engine
Validates criterion scores from AI and enforces marking constraints.
"""
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class RubricScoringError(Exception):
    pass


class CriterionResult:
    def __init__(self, name: str, max_marks: float, ai_score: float, justification: str = ""):
        self.name = name
        self.max_marks = max_marks
        self.ai_score = ai_score
        self.clamped_score = min(max(ai_score, 0.0), max_marks)
        self.justification = justification
        self.was_clamped = abs(ai_score - self.clamped_score) > 0.001

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "max_marks": self.max_marks,
            "ai_score": self.ai_score,
            "validated_score": self.clamped_score,
            "justification": self.justification,
            "was_clamped": self.was_clamped,
        }


class RubricScorer:
    """
    Validates AI criterion scores against rubric constraints.
    Supported max marks: 10, 20, 25, 50, 100, or any custom value.
    """

    SUPPORTED_MAX_MARKS = {10, 20, 25, 50, 100}

    def __init__(self, total_max_marks: float, criteria: List[Dict]):
        """
        criteria: list of {name, max_marks} dicts from the rubric.
        """
        self.total_max_marks = total_max_marks
        self.criteria = criteria
        self._validate_rubric()

    def _validate_rubric(self):
        """Ensure rubric criterion marks sum to total."""
        if not self.criteria:
            raise RubricScoringError("Rubric has no criteria defined")

        criteria_sum = sum(c["max_marks"] for c in self.criteria)
        if abs(criteria_sum - self.total_max_marks) > 0.5:
            raise RubricScoringError(
                f"Rubric criteria sum ({criteria_sum}) does not match "
                f"total max marks ({self.total_max_marks})"
            )

    def validate_and_score(self, ai_scores: Dict[str, float]) -> Tuple[List[CriterionResult], float, List[str]]:
        """
        Validate AI-provided criterion scores.

        ai_scores: {criterion_name: score}

        Returns:
            (criterion_results, total_validated_score, warnings)
        """
        warnings = []
        results = []

        for criterion in self.criteria:
            cname = criterion["name"]
            max_m = criterion["max_marks"]

            # Find matching AI score (case-insensitive)
            ai_score = None
            for key, val in ai_scores.items():
                if key.lower().strip() == cname.lower().strip():
                    ai_score = val
                    break

            if ai_score is None:
                warnings.append(f"AI did not provide score for criterion: '{cname}'. Defaulting to 0.")
                ai_score = 0.0

            if not isinstance(ai_score, (int, float)):
                warnings.append(f"Invalid score type for '{cname}': {type(ai_score)}. Defaulting to 0.")
                ai_score = 0.0

            result = CriterionResult(
                name=cname,
                max_marks=max_m,
                ai_score=float(ai_score),
                justification=criterion.get("description", ""),
            )

            if result.was_clamped:
                warnings.append(
                    f"Score for '{cname}' was clamped from {ai_score:.1f} to {result.clamped_score:.1f} "
                    f"(max: {max_m})"
                )

            results.append(result)

        total = sum(r.clamped_score for r in results)
        # Final clamp at total max
        if total > self.total_max_marks:
            warnings.append(
                f"Total score {total:.1f} exceeded max {self.total_max_marks}. Clamped to max."
            )
            total = self.total_max_marks

        return results, round(total, 2), warnings

    @staticmethod
    def build_default_rubric(max_marks: float) -> List[Dict]:
        """
        Build a sensible default rubric when faculty hasn't defined one.
        Used as fallback — faculty is warned.
        """
        proportions = [
            ("Conceptual Understanding", 0.30),
            ("Technical Knowledge", 0.25),
            ("Content Relevance", 0.20),
            ("Explanation Quality", 0.15),
            ("Examples & Evidence", 0.10),
        ]
        criteria = []
        allocated = 0.0
        for i, (name, proportion) in enumerate(proportions):
            if i == len(proportions) - 1:
                mark = round(max_marks - allocated, 2)
            else:
                mark = round(max_marks * proportion, 2)
            allocated += mark
            criteria.append({"name": name, "max_marks": mark, "description": ""})
        return criteria

