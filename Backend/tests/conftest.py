"""Test configuration.

By default the model call is replaced by a deterministic fake so the suite never spends API
credits and always produces the same result. Set RUN_LIVE_AI=1 to exercise the real model.
"""
import json
import os
import re

import pytest


def fake_chat_json(system: str, user: str, max_tokens: int):
    """Return a schema-valid evaluation for whatever prompt it receives."""
    n_criteria = len(re.findall(r"^Criterion \d+ \[", user, re.M))
    maxima = [float(m) for m in re.findall(r"^Criterion \d+ \[.\] — .+? \(maximum ([\d.]+) marks\)", user, re.M)]
    missing = re.search(r"Annotations are missing for these segment ids: ([\d, ]+)", user)
    if missing:
        ids = [int(x) for x in missing.group(1).split(",")]
        return {"annotations": [
            {"segment_id": i, "criterion_index": 1, "type": "strength", "comment": "Clear and relevant point."}
            for i in ids
        ]}, 10
    m = re.search(r"split into (\d+) numbered segments", user)
    n_segments = int(m.group(1)) if m else 0
    kinds = ["strength", "strength", "weakness", "suggestion"]
    return {
        "subject_relevant": True,
        "relevance_explanation": "The submission addresses the assessment brief.",
        "criterion_scores": [
            {"criterion_index": i + 1, "criterion_name": "", "level": "Good",
             "score": round(maxima[i] * 0.75, 2) if i < len(maxima) else 3.0,
             "justification": f"Solid evidence for criterion {i + 1} (see 1)."}
            for i in range(n_criteria)
        ],
        "overall_feedback": "You address the brief clearly and use course concepts accurately. Your strongest "
                            "feature is the explanation of evaluation metrics. To raise your mark, analyse "
                            "error cases in more depth and connect them to the course readings.",
        "annotations": [
            {"segment_id": i, "criterion_index": (i % max(n_criteria, 1)) + 1, "type": kinds[i % 4],
             "category": "Analysis" if kinds[i % 4] == "suggestion" else None,
             "comment": f"Specific comment about segment {i} and how it meets the rubric."}
            for i in range(1, n_segments + 1)
        ],
        "strengths": ["Clear structure", "Accurate terminology"],
        "weaknesses": ["Limited error analysis"],
        "improvement_suggestions": ["Add an error analysis section"],
        "missing_concepts": [],
        "supporting_evidence": [],
        "irrelevant_content_observations": [],
    }, 1234


@pytest.fixture(autouse=True)
def _offline_model(monkeypatch):
    if os.environ.get("RUN_LIVE_AI") == "1":
        yield
        return
    from app.services.ai import evaluator
    monkeypatch.setattr(evaluator, "_chat_json", fake_chat_json)
    yield


@pytest.fixture(scope="session", autouse=True)
def _migrated_database():
    """Apply migrations + seed once (TestClient without a context manager skips app startup)."""
    from app.core.init_db import run_migrations_and_seed
    run_migrations_and_seed()
    yield
