"""The same job turns up on three boards. Keep the copy with the most to go on."""
from __future__ import annotations

# Boards with a structured "who can apply" field come first: their copy carries
# the strongest remote evidence.
SOURCE_RANK = {"himalayas": 0, "remotive": 0, "jobicy": 0, "pnet": 0,
               "remoteok": 1, "workingnomads": 1, "weworkremotely": 2,
               "indeed": 3, "glassdoor": 3}


def _rank(p):
    return (SOURCE_RANK.get(p.get("site"), 5),
            0 if p.get("usd_month") is not None else 1,
            -len(p.get("description") or ""))


def dedupe(postings: list[dict]) -> list[dict]:
    """Drop repeats by URL, then by (company, title). Adds `seen_on`: every board it was on."""
    best: dict[tuple, dict] = {}
    seen_on: dict[tuple, set] = {}
    url_to_key: dict[str, tuple] = {}
    for p in postings:
        key = (p.get("company_key") or "", p.get("title_key") or "")
        url = p.get("job_url")
        if url and url in url_to_key:
            key = url_to_key[url]
        if url:
            url_to_key[url] = key
        seen_on.setdefault(key, set()).add(p.get("site") or "?")
        if key not in best or _rank(p) < _rank(best[key]):
            best[key] = p
    out = []
    for key, p in best.items():
        out.append(dict(p, seen_on=", ".join(sorted(seen_on[key]))))
    return out
