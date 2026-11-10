"""One shape for every source, so the later steps never care where a row came from."""
from __future__ import annotations

import html
import math
import re

COLUMNS = ["site", "title", "company", "location", "board_scope", "description",
           "min_amount", "max_amount", "currency", "interval", "date_posted", "job_url",
           "search_term"]

_TAGS = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")
_COMPANY_NOISE = re.compile(r"\(yc [^)]*\)|\b(?:inc|ltd|llc|pty|gmbh|corp|limited|co)\b\.?|[^a-z0-9 ]")


def _fix_mojibake(s: str) -> str:
    """Remote OK sends some text UTF-8 encoded twice ('Â·' for '·'). Undo it when it parses."""
    if "Ã" not in s and "Â" not in s and "â€" not in s:
        return s
    try:
        return s.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def _clean(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, str):
        v = _fix_mojibake(v)
        v = _SPACE.sub(" ", html.unescape(_TAGS.sub(" ", v))).strip()
        return v or None
    return v


def normalise(row: dict) -> dict:
    """Keep the shared columns, strip HTML and blank strings, and add match keys."""
    out = {c: _clean(row.get(c)) for c in COLUMNS}
    out["description"] = out["description"] or ""
    out["company_key"] = company_key(out["company"])
    out["title_key"] = _SPACE.sub(" ", re.sub(r"[^a-z0-9 ]", " ", (out["title"] or "").lower())).strip()
    return out


def company_key(name) -> str:
    """'Acme, Inc.' and 'ACME (YC W24)' both become 'acme'."""
    return _SPACE.sub(" ", _COMPANY_NOISE.sub("", (name or "").lower())).strip()
