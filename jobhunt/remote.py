"""The "remote in name only" detector.

A job board's remote filter answers one question: can this job be done from home?
A job seeker needs a different answer: can this job be done from *my* home?
Most "remote" ads fail the second test. They want US residence, a UK right to work,
a security clearance, or a seat tied to a sales territory.

`check_remote_eligibility` reads the evidence in a fixed order, strongest first, and
returns a verdict with the reason, so every flag can be checked by a person.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Phrases that tie a "remote" job to one country's residence, work permit or clearance.
LOCK_PHRASES = re.compile(
    r"(?:authori[sz]ed to work in the (?:u\.?s\.?a?|united states|uk|united kingdom|eu|european union)"
    r"|(?:legally )?eligible to work in the (?:u\.?s\.?a?|united states|uk|united kingdom)"
    r"|must (?:reside|live|be (?:located|based)) in (?:the )?(?!south africa|africa|emea)[a-z .]{2,30}"
    r"|(?:us|u\.s\.) citizens? only|green card|security clearance|\bitar\b"
    r"|remote\s*[\(\-–:]\s*(?:us|usa|u\.s\.|united states|uk|canada|eu|europe)(?:\s*only)?\)?"
    r"|(?:within|anywhere in) the (?:united states|us|u\.s\.|uk|united kingdom|continental us)"
    r"|(?:us|usa|uk|canada)[- ]based (?:candidates|applicants|only)"
    r"|no visa sponsorship)",
    re.I,
)

# Territory words in a title mean the seat covers that patch, whatever the board says.
TITLE_TERRITORY = re.compile(
    r"\b(?:us|usa|u\.s\.|amer|americas|north america|namer|na|canada|uk|dach|nordics|benelux"
    r"|apac|anz|latam|federal|public sector|east|west|central|midwest|northeast|southeast"
    r"|southwest|northwest|ny|nyc|texas|california|florida|chicago|boston|new york|london"
    r"|toronto|sydney|singapore|germany|france|spain|italy|netherlands|japan|india|brazil|mexico)\b",
    re.I,
)

# A location or board-scope field that names any of these places is locked to them.
ELSEWHERE = re.compile(
    r"\b(?:us|usa|u\.s\.|united states|america|americas|canada|uk|united kingdom|england|ireland"
    r"|europe|eu|european union|germany|france|spain|portugal|netherlands|poland|italy|sweden"
    r"|norway|denmark|finland|switzerland|austria|latam|latin america|brazil|mexico|argentina"
    r"|colombia|apac|asia|india|japan|singapore|australia|new zealand|philippines|israel"
    r"|san francisco|new york|london|berlin|toronto|[A-Z][a-z]+, (?:CA|NY|TX|WA|MA|FL|IL|CO|GA))\b",
    re.I,
)

DEFAULT_OPEN = ["south africa", "africa", "emea", "worldwide", "anywhere", "global",
                "work from anywhere", "fully distributed"]


@dataclass(frozen=True)
class RemoteVerdict:
    """eligible is True (open to you), False (locked elsewhere) or None (not stated)."""
    eligible: bool | None
    reason: str

    @property
    def label(self) -> str:
        return {True: "open", False: "locked", None: "unclear"}[self.eligible]


def _open_pattern(open_markers):
    words = "|".join(re.escape(m) for m in (open_markers or DEFAULT_OPEN))
    return re.compile(rf"\b(?:{words})\b(?! in the (?:us|united states|uk))", re.I)


# In ad text, "global" and bare "anywhere" are boilerplate ("a global team", "work anywhere
# in the US"), so they only count in location and scope fields.
WEAK_IN_TEXT = {"global", "anywhere"}
# Phrases that are about hiring on their own, wherever they appear in the ad.
HIRING_PHRASES = {"work from anywhere", "fully distributed", "anywhere in the world"}
# Other markers in ad text count only next to a hiring word: "Remote - EMEA", "Location:
# Worldwide", "hiring in South Africa". "Customers worldwide" and "offices worldwide" don't.
HIRING_CONTEXT = re.compile(
    r"(?:remote|location|based|hiring|hire|candidates|applicants|open to|eligible|work from"
    r"|living in|live in|reside|located|residents?)\W[^.\n]{0,25}$", re.I)

# A territory word in a title followed by one of these names a client market or a time
# zone, not where you must live: "US Healthcare", "USA Hours", "UK clients".
CLIENT_CONTEXT = re.compile(
    r"^\W{0,3}(?:hours|time|timezone|time zone|shift|healthcare|company|clients?|customers?"
    r"|est|pst|cst|gmt)\b", re.I)


def _title_territory(title: str):
    for m in TITLE_TERRITORY.finditer(title):
        if not CLIENT_CONTEXT.search(title[m.end():m.end() + 20]):
            return m
    return None


def _text_open(description: str, markers) -> re.Match | None:
    for m in _open_pattern(markers).finditer(description):
        if m.group(0).lower() in HIRING_PHRASES:
            return m
        if HIRING_CONTEXT.search(description[max(0, m.start() - 40):m.start()]):
            return m
    return None


def _quote(m: re.Match) -> str:
    return m.group(0).strip()[:60]


def check_remote_eligibility(title: str = "", location: str = "", description: str = "",
                             board_scope: str | None = None, open_markers=None) -> RemoteVerdict:
    """Decide whether a "remote" posting is open to someone in the target region.

    title        job title
    location     the board's free-text location field
    description  the ad text
    board_scope  a board's structured "who can apply" field (Himalayas, Remotive, Jobicy).
                 None when the board has none or its label can't be trusted (We Work Remotely).
    open_markers place words that mean "open to you", e.g. ["south africa", "emea", "worldwide"]

    Order of evidence, strongest first:
      1. the title names a territory (a "US East" seat is locked whatever else it says)
      2. the ad text has a residence, work-permit or clearance clause
      3. the board's structured scope field
      4. the free-text location field
      5. the ad text says it hires in your region ("Remote - EMEA", "work from anywhere")
    """
    title, location, description = title or "", location or "", description or ""
    is_open = _open_pattern(open_markers)

    m = _title_territory(title)
    if m:
        return RemoteVerdict(False, f"title names a territory: '{_quote(m)}'")

    m = LOCK_PHRASES.search(description)
    if m:
        return RemoteVerdict(False, f"ad text locks it: '{_quote(m)}'")

    if board_scope is not None and str(board_scope).strip():
        scope = str(board_scope)
        m = is_open.search(scope)
        if m:
            return RemoteVerdict(True, f"board scope includes '{_quote(m)}'")
        return RemoteVerdict(False, f"board scope is '{scope.strip()[:60]}'")

    if location.strip():
        m = is_open.search(location)
        if m:
            return RemoteVerdict(True, f"location says '{_quote(m)}'")
        m = ELSEWHERE.search(location)
        if m:
            return RemoteVerdict(False, f"location is tied to '{_quote(m)}'")

    text_markers = [w for w in (open_markers or DEFAULT_OPEN) if w.lower() not in WEAK_IN_TEXT]
    m = _text_open(description, text_markers)
    if m:
        return RemoteVerdict(True, f"ad text says '{_quote(m)}'")

    return RemoteVerdict(None, "no region stated: read the ad")
