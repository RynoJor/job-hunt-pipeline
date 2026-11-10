"""Indeed and Glassdoor through JobSpy (pip: python-jobspy).

LinkedIn is supported by JobSpy but is left out of this repo on purpose: its terms
forbid scraping. Google Jobs is supported too but returned nothing on every run in
October 2026, so it is off by default.
"""
from __future__ import annotations

import sys

BLOCKED_SITES = {"linkedin"}


def fetch(terms, sites=("indeed", "glassdoor"), countries=("usa", "uk", "south africa"),
          hours_old=168, results_per_term=30, log=print):
    from jobspy import scrape_jobs  # imported here so tests and offline runs don't need it

    sites = [s for s in sites if s not in BLOCKED_SITES]
    rows, status = [], {}
    for country in countries:
        for term in terms:
            key = f"{term} / {country}"
            try:
                df = scrape_jobs(site_name=sites, search_term=term, is_remote=True,
                                 results_wanted=results_per_term, hours_old=hours_old,
                                 country_indeed=country, description_format="markdown",
                                 verbose=0)
            except Exception as e:  # 403s, 429s and timeouts: log and move on
                status[key] = f"failed: {e.__class__.__name__}"
                print(f"  ! jobspy {key}: {e.__class__.__name__}: {str(e)[:120]}", file=sys.stderr)
                continue
            for r in df.to_dict("records"):
                rows.append({
                    "site": r.get("site"), "title": r.get("title"), "company": r.get("company"),
                    "location": r.get("location"), "board_scope": None,
                    "description": r.get("description"),
                    "min_amount": r.get("min_amount"), "max_amount": r.get("max_amount"),
                    "currency": r.get("currency"), "interval": r.get("interval"),
                    "date_posted": str(r.get("date_posted") or "")[:10],
                    "job_url": r.get("job_url"), "search_term": key,
                })
            status[key] = len(df)
            log(f"  jobspy {key}: {len(df)}")
    return rows, status
