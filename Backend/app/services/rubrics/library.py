"""RTLP rubric library — Aurora Reflective Teaching Learning Policy, Chapter 14.

The canonical rubric data lives in ``app/data/rtlp_rubrics.json`` (extracted from the RTLP
policy document, every criterion and level descriptor verbatim). This module converts it to
the ``criteria_data`` format stored on ``RubricVersion`` and provides scaling helpers so a
rubric can be applied to an assessment whose maximum marks differ from the rubric total.
"""
from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "rtlp_rubrics.json"

# Quiz-type RTLP tools are marked against a predefined answer key, not a descriptor rubric.
ANSWER_KEY_TYPES = [
    {
        "code": "14.2.3", "name": "Quiz", "section": "Pre-Learning Assessment", "category": "pre_learning",
        "description": "Objective quiz (MCQ, true/false, short answer) evaluated strictly against the faculty answer key.",
    },
    {
        "code": "14.4.3", "name": "Laboratory Quiz", "section": "Laboratory Assessment", "category": "laboratory",
        "description": "Short objective laboratory quiz evaluated strictly against the faculty answer key.",
    },
]


@lru_cache(maxsize=1)
def _raw() -> Dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def _criteria_data(rubric: Dict) -> List[Dict]:
    out = []
    for c in rubric["criteria"]:
        descs = c["descriptors"]
        out.append({
            "name": c["name"],
            "max_marks": float(c["max_marks"]),
            "description": descs[0]["text"],
            "levels": [
                {
                    "level": 4 - i,
                    "name": d["level"],
                    "description": d["text"],
                    "min_marks": float(d["min"]),
                    "max_marks": float(d["max"]),
                }
                for i, d in enumerate(descs)
            ],
        })
    return out


def _answer_key_criteria(total: float = 20.0) -> List[Dict]:
    return [{
        "name": "Accuracy against answer key",
        "max_marks": float(total),
        "description": "Each response is marked correct, partially correct, or incorrect strictly against the faculty answer key.",
        "levels": [
            {"level": 4, "name": "Excellent", "description": "All or nearly all responses match the answer key.", "min_marks": total * 0.85, "max_marks": total},
            {"level": 3, "name": "Good", "description": "Most responses match the answer key with a few errors.", "min_marks": total * 0.6, "max_marks": total * 0.85},
            {"level": 2, "name": "Average", "description": "About half of the responses match the answer key.", "min_marks": total * 0.35, "max_marks": total * 0.6},
            {"level": 1, "name": "Needs Improvement", "description": "Few responses match the answer key.", "min_marks": 0.0, "max_marks": total * 0.35},
        ],
    }]


def library() -> List[Dict]:
    """All RTLP assessment types: [{code, name, section, category, evaluation_mode, total_marks, description, criteria}]."""
    items = []
    for r in _raw()["rubrics"]:
        items.append({
            "code": r["code"],
            "name": r["name"],
            "section": r["section"],
            "category": r["category"],
            "evaluation_mode": r["evaluation_mode"],
            "total_marks": float(r["total_marks"]),
            "description": f"RTLP {r['code']} · {r['section']} — {r['name']} ({int(r['total_marks'])} marks, "
                           f"{len(r['criteria'])} criteria).",
            "criteria": _criteria_data(r),
        })
    for q in ANSWER_KEY_TYPES:
        items.append({**q, "evaluation_mode": "answer_key", "total_marks": 20.0, "criteria": _answer_key_criteria(20.0)})
    items.sort(key=lambda x: [int(p) for p in x["code"].split(".")])
    return items


def source_name() -> str:
    return _raw().get("source", "RTLP")


def scale_criteria(criteria: List[Dict], target_total: Optional[float]) -> List[Dict]:
    """Scale criterion maxima (and level bands) so they sum to ``target_total``."""
    criteria = copy.deepcopy(criteria or [])
    total = sum(float(c.get("max_marks", 0) or 0) for c in criteria)
    if not criteria or not target_total or total <= 0 or abs(total - float(target_total)) < 1e-9:
        return criteria
    k = float(target_total) / total
    for c in criteria:
        c["max_marks"] = round(float(c["max_marks"]) * k, 2)
        for lvl in c.get("levels", []) or []:
            for key in ("min_marks", "max_marks"):
                if key in lvl and lvl[key] is not None:
                    lvl[key] = round(float(lvl[key]) * k, 2)
    # absorb rounding drift in the last criterion
    drift = round(float(target_total) - sum(c["max_marks"] for c in criteria), 2)
    criteria[-1]["max_marks"] = round(criteria[-1]["max_marks"] + drift, 2)
    return criteria
