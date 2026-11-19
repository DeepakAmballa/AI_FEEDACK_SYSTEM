"""Unit tests for the RTLP rubric library, segmentation, scoring and the feedback document/PDF."""
from types import SimpleNamespace

from app.services.ai.evaluator import AnnotationAI, AIEvaluationResponse, CriterionScoreAI, _validate_annotations, _validate_scores
from app.services.ai.scoring import combine_criterion_scores, performance_level
from app.services.ai.segmenter import segment_submission
from app.services.report.feedback_pdf import render_feedback_pdf
from app.services.rubrics.library import library, scale_criteria


def test_rtlp_library_is_complete_and_consistent():
    items = library()
    codes = {i["code"] for i in items}
    # every rubric in RTLP chapter 14 plus the two answer-key quizzes
    for code in ["14.2.1", "14.2.11", "14.3.1", "14.3.7", "14.4.2", "14.5", "14.6.2", "14.7.2", "14.8.2", "14.2.3", "14.4.3"]:
        assert code in codes
    for item in items:
        total = sum(c["max_marks"] for c in item["criteria"])
        assert abs(total - item["total_marks"]) < 1e-6, item["name"]
        for c in item["criteria"]:
            assert len(c["levels"]) == 4 and all(l["description"] for l in c["levels"]), (item["name"], c["name"])
    essay = next(i for i in items if i["name"] == "Reflective Essay")
    assert essay["total_marks"] == 40 and essay["criteria"][0]["levels"][0]["max_marks"] == 8


def test_scale_criteria_to_assessment_marks():
    case = next(i for i in library() if i["name"] == "Case Study")  # 5 x 20 = 100
    scaled = scale_criteria(case["criteria"], 20)
    assert [c["max_marks"] for c in scaled] == [4.0] * 5
    assert scaled[0]["levels"][0]["min_marks"] == 3.2
    assert case["criteria"][0]["max_marks"] == 20  # original untouched


def test_segmenter_keeps_text_and_paragraphs():
    text = ("Dr. Rao explained e.g. caching. Caches reduce latency! Do they always help?\n\n"
            "Second paragraph starts here. It ends here.")
    segs = segment_submission(text)
    assert [s["id"] for s in segs] == list(range(1, len(segs) + 1))
    assert segs[0]["text"].startswith("Dr. Rao explained e.g. caching.")
    assert {s["paragraph"] for s in segs} == {0, 1}
    assert " ".join(s["text"] for s in segs).replace("  ", " ") == text.replace("\n\n", " ")


def test_segmenter_groups_long_submissions():
    text = " ".join(f"Sentence number {i} is long enough to stand alone." for i in range(400))
    segs = segment_submission(text, max_segments=100)
    assert len(segs) <= 100
    assert "Sentence number 0" in segs[0]["text"] and "Sentence number 399" in segs[-1]["text"]


def test_criterion_scores_average_and_sum_to_final():
    ai = [{"criterion_name": n, "max_marks": 4, "score": s} for n, s in zip("ABCDE", [3, 3.5, 2, 4, 3])]
    fac = [{"criterion_name": n, "score": s} for n, s in zip("ABCDE", [3, 3, 3, 3.5, 2.5])]
    rows = combine_criterion_scores(ai, fac, 15.0, 15.25)
    assert [r["final"] for r in rows] == [3.0, 3.25, 2.5, 3.75, 2.75]
    rows = combine_criterion_scores(ai, None, 13.0, 14.25)  # faculty gave a holistic total only
    assert round(sum(r["final"] for r in rows), 2) == 14.25
    assert all(0 <= r["final"] <= r["max_marks"] for r in rows)


def test_performance_level_uses_bands():
    crit = scale_criteria(next(i for i in library() if i["name"] == "Case Study")["criteria"], 20)[0]
    assert performance_level(3.4, crit)["name"].startswith("A")
    assert performance_level(2.4, crit)["name"].startswith("B")
    assert performance_level(0.2, crit)["name"].startswith("D")


def test_validation_clamps_scores_and_filters_annotations():
    criteria = [{"name": "Relevance", "label": "A", "max_marks": 4.0}, {"name": "Clarity", "label": "B", "max_marks": 4.0}]
    result = AIEvaluationResponse(criterion_scores=[
        CriterionScoreAI(criterion_index=1, score=9), CriterionScoreAI(criterion_name="clarity", score=2.3)])
    scores = _validate_scores(result, criteria)
    assert [s["score"] for s in scores] == [4.0, 2.5]
    ann = _validate_annotations([
        AnnotationAI(segment_id=1, criterion_index=7, type="Weakness", comment="Typo 'teh'."),
        AnnotationAI(segment_id=1, criterion_index=1, type="strength", comment="duplicate"),
        AnnotationAI(segment_id=99, criterion_index=1, type="strength", comment="unknown segment"),
        AnnotationAI(segment_id=2, criterion_index=1, type="suggestion", category="style", comment="Vary sentence length."),
    ], {1, 2}, n_criteria=2)
    assert ann[1]["criterion_index"] == 1 and ann[1]["type"] == "weakness"
    assert ann[2]["category"] == "Style" and set(ann) == {1, 2}


def test_feedback_pdf_renders():
    colors = ["#0184c7", "#9333ea"]
    doc = {
        "brand": "EduEval AI", "student_name": "Test Student", "date": "2026-05-06T00:00:00",
        "assessment_title": "Essay", "question": "Explain caching.", "max_display": "8", "score_display": "6.5",
        "criteria": [{"label": "A", "name": "Understanding", "color": colors[0], "score_display": "3.5", "max_display": "4",
                      "level": "Good", "level_description": "Good understanding"},
                     {"label": "B", "name": "Clarity", "color": colors[1], "score_display": "3", "max_display": "4"}],
        "paragraphs": [[{"id": i, "text": f"Sentence {i} about caches → latency “quoted”.", "color": colors[i % 2]}
                        for i in range(1, 30)]],
        "overall_feedback": "Good work. " * 20,
        "strengths": [{"id": i, "color": colors[0], "comment": "Clear point."} for i in range(1, 25)],
        "weaknesses": [{"id": 25, "color": colors[1], "comment": "Spelling 'teh'."}],
        "suggestions": [{"category": "Style", "items": [{"id": 26, "color": colors[1], "comment": "Vary sentences."}]}],
    }
    pdf = render_feedback_pdf(doc)
    assert pdf.startswith(b"%PDF") and len(pdf) > 5000


def test_model_response_parsing_is_lenient():
    """Real model outputs that used to raise a ValidationError and fail the whole evaluation."""
    r = AIEvaluationResponse(**{
        "subject_relevant": "true",
        "irrelevant_content_observations": ["'sentiment analysis, model fine-tuning and empirical evaluation metrics'",
                                            {"text": "off-topic aside", "why_unrelated": "not in the brief"}, None],
        "supporting_evidence": ["exact quote", {"quote": "another"}],
        "strengths": "Clear structure",
        "weaknesses": [{"point": "Thin analysis"}, ""],
        "criterion_scores": [{"criterion_index": "1", "score": "3.5/4"}, "junk"],
        "annotations": [{"segment_id": "[3]", "criterion_index": "B2", "type": "Strength", "comment": "Good."},
                        {"segment_id": "n/a", "comment": "dropped later"}, "junk"],
        "overall_feedback": ["Part one.", "Part two."],
    })
    assert r.subject_relevant is True
    assert r.irrelevant_content_observations[0].excerpt.startswith("'sentiment analysis")
    assert r.irrelevant_content_observations[1].why_unrelated == "not in the brief"
    assert [e.text for e in r.supporting_evidence] == ["exact quote", "another"]
    assert r.strengths == ["Clear structure"] and r.weaknesses == ["Thin analysis"]
    assert r.criterion_scores[0].score == 3.5 and r.criterion_scores[0].criterion_index == 1
    assert r.annotations[0].segment_id == 3 and r.annotations[0].criterion_index == 2
    ann = _validate_annotations(r.annotations, {1, 2, 3}, n_criteria=2)
    assert set(ann) == {3}
    assert r.overall_feedback == "Part one.; Part two."
