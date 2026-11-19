"""Render the student feedback document (see ``feedback_document``) as a PDF.

The layout reproduces the reference essay-feedback document: an A4 page with 48pt margins,
Manrope ExtraBold headings and Inter body text; the student's text is laid out word by word so
each numbered segment can carry a tinted highlight, a coloured underline and a numbered badge.
"""
from __future__ import annotations

import logging
import unicodedata
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

logger = logging.getLogger(__name__)

FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"
W, H = A4
LEFT, RIGHT = 48.0, 547.3
TOP, BOTTOM = 52.9, 782.0
FOOTER_Y = 823.0

INK = "#0f172a"         # headings, scores
META = "#4b5563"        # name/date, footer
TEXT = "#334055"        # criteria, feedback text
BODY = "#475569"        # student text
RULE = "#cbd5e1"
MUTED = "#94a3b8"

TINTS = {
    "#0184c7": "#e0f2fe", "#9333ea": "#f0e6ff", "#ec4899": "#fdf2f8", "#16a34a": "#f0fdf4",
    "#ea580c": "#fff7ed", "#0d9488": "#ccfbf1", "#ca8a04": "#fef9c3", "#4f46e5": "#e0e7ff",
}

_FONTS = {"regular": "Helvetica", "medium": "Helvetica", "semibold": "Helvetica-Bold", "heading": "Helvetica-Bold"}
_CMAP: Dict[str, set] = {}


def _register_fonts() -> None:
    if _FONTS["medium"] != "Helvetica":
        return
    files = {"regular": "inter-400.ttf", "medium": "inter-500.ttf", "semibold": "inter-600.ttf", "heading": "manrope-800.ttf"}
    try:
        for key, fname in files.items():
            name = f"EE-{key}"
            if name not in pdfmetrics.getRegisteredFontNames():
                font = TTFont(name, str(FONT_DIR / fname))
                pdfmetrics.registerFont(font)
            _FONTS[key] = name
            _CMAP[name] = set(pdfmetrics.getFont(name).face.charToGlyph.keys())
    except Exception as exc:  # fonts missing: fall back to the built-in Helvetica family
        logger.warning("Feedback PDF fonts unavailable, using Helvetica: %s", exc)
        _FONTS.update({"regular": "Helvetica", "medium": "Helvetica", "semibold": "Helvetica-Bold", "heading": "Helvetica-Bold"})


def _safe(text: str, font: str) -> str:
    """Replace characters the font cannot draw (keeps the PDF free of tofu boxes)."""
    cmap = _CMAP.get(font)
    text = (text or "").replace(" ", " ").replace("\t", " ")
    if not cmap:
        return text.encode("latin-1", "replace").decode("latin-1")
    out = []
    for ch in text:
        if ord(ch) in cmap or ch in "\n ":
            out.append(ch)
            continue
        alt = unicodedata.normalize("NFKD", ch).encode("ascii", "ignore").decode()
        out.append(alt if alt and all(ord(c) in cmap for c in alt) else "?")
    return "".join(out)


def _w(text: str, font: str, size: float) -> float:
    return pdfmetrics.stringWidth(text, font, size)


def _wrap(text: str, font: str, size: float, width: float) -> List[str]:
    lines: List[str] = []
    for para in (text or "").split("\n"):
        words, cur = para.split(), ""
        if not words:
            lines.append("")
            continue
        for word in words:
            trial = f"{cur} {word}" if cur else word
            if _w(trial, font, size) <= width:
                cur = trial
                continue
            if cur:
                lines.append(cur)
            while _w(word, font, size) > width:  # hard-break very long tokens (URLs, code)
                cut = max(1, int(len(word) * width / _w(word, font, size)) - 1)
                lines.append(word[:cut])
                word = word[cut:]
            cur = word
        lines.append(cur)
    return lines


def _date(iso: Optional[str]) -> str:
    if not iso:
        d = datetime.now()
        return f"{d.day} {d.strftime('%B %Y')}"
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso[:10]
    return f"{d.day} {d.strftime('%B %Y')}"


class _Writer:
    def __init__(self, brand: str):
        self.buf = BytesIO()
        self.c = Canvas(self.buf, pagesize=A4)
        self.brand = brand
        self.y = TOP
        self.page_started = True

    # coordinates: callers use top-down y; ReportLab is bottom-up
    @staticmethod
    def Y(y: float) -> float:
        return H - y

    def text(self, x: float, y_top: float, s: str, font: str, size: float, color: str, align: str = "left") -> None:
        """Draw text whose bounding box top is ``y_top``."""
        s = _safe(s, font)
        self.c.setFont(font, size)
        self.c.setFillColor(HexColor(color))
        baseline = self.Y(y_top + size * 0.96)
        if align == "right":
            self.c.drawRightString(x, baseline, s)
        else:
            self.c.drawString(x, baseline, s)

    def rule(self, y: float, width: float = 1.0, x0: float = LEFT, x1: float = RIGHT) -> None:
        self.c.setStrokeColor(HexColor(RULE))
        self.c.setLineWidth(width)
        self.c.line(x0, self.Y(y), x1, self.Y(y))

    def badge(self, cx: float, cy_top: float, d: float, n: int, color: str, size: float) -> None:
        tint = TINTS.get(color, "#ffffff")
        self.c.setFillColor(HexColor(color))
        self.c.setStrokeColor(HexColor(color))
        self.c.setLineWidth(0.8)
        self.c.circle(cx, self.Y(cy_top), d / 2.0, stroke=1, fill=1)
        font = _FONTS["semibold"]
        label = str(n)
        self.c.setFont(font, size)
        self.c.setFillColor(HexColor(tint))
        self.c.drawCentredString(cx, self.Y(cy_top) - size * 0.36, label)

    def watermark(self) -> None:
        """Faint brand mark in the middle of the page (like the reference document)."""
        c = self.c
        c.saveState()
        c.setFillColor(HexColor("#f1f1f1"))
        c.roundRect(W / 2 - 60, H / 2 - 60, 120, 120, 26, stroke=0, fill=1)
        c.setFillColor(HexColor("#ffffff"))
        p = c.beginPath()  # mortarboard
        cx, cy = W / 2, H / 2 + 8
        p.moveTo(cx - 40, cy); p.lineTo(cx, cy + 20); p.lineTo(cx + 40, cy); p.lineTo(cx, cy - 20); p.close()
        c.drawPath(p, stroke=0, fill=1)
        c.roundRect(cx - 24, cy - 36, 48, 26, 8, stroke=0, fill=1)
        c.restoreState()

    def footer(self) -> None:
        self.text(RIGHT, FOOTER_Y - 9.4, self.brand, _FONTS["medium"], 10.5, META, align="right")

    def new_page(self) -> None:
        self.footer()
        self.c.showPage()
        self.y = TOP
        self.watermark()

    def ensure(self, needed: float, on_break=None) -> bool:
        if self.y + needed <= BOTTOM:
            return False
        if on_break:
            on_break("close")
        self.new_page()
        if on_break:
            on_break("open")
        return True

    def finish(self) -> bytes:
        self.footer()
        self.c.save()
        return self.buf.getvalue()


# ─── Sections ────────────────────────────────────────────────────────────────

def _score_page(w: _Writer, doc: Dict) -> None:
    w.watermark()
    heading, medium, semi = _FONTS["heading"], _FONTS["medium"], _FONTS["semibold"]
    title = f"Score {doc['score_display']}"
    w.text(LEFT, TOP, title, heading, 16.8, INK)
    tw = _w(title, heading, 16.8)
    w.text(LEFT + tw + 4, TOP + 4.6, f"/ {doc['max_display']}", heading, 12, MUTED)

    y = 82.9
    name = doc.get("student_name") or "Student"
    w.text(LEFT, y, name, medium, 11.2, META)
    nx = LEFT + _w(name, medium, 11.2) + 9.8
    w.c.setFillColor(HexColor(META))
    w.c.circle(nx, w.Y(y + 7.1), 1.5, stroke=0, fill=1)
    w.text(nx + 8.2, y, _date(doc.get("date")), medium, 11.2, META)

    info = " · ".join(filter(None, [doc.get("subject_name"), doc.get("assessment_title"),
                                    (f"RTLP {doc['rtlp_code']} {doc['assessment_type']}" if doc.get("rtlp_code")
                                     else doc.get("assessment_type"))]))
    y += 16
    for line in _wrap(info, _FONTS["regular"], 9.2, RIGHT - LEFT):
        w.text(LEFT, y, line, _FONTS["regular"], 9.2, MUTED)
        y += 12

    y += 6
    text_w = (RIGHT - 52) - 62
    for i, c in enumerate(doc["criteria"]):
        label = f"{c['label']}. {c['name']}"
        if c.get("level"):
            label += f" — {c['level']}"
        lines = _wrap(label, medium, 10.2, text_w)
        if c.get("level_description"):
            lines += _wrap(c["level_description"], _FONTS["regular"], 9.4, text_w)
        if i:
            w.rule(y - 5.8, 0.75)
        w.c.setFillColor(HexColor(c["color"]))
        w.c.circle(53.0, w.Y(y + 5.6), 3.15, stroke=0, fill=1)
        n_label = len(_wrap(label, medium, 10.2, text_w))
        for j, line in enumerate(lines):
            if j < n_label:
                w.text(62, y, line, medium, 10.2, TEXT)
            else:
                w.text(62, y, line, _FONTS["regular"], 9.4, META)
            y += 14 if j < n_label else 13
        score = c["score_display"]
        maxs = f"/{c['max_display']}"
        top = y - sum(14 if j < n_label else 13 for j in range(len(lines)))
        w.text(RIGHT, top, maxs, medium, 9.0, MUTED, align="right")
        w.text(RIGHT - _w(maxs, medium, 9.0) - 1.5, top, score, semi, 10.2, INK, align="right")
        y += 10
    w.y = y


def _annotated_pages(w: _Writer, doc: Dict) -> None:
    medium, semi = _FONTS["medium"], _FONTS["semibold"]
    w.new_page()
    question = f"{doc.get('question') or doc.get('assessment_title')} [{doc['max_display']}]"
    y = 54.4
    for line in _wrap(question, medium, 13.2, RIGHT - LEFT):
        w.text(LEFT, y, line, medium, 13.2, INK)
        y += 17
    y += 1
    w.rule(y + 0.6, 1.0)
    y += 14.3

    size, pitch = 11.0, 16.0
    space = _w(" ", medium, size)
    width = RIGHT - LEFT

    for p_idx, para in enumerate(doc["paragraphs"]):
        # tokens: (word, segment, is_first_word_of_segment)
        tokens: List[Tuple[str, Dict, bool]] = []
        for seg in para:
            words = _safe(seg["text"], medium).split()
            for k, word in enumerate(words):
                tokens.append((word, seg, k == 0))
        # greedy line breaking
        lines: List[List[Tuple[str, Dict, bool, float]]] = []
        cur: List[Tuple[str, Dict, bool, float]] = []
        x = 0.0
        for word, seg, first in tokens:
            ww = _w(word, medium, size)
            if cur and x + space + ww > width:
                lines.append(cur)
                cur, x = [], 0.0
            if cur:
                x += space
            cur.append((word, seg, first, x))
            x += ww
        if cur:
            lines.append(cur)

        if p_idx:
            y += pitch  # blank line between paragraphs
        for line in lines:
            if y + pitch > BOTTOM:
                w.new_page()
                y = TOP + 2
            badges = []
            # highlight runs (consecutive words of the same annotated segment)
            run_start = 0
            for k in range(1, len(line) + 1):
                if k == len(line) or line[k][1]["id"] != line[run_start][1]["id"]:
                    seg = line[run_start][1]
                    if seg.get("color"):
                        x0 = LEFT + line[run_start][3]
                        last = line[k - 1]
                        x1 = LEFT + last[3] + _w(last[0], medium, size)
                        tint = TINTS.get(seg["color"], "#f1f5f9")
                        w.c.setFillColor(HexColor(tint))
                        w.c.rect(x0 - 0.5, w.Y(y - 2.3 + 15), (x1 - x0) + 1.0, 15, stroke=0, fill=1)
                        w.c.setStrokeColor(HexColor(seg["color"]))
                        w.c.setLineWidth(1.1)
                        w.c.line(x0, w.Y(y + 12.7), x1, w.Y(y + 12.7))
                    run_start = k
            for word, seg, first, xo in line:
                w.text(LEFT + xo, y, word, medium, size, BODY)
                if first and seg.get("color"):
                    badges.append((LEFT + xo, seg))
            for bx, seg in badges:
                two = seg["id"] >= 10
                w.badge(bx + 1.25, y - 0.8, 12.5 if two else 11.5, seg["id"], seg["color"], 6.1 if two else 6.7)
            y += pitch
    w.y = y


def _items_box(w: _Writer, title: str, items: List[Dict], *, title_size: float = 12.5) -> None:
    """A bordered box with a title and numbered comment items; repeats the title on page breaks."""
    medium, heading = _FONTS["medium"], _FONTS["heading"]
    text_x, text_w = 86.0, RIGHT - 14 - 86.0
    state = {"top": w.y}

    def open_box():
        state["top"] = w.y
        w.text(62, w.y + 13.2, title, heading, title_size, INK)
        w.y += 13.2 + 17 + 10

    def close_box():
        bottom = w.y + 2
        w.c.setStrokeColor(HexColor(RULE))
        w.c.setLineWidth(1.0)
        w.c.rect(LEFT, w.Y(bottom), RIGHT - LEFT, bottom - state["top"], stroke=1, fill=0)

    def on_break(kind):
        close_box() if kind == "close" else open_box()

    if w.y + 80 > BOTTOM:
        w.new_page()
    open_box()
    for it in items:
        lines = _wrap(_safe(it["comment"], medium), medium, 10.2, text_w)
        need = 14 * len(lines) + 12
        w.ensure(need + 14, on_break)
        two = it["id"] >= 10
        w.badge(71.0, w.y + 1.2 + 8.5, 17, it["id"], it["color"], 7.0 if two else 7.5)
        for k, line in enumerate(lines):
            w.text(text_x, w.y + k * 14, line, medium, 10.2, TEXT)
        w.y += need
    w.y += 2
    close_box()
    w.y += 14


def _feedback_pages(w: _Writer, doc: Dict) -> None:
    heading, medium = _FONTS["heading"], _FONTS["medium"]
    w.new_page()
    w.text(LEFT, TOP, "Overall feedback", heading, 16, INK)
    y = 82.3
    for line in _wrap(doc.get("overall_feedback") or "", medium, 10.8, RIGHT - LEFT):
        w.text(LEFT, y, line, medium, 10.8, TEXT)
        y += 15.5
    w.y = y
    if doc.get("faculty_comments"):
        w.y += 8
        w.ensure(60)
        w.text(LEFT, w.y, "Faculty comments", heading, 12.5, INK)
        w.y += 22
        for line in _wrap(doc["faculty_comments"], medium, 10.8, RIGHT - LEFT):
            w.ensure(16)
            w.text(LEFT, w.y, line, medium, 10.8, TEXT)
            w.y += 15.5
    w.y += 18
    w.rule(w.y, 1.0)
    w.y += 12.9

    if doc.get("strengths") or doc.get("weaknesses"):
        w.ensure(90)
        w.text(LEFT, w.y, "Feedback", heading, 16, INK)
        w.y += 29.1
        if doc.get("strengths"):
            _items_box(w, "Strengths", doc["strengths"])
        if doc.get("weaknesses"):
            _items_box(w, "Weaknesses", doc["weaknesses"])
    if doc.get("suggestions"):
        w.ensure(90)
        w.text(LEFT, w.y, "Suggestions", heading, 16, INK)
        w.y += 29.1
        for group in doc["suggestions"]:
            _items_box(w, group["category"], group["items"])


def render_feedback_pdf(doc: Dict) -> bytes:
    _register_fonts()
    w = _Writer(doc.get("brand") or "EduEval AI")
    w.c.setTitle(f"Feedback — {doc.get('assessment_title', '')} — {doc.get('student_name', '')}")
    w.c.setAuthor(doc.get("brand") or "EduEval AI")
    _score_page(w, doc)
    if doc.get("paragraphs"):
        _annotated_pages(w, doc)
    _feedback_pages(w, doc)
    return w.finish()
