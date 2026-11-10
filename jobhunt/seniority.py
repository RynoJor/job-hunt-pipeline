"""Seniority from the title. Coarse on purpose: it feeds a filter, not a judgement."""
import re

LEVELS = [
    ("exec", re.compile(r"\b(?:vp|vice president|chief|c[rmo]o|head of|director)\b", re.I)),
    ("lead", re.compile(r"\b(?:lead|principal|staff|manager)\b", re.I)),
    ("senior", re.compile(r"\b(?:senior|sr\.?)\b", re.I)),
    ("junior", re.compile(r"\b(?:junior|jr\.?|associate|entry|graduate|intern(?:ship)?|trainee)\b", re.I)),
]


def seniority(title: str) -> str:
    """'Senior RevOps Manager' -> 'senior'. Senior beats manager; exec beats both."""
    t = title or ""
    hits = {name for name, rx in LEVELS if rx.search(t)}
    for name in ("exec", "senior", "lead", "junior"):
        if name in hits:
            return name
    return "mid"
