"""source -> normalise -> enrich -> dedupe -> score -> shortlist."""
from __future__ import annotations

from collections import Counter

from .dedupe import dedupe
from .normalise import normalise
from .pay import convert_monthly
from .remote import check_remote_eligibility
from .score import pay_floor_usd_month, score_posting
from .seniority import seniority


def enrich(p: dict, profile: dict, rates: dict) -> dict:
    """Add pay in USD and ZAR a month, seniority, and the remote verdict with its reason."""
    amount = p.get("max_amount") if p.get("max_amount") is not None else p.get("min_amount")
    pay = convert_monthly(amount, p.get("currency"), p.get("interval"), rates)
    verdict = check_remote_eligibility(
        title=p.get("title") or "", location=p.get("location") or "",
        description=p.get("description") or "", board_scope=p.get("board_scope"),
        open_markers=profile.get("region", {}).get("open_markers"))
    return dict(p, **pay, seniority=seniority(p.get("title") or ""),
                remote_eligible=verdict.eligible, remote=verdict.label,
                remote_reason=verdict.reason)


def run(raw_rows: list[dict], profile: dict, rates: dict) -> tuple[list[dict], list[dict], dict]:
    """Returns (every unique posting, the shortlist, summary counts)."""
    rows = [normalise(r) for r in raw_rows]
    rows = [r for r in rows if r["title"]]
    enriched = [enrich(r, profile, rates) for r in rows]
    unique = dedupe(enriched)

    floor = pay_floor_usd_month(profile.get("pay", {}), rates)
    for p in unique:
        s = score_posting(p, profile, floor)
        p.update(score=s.points, disqualified=s.disqualified, why=s.why)

    ranked = sorted(unique, key=lambda p: (p["disqualified"], -p["score"]))
    # One row per company: its best opening, with a count of its other matches.
    per_company = Counter(p["company_key"] for p in ranked if not p["disqualified"])
    shortlist, taken = [], set()
    for p in ranked:
        if p["disqualified"] or p["company_key"] in taken:
            continue
        taken.add(p["company_key"])
        shortlist.append(dict(p, other_roles=per_company[p["company_key"]] - 1))

    return ranked, shortlist, summarise(raw_rows, ranked, shortlist)


def summarise(raw_rows, unique, shortlist) -> dict:
    remote = Counter(p["remote"] for p in unique)
    lock_kind = Counter(p["remote_reason"].split(":")[0].split(" '")[0]
                        for p in unique if p["remote"] == "locked")
    on_target = [p for p in unique if "title off target" not in p["why"] and "title excluded" not in p["why"]]
    on_target_remote = Counter(p["remote"] for p in on_target)
    by_site = {}
    for p in unique:
        s = by_site.setdefault(p["site"], {"postings": 0, "open": 0, "locked": 0, "unclear": 0})
        s["postings"] += 1
        s[p["remote"]] += 1
    n = len(unique) or 1
    return {
        "rows_scraped": len(raw_rows),
        "unique_postings": len(unique),
        "remote_open": remote["open"], "remote_locked": remote["locked"],
        "remote_unclear": remote["unclear"],
        "pct_locked": round(100 * remote["locked"] / n, 1),
        "pct_open": round(100 * remote["open"] / n, 1),
        "lock_reasons": dict(lock_kind.most_common()),
        "on_target_titles": len(on_target),
        "on_target_locked": on_target_remote["locked"],
        "pay_listed": sum(1 for p in unique if p.get("usd_month") is not None),
        "disqualified": sum(1 for p in unique if p["disqualified"]),
        "shortlist": len(shortlist),
        "by_site": by_site,
    }
