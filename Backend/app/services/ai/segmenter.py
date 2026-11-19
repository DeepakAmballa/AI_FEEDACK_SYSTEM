"""Deterministic segmentation of a student submission into numbered sentences.

The annotated feedback document shows the student's own text split into numbered
segments, each highlighted by the rubric criterion it relates to. Segmentation is done
here (never by the model) so the text in the report is exactly what the student wrote;
the model only annotates segment ids.
"""
from __future__ import annotations

import re
from typing import List, Dict

# Abbreviations that end in a period but do not end a sentence.
_ABBREV = {
    "e.g", "i.e", "etc", "vs", "dr", "mr", "mrs", "ms", "prof", "fig", "no", "vol", "pp",
    "al", "st", "jr", "sr", "approx", "dept", "eq", "ref", "sec", "ch", "cf", "inc", "ltd",
}
# A sentence ends at . ! ? (optionally followed by closing quotes/brackets) + whitespace.
_BOUNDARY = re.compile(r'([.!?]["\'”’)\]]*)(\s+)(?=[\"“‘(\[]?[A-Z0-9])')
_BULLET = re.compile(r'^\s*(?:[-*•▪◦·]|\d{1,3}[.)]|[a-zA-Z][.)])\s+')

MIN_CHARS = 25          # fragments shorter than this are merged into a neighbour
DEFAULT_MAX_SEGMENTS = 140


def _clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace(" ", "\n").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_paragraph(par: str) -> List[str]:
    """Split one paragraph into sentences, respecting common abbreviations."""
    par = re.sub(r"\s*\n\s*", " ", par).strip()
    if not par:
        return []
    out, start = [], 0
    for m in _BOUNDARY.finditer(par):
        end = m.end(1)
        prev_word = re.search(r"([A-Za-z.]+)[.!?][\"'”’)\]]*$", par[start:end])
        if prev_word and prev_word.group(1).lower().rstrip(".") in _ABBREV:
            continue
        # single capital initial ("J. Smith") is not a boundary
        if re.search(r"\b[A-Z]\.$", par[start:end]):
            continue
        out.append(par[start:end].strip())
        start = m.end()
    tail = par[start:].strip()
    if tail:
        out.append(tail)
    return out


def _paragraphs(text: str) -> List[str]:
    """Blank lines separate paragraphs; list items / short lines become their own paragraphs."""
    paras: List[str] = []
    for block in re.split(r"\n\s*\n", text):
        lines = [l for l in block.split("\n") if l.strip()]
        if not lines:
            continue
        # A block of list items / headings / code-like short lines: keep each line separate.
        listy = sum(1 for l in lines if _BULLET.match(l) or len(l) < 60) >= max(2, len(lines) * 0.6)
        if listy and len(lines) > 1:
            paras.extend(l.strip() for l in lines)
        else:
            paras.append(" ".join(l.strip() for l in lines))
    return paras


def segment_submission(text: str, max_segments: int = DEFAULT_MAX_SEGMENTS) -> List[Dict]:
    """Return [{id, paragraph, text}] with ids starting at 1.

    Very short fragments are merged with the following sentence of the same paragraph,
    and for long submissions consecutive sentences are grouped so the document stays
    within ``max_segments`` annotations.
    """
    text = _clean(text or "")
    if not text:
        return []

    raw: List[Dict] = []
    for p_idx, par in enumerate(_paragraphs(text)):
        sentences = _split_paragraph(par)
        merged: List[str] = []
        for s in sentences:
            if merged and len(merged[-1]) < MIN_CHARS:
                merged[-1] = f"{merged[-1]} {s}"
            else:
                merged.append(s)
        if len(merged) > 1 and len(merged[-1]) < MIN_CHARS:
            last = merged.pop()
            merged[-1] = f"{merged[-1]} {last}"
        raw.extend({"paragraph": p_idx, "text": s} for s in merged)

    # Group sentences when the document is long, never across paragraphs.
    group = max(1, -(-len(raw) // max_segments))
    segments: List[Dict] = []
    if group == 1:
        segments = raw
    else:
        buf: List[Dict] = []
        for item in raw:
            if buf and (len(buf) >= group or buf[-1]["paragraph"] != item["paragraph"]):
                segments.append({"paragraph": buf[0]["paragraph"], "text": " ".join(b["text"] for b in buf)})
                buf = []
            buf.append(item)
        if buf:
            segments.append({"paragraph": buf[0]["paragraph"], "text": " ".join(b["text"] for b in buf)})

    return [{"id": i, "paragraph": s["paragraph"], "text": s["text"]} for i, s in enumerate(segments, start=1)]


def numbered_for_prompt(segments: List[Dict], char_budget: int = 60000) -> str:
    """Render segments as '[id] text' lines (paragraph breaks kept) for the model prompt."""
    lines, used, prev_par = [], 0, None
    for s in segments:
        if prev_par is not None and s["paragraph"] != prev_par:
            lines.append("")
        line = f"[{s['id']}] {s['text']}"
        used += len(line)
        if used > char_budget:
            lines.append(f"[{s['id']}…] (remaining text truncated for length)")
            break
        lines.append(line)
        prev_par = s["paragraph"]
    return "\n".join(lines)
