"""Authoritative scoring engine for EduEval AI.

Final mark policy (institutional requirement):
    The student's final mark is the AVERAGE of the faculty mark and the AI mark:

        Final = (F + A) / 2

    where F = faculty overall marks, A = validated AI overall marks, M = maximum marks.

The discrepancy D = |F - A| is still computed against a threshold T = ratio x M. It no
longer changes the mark; when D > T the evaluation is flagged ``is_discrepant`` so the
admin can review it in Evaluation Monitoring.

Per-criterion marks are combined the same way, so the criteria shown on the student's
feedback document always add up exactly to the final mark.
"""
from typing import Any, Dict, List, Optional

CALCULATION_METHOD = "averaged"


def _clamp(v: float, hi: float) -> float:
    return max(0.0, min(float(hi), float(v)))


def calculate_final_score(
    faculty_marks: float,
    ai_marks: float,
    max_marks: float,
    threshold_ratio: float = 0.20,
) -> Dict[str, Any]:
    """Combine faculty and AI marks into the final mark (always the average)."""
    max_marks = float(max_marks)
    f = _clamp(faculty_marks, max_marks)
    a = _clamp(ai_marks, max_marks)

    discrepancy = round(abs(f - a), 4)
    threshold = round(float(threshold_ratio) * max_marks, 4)
    final = _clamp(round((f + a) / 2.0, 2), max_marks)

    return {
        "faculty_marks": round(f, 2),
        "ai_marks": round(a, 2),
        "max_marks": round(max_marks, 2),
        "discrepancy_value": discrepancy,
        "discrepancy_threshold": threshold,
        "is_discrepant": discrepancy > threshold,
        "calculation_method": CALCULATION_METHOD,
        "final_marks": final,
        "final_total_marks": final,
    }


def combine_criterion_scores(
    ai_scores: List[Dict[str, Any]],
    faculty_scores: Optional[List[Dict[str, Any]]],
    faculty_total: float,
    final_total: float,
) -> List[Dict[str, Any]]:
    """Average faculty and AI marks per criterion.

    ``ai_scores``: [{criterion_name, max_marks, score}] (validated AI marks).
    ``faculty_scores``: [{criterion_name, score}] when faculty marked per criterion. When the
    faculty only gave a holistic total, it is distributed across criteria in proportion to the
    AI marks (or evenly when the AI awarded nothing), which keeps the faculty total intact.
    The result is adjusted so the criteria sum exactly to ``final_total``.
    """
    if not ai_scores:
        return []
    fac_by_name = {
        (fs.get("criterion_name") or "").strip().lower(): fs for fs in (faculty_scores or [])
    }
    ai_sum = sum(float(c["score"]) for c in ai_scores)
    n = len(ai_scores)

    rows = []
    for c in ai_scores:
        cmax = float(c["max_marks"])
        ai_v = _clamp(c["score"], cmax)
        fac = fac_by_name.get(c["criterion_name"].strip().lower())
        if fac is not None and fac.get("score") is not None:
            fac_v = _clamp(fac["score"], cmax)
            estimated = False
        else:
            share = (ai_v / ai_sum) if ai_sum > 0 else (1.0 / n)
            fac_v = _clamp(float(faculty_total) * share, cmax)
            estimated = True
        rows.append({
            "criterion_name": c["criterion_name"],
            "max_marks": cmax,
            "faculty": round(fac_v, 2),
            "ai": round(ai_v, 2),
            "final": round((fac_v + ai_v) / 2.0, 2),
            "faculty_estimated": estimated,
        })

    # Make the criteria add up exactly to the final total (rounding drift).
    drift = round(float(final_total) - sum(r["final"] for r in rows), 2)
    if abs(drift) >= 0.01:
        order = sorted(range(n), key=lambda i: rows[i]["max_marks"] - rows[i]["final"], reverse=drift > 0)
        for i in order:
            if drift > 0:
                step = min(drift, rows[i]["max_marks"] - rows[i]["final"])
            else:
                step = -min(-drift, rows[i]["final"])
            rows[i]["final"] = round(rows[i]["final"] + step, 2)
            drift = round(drift - step, 2)
            if abs(drift) < 0.01:
                break
    return rows


def performance_level(score: float, criterion: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return the rubric level whose mark band contains ``score`` (scaled criteria)."""
    levels = criterion.get("levels") or []
    if not levels:
        return None
    cmax = float(criterion.get("max_marks") or 0) or 1.0
    best = None
    for lvl in sorted(levels, key=lambda l: l.get("level", 0), reverse=True):
        lo = lvl.get("min_marks")
        if lo is None:  # legacy 1-4 levels without bands: map proportionally
            lo = cmax * (lvl.get("level", 1) - 1) / 4.0
        if score + 1e-9 >= float(lo):
            return lvl
        best = lvl
    return best
