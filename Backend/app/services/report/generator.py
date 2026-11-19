"""
PDF Report Generator for EduEval AI using ReportLab.
Generates the 10-section Unified Student Academic Evaluation Report.
"""
from io import BytesIO
import logging
from xml.sax.saxutils import escape
from typing import Dict, Any

logger = logging.getLogger(__name__)


def generate_unified_pdf_report(report_data: Dict[str, Any]) -> bytes:
    """
    Generate professional evaluation PDF report.

    10 Sections:
    1. Student Information
    2. Assessment Information
    3. Final Evaluation (Final marks, Max marks, Percentage)
    4. Overall Feedback
    5. Strengths
    6. Areas for Improvement
    7. Criterion-Level Feedback
    8. Improvement Suggestions
    9. Irrelevant-Content Observations
    10. Final Remarks
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib import colors

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    header_style = ParagraphStyle(
        "HeaderTitle",
        parent=styles["Title"],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1e3a8a"),
        alignment=0,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "SubTitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=12,
    )
    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#334155"),
        spaceAfter=6,
    )
    score_banner = ParagraphStyle(
        "ScoreBanner",
        parent=styles["Normal"],
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#047857"),
        spaceAfter=6,
    )
    callout_box = ParagraphStyle(
        "CalloutBox",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#991b1b"),
    )

    story = []

    # Title & Subtitle
    story.append(Paragraph("EduEval AI — Student Evaluation Report", header_style))
    story.append(Paragraph("Official Academic Assessment & Evaluation Feedback", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563eb"), spaceAfter=12))

    # Section 1 & 2: Student & Assessment Info Table
    info_data = [
        [
            Paragraph("<b>Student Name:</b> " + escape(str(report_data.get("student_name", "N/A"))), body_style),
            Paragraph("<b>Subject:</b> " + escape(str(report_data.get("subject_name", "N/A"))), body_style),
        ],
        [
            Paragraph("<b>Student ID:</b> " + escape(str(report_data.get("student_id", "N/A"))), body_style),
            Paragraph("<b>Assessment:</b> " + escape(str(report_data.get("assessment_title", "N/A"))), body_style),
        ],
        [
            Paragraph("<b>Program:</b> " + escape(str(report_data.get("program", "Academic Program"))), body_style),
            Paragraph("<b>Assessment Type:</b> " + escape(str(report_data.get("assessment_type", "Standard"))), body_style),
        ],
        [
            Paragraph("<b>Submission Date:</b> " + escape(str(report_data.get("submission_date", "N/A"))), body_style),
            Paragraph("<b>Maximum Marks:</b> " + escape(str(report_data.get("max_marks", 20))), body_style),
        ],
    ]
    info_table = Table(info_data, colWidths=[85 * mm, 85 * mm])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#f1f5f9")),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 10))

    # Section 3: Final Evaluation
    final_score = report_data.get("final_score", 0.0)
    max_marks = report_data.get("max_marks", 20.0)
    percentage = round((final_score / max_marks) * 100, 1) if max_marks else 0

    score_data = [[
        Paragraph(f"<b>Final Marks Awarded:</b> <font size=16 color='#047857'><b>{final_score} / {max_marks}</b></font> ({percentage}%)", score_banner)
    ]]
    score_table = Table(score_data, colWidths=[170 * mm])
    score_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ecfdf5")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#a7f3d0")),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 10))

    # Section 4: Submitted Document
    submission_filename = report_data.get("submission_filename")
    submission_content = report_data.get("submission_content")
    if submission_filename or submission_content:
        story.append(Paragraph("4. Submitted Document", section_heading))
        if submission_filename:
            story.append(Paragraph(
                f"<b>File:</b> {escape(str(submission_filename))}",
                body_style,
            ))
        if submission_content:
            content = escape(str(submission_content)).replace("\r\n", "\n").replace("\r", "\n")
            content = content.replace("\n", "<br/>")
            story.append(Paragraph(content, body_style))

    # Section 5: Overall Feedback
    if report_data.get("overall_feedback"):
        story.append(Paragraph("5. Overall Feedback", section_heading))
        story.append(Paragraph(escape(str(report_data["overall_feedback"])), body_style))

    # Section 6: Strengths
    if report_data.get("strengths"):
        story.append(Paragraph("6. Demonstrated Strengths", section_heading))
        story.append(Paragraph(escape(str(report_data["strengths"])), body_style))

    # Section 7: Areas for Improvement
    if report_data.get("weaknesses"):
        story.append(Paragraph("7. Areas Requiring Improvement", section_heading))
        story.append(Paragraph(escape(str(report_data["weaknesses"])), body_style))

    # Section 8: Criterion-Level Feedback
    criterion_feedback = report_data.get("criterion_feedback", [])
    if criterion_feedback:
        story.append(Paragraph("8. Rubric Criterion Analysis", section_heading))
        crit_rows = [["Criterion", "Evaluation & Guidance"]]
        for item in criterion_feedback:
            crit_rows.append([
                Paragraph(f"<b>{escape(item.get('criterion_name', ''))}</b>", body_style),
                Paragraph(escape(str(item.get("description", ""))), body_style),
            ])
        crit_table = Table(crit_rows, colWidths=[55 * mm, 115 * mm], repeatRows=1)
        crit_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("PADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(crit_table)
        story.append(Spacer(1, 6))

    # Section 9: Improvement Suggestions
    if report_data.get("improvement_suggestions"):
        story.append(Paragraph("9. Actionable Improvement Suggestions", section_heading))
        story.append(Paragraph(escape(str(report_data["improvement_suggestions"])), body_style))

    # Section 10: Mark Reduction Reasons
    if report_data.get("deduction_reasons"):
        story.append(Paragraph("10. Reasons for Mark Reduction", section_heading))
        story.append(Paragraph(escape(str(report_data["deduction_reasons"])), callout_box))

    # Section 11: Irrelevant-Content Observations
    irrelevant_obs = report_data.get("irrelevant_observations", [])
    if irrelevant_obs:
        story.append(Paragraph("11. Irrelevant-Content Observations", section_heading))
        for obs in irrelevant_obs:
            obs_text = (
                f"<b>Excerpt:</b> \"{escape(str(obs.get('excerpt', '')))}\"<br/>"
                f"<b>Section/Page:</b> {escape(str(obs.get('section_or_page', 'Submission')))}<br/>"
                f"<b>Observation:</b> {escape(str(obs.get('why_unrelated', '')))}<br/>"
                f"<b>Affected Criterion:</b> {escape(str(obs.get('relevant_criterion', 'Content Relevance')))}<br/>"
                f"<b>Score Impact:</b> {escape(str(obs.get('score_impact', 'None')))}"
            )
            obs_table = Table([[Paragraph(obs_text, callout_box)]], colWidths=[170 * mm])
            obs_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fef2f2")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#fecaca")),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(obs_table)
            story.append(Spacer(1, 4))

    # Section 12: Final Remarks
    story.append(Paragraph("12. Final Remarks", section_heading))
    remarks = report_data.get("final_remarks") or (
        "This evaluation reflects your performance against the academic rubric criteria. "
        "Review the strengths and suggestions carefully to support your ongoing academic development."
    )
    story.append(Paragraph(escape(remarks), body_style))

    # Footer note
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#94a3b8"), spaceAfter=6))
    story.append(Paragraph(
        "EduEval AI Academic Assessment System · Verified Academic Evaluation Report",
        ParagraphStyle("FooterNote", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#94a3b8"), alignment=1)
    ))

    doc.build(story)
    return buffer.getvalue()
