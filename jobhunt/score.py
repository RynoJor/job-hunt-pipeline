"""Fit score against a profile, plus the disqualifiers. Every point comes with a reason."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

COMMISSION_ONLY = re.compile(r"commission[- ]only|100% commission", re.I)


@dataclass
class Score:
    points: int
    disqualified: bool
    reasons: list[str] = field(default_factory=list)

    @property
    def why(self) -> str:
        return "; ".join(self.reasons)


def title_tier(title: str, titles: dict) -> int:
    """3, 2, 1 for the highest tier the title matches, 0 for none, -1 if excluded."""
    t = title or ""
    if any(re.search(p, t, re.I) for p in titles.get("exclude", [])):
        return -1
    for tier in (3, 2, 1):
        if any(re.search(p, t, re.I) for p in titles.get(f"tier_{tier}", [])):
            return tier
    return 0


def pay_floor_usd_month(pay: dict, rates: dict) -> float | None:
    from .pay import annualise
    if not pay or pay.get("floor") is None:
        return None
    yearly = annualise(pay["floor"], pay.get("per", "yearly"))
    return yearly / rates.get(pay.get("currency", "USD").upper(), 1.0) / 12


def score_posting(p: dict, profile: dict, floor_usd_month: float | None) -> Score:
    """p needs: title, remote_eligible (True/False/None), remote_reason, usd_month,
    seniority, description. Returns points out of 100 and whether it is disqualified."""
    w = profile.get("weights", {"title": 40, "remote": 30, "pay": 20, "seniority": 10})
    reasons, pts, dq = [], 0, False

    tier = title_tier(p.get("title", ""), profile.get("titles", {}))
    if tier <= 0:
        dq = True
        reasons.append("title excluded" if tier < 0 else "title off target")
    else:
        pts += round(w["title"] * tier / 3)
        reasons.append(f"title tier {tier}")

    eligible = p.get("remote_eligible")
    if eligible is False:
        dq = True
        reasons.append(f"not open to {profile.get('region', {}).get('name', 'you')}: {p.get('remote_reason')}")
    elif eligible is True:
        pts += w["remote"]
        reasons.append("remote, open to you")
    else:
        pts += round(w["remote"] / 3)
        reasons.append("remote region unclear")

    usd = p.get("usd_month")
    if usd is None or floor_usd_month is None:
        pts += round(w["pay"] / 2)
        reasons.append("pay not listed")
    elif usd >= floor_usd_month:
        pts += w["pay"]
        reasons.append("pay meets floor")
    else:
        reasons.append("pay below floor")
        if profile.get("pay", {}).get("below_floor", "disqualify") == "disqualify":
            dq = True

    if p.get("seniority") in profile.get("seniority", {}).get("wanted", []):
        pts += w["seniority"]

    if COMMISSION_ONLY.search(f"{p.get('title', '')} {p.get('description', '')}"):
        dq = True
        reasons.append("commission only")

    return Score(points=pts, disqualified=dq, reasons=reasons)
