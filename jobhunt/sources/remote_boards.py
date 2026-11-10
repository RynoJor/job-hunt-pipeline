"""Remote-first boards with public feeds. Most of them say who can apply.

board_scope holds a board's structured "who can apply" field, which the remote
detector trusts above free text. It is None where a board has no such field, or
where the label can't be trusted: We Work Remotely tags almost every ad "Anywhere in
the World", including US-only seats.

Remotive, Remote OK and Jobicy ask for a link back and a source credit when their
jobs are shared. The job_url column keeps that link.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from ..pay import parse_salary_text

UA = {"User-Agent": "Mozilla/5.0 (job-hunt-pipeline; personal job search)"}
BROWSER_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/130 Safari/537.36"}
REMOTEOK_TAGS = ["sales", "marketing", "operations"]
WWR_FEEDS = ["remote-sales-and-marketing-jobs", "all-other-remote-jobs"]
WWR_LABEL = re.compile(r"anywhere in the world", re.I)


def _get(url, as_json=True, headers=UA):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
        body = r.read()
    return json.loads(body) if as_json else body


def _row(**kw):
    base = dict(site=None, title=None, company=None, location=None, board_scope=None,
                description="", min_amount=None, max_amount=None, currency=None,
                interval=None, date_posted="", job_url=None, search_term=None)
    base.update(kw)
    return base


def _per_year(period):
    p = (period or "year").lower()
    return 12 if p.startswith("month") else 2080 if p.startswith("hour") else 1


def remotive(terms):
    rows = []
    for term in terms:
        q = urllib.parse.quote(term)
        for j in _get(f"https://remotive.com/api/remote-jobs?search={q}&limit=50")["jobs"]:
            lo, hi, cur, iv = parse_salary_text(j.get("salary"))
            where = j.get("candidate_required_location")
            rows.append(_row(site="remotive", title=j["title"], company=j["company_name"],
                             location=where, board_scope=where, min_amount=lo, max_amount=hi,
                             currency=cur, interval=iv,
                             date_posted=(j.get("publication_date") or "")[:10],
                             job_url=j["url"], description=j.get("description", ""),
                             search_term=term))
    return rows


def himalayas(terms):
    rows = []
    for term in terms:
        q = urllib.parse.quote(term)
        for j in _get(f"https://himalayas.app/jobs/api/search?q={q}&limit=50").get("jobs", []):
            restr = j.get("locationRestrictions") or []
            where = ", ".join(restr) if restr else "Worldwide"
            m = _per_year(j.get("salaryPeriod"))
            ts = j.get("pubDate")
            rows.append(_row(
                site="himalayas", title=j["title"], company=j["companyName"], location=where,
                board_scope=where,
                min_amount=j["minSalary"] * m if j.get("minSalary") else None,
                max_amount=j["maxSalary"] * m if j.get("maxSalary") else None,
                currency=j.get("currency"), interval="yearly",
                date_posted=dt.datetime.fromtimestamp(ts, dt.timezone.utc).date().isoformat() if ts else "",
                job_url=j.get("applicationLink") or j.get("guid"),
                description=j.get("excerpt", ""), search_term=term))
    return rows


def jobicy(terms):
    rows, seen = [], set()
    for term in terms:
        q = urllib.parse.quote(term)
        try:
            jobs = _get(f"https://jobicy.com/api/v2/remote-jobs?count=50&tag={q}").get("jobs", [])
        except urllib.error.HTTPError as e:
            if e.code == 400:  # Jobicy answers 400, not an empty list, when a tag has no jobs
                continue
            raise
        for j in jobs:
            if j["id"] in seen:
                continue
            seen.add(j["id"])
            m = _per_year(j.get("salaryPeriod"))
            rows.append(_row(
                site="jobicy", title=j.get("jobTitle"), company=j.get("companyName"),
                location=j.get("jobGeo"), board_scope=j.get("jobGeo"),
                min_amount=float(j["salaryMin"]) * m if j.get("salaryMin") else None,
                max_amount=float(j["salaryMax"]) * m if j.get("salaryMax") else None,
                currency=j.get("salaryCurrency"), interval="yearly",
                date_posted=(j.get("pubDate") or "")[:10], job_url=j.get("url"),
                description=j.get("jobDescription") or j.get("jobExcerpt") or "", search_term=term))
    return rows


def remoteok(terms=None):
    rows, seen = [], set()
    for tag in REMOTEOK_TAGS:
        for j in _get(f"https://remoteok.com/api?tag={tag}")[1:]:
            if j["id"] in seen:
                continue
            seen.add(j["id"])
            lo, hi = j.get("salary_min") or None, j.get("salary_max") or None
            rows.append(_row(site="remoteok", title=j.get("position"), company=j.get("company"),
                             location=j.get("location"), min_amount=lo, max_amount=hi,
                             currency="USD" if (lo or hi) else None, interval="yearly",
                             date_posted=(j.get("date") or "")[:10], job_url=j.get("url"),
                             description=j.get("description", ""), search_term=f"tag:{tag}"))
    return rows


def weworkremotely(terms=None):
    rows = []
    for feed in WWR_FEEDS:
        root = ET.fromstring(_get(f"https://weworkremotely.com/categories/{feed}.rss", as_json=False))
        for it in root.iter("item"):
            raw = it.findtext("title") or ""
            company, _, title = raw.partition(": ")
            rows.append(_row(
                site="weworkremotely", title=title or raw, company=company if title else "",
                location=None,  # the region label is no signal; leave it to the ad text
                description=WWR_LABEL.sub("", it.findtext("description") or ""),
                date_posted=(it.findtext("pubDate") or "")[5:16], job_url=it.findtext("link"),
                search_term=f"feed:{feed}"))
    return rows


def workingnomads(terms=None):
    return [_row(site="workingnomads", title=j.get("title"), company=j.get("company_name"),
                 location=j.get("location"), date_posted=(j.get("pub_date") or "")[:10],
                 job_url=j.get("url"), description=j.get("description", ""), search_term="feed")
            for j in _get("https://www.workingnomads.com/api/exposed_jobs/")]


PNET_STATE = re.compile(r'window\.__PRELOADED_STATE__\["app-unifiedResultlist"\]\s*=\s*')


def pnet(terms):
    """South Africa's largest board, fully-remote filter (wfh=1). No API: this reads the
    result-list JSON embedded in the search page, so it breaks if Pnet changes the page."""
    rows = []
    for term in terms:
        slug = re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")
        page = _get(f"https://www.pnet.co.za/jobs/{slug}?wfh=1", as_json=False,
                    headers=BROWSER_UA).decode("utf-8", "ignore")
        m = PNET_STATE.search(page)
        if not m:
            raise RuntimeError("result list not found: page layout changed or request blocked")
        blob = page[m.end():page.find("</script>", m.end())].rstrip().rstrip(";")
        for it in json.loads(blob)["searchResults"]["items"]:
            rows.append(_row(site="pnet", title=it.get("title"), company=it.get("companyName"),
                             location=it.get("location"), board_scope="South Africa",
                             date_posted=(it.get("datePosted") or "")[:10],
                             job_url=(it.get("url") or "").split("?")[0],
                             description=re.sub(r"<[^>]+>", "", it.get("textSnippet") or ""),
                             search_term=term))
    return rows


BOARDS = {"remotive": remotive, "himalayas": himalayas, "jobicy": jobicy, "remoteok": remoteok,
          "weworkremotely": weworkremotely, "workingnomads": workingnomads, "pnet": pnet}


def fetch(terms, boards=None, log=print):
    rows, status = [], {}
    for name in boards or BOARDS:
        try:
            got = BOARDS[name](terms)
            rows += got
            status[name] = len(got)
            log(f"  {name}: {len(got)}")
        except Exception as e:  # one board failing never stops the run
            status[name] = f"failed: {e.__class__.__name__}"
            print(f"  ! {name}: {e.__class__.__name__}: {str(e)[:120]}", file=sys.stderr)
    return rows, status
