from pathlib import Path

import pytest

from jobhunt.dedupe import dedupe
from jobhunt.normalise import company_key, normalise
from jobhunt.pipeline import run
from jobhunt.profile import load_profile
from jobhunt.score import pay_floor_usd_month, score_posting, title_tier
from jobhunt.seniority import seniority

PROFILE = load_profile(Path(__file__).parent.parent / "profile.example.yaml")
RATES = {"USD": 1.0, "ZAR": 18.0, "EUR": 0.9}
FLOOR = pay_floor_usd_month(PROFILE["pay"], RATES)  # 72k USD a year = 6,000 a month


def posting(**kw):
    base = dict(title="Revenue Operations Manager", remote_eligible=True, remote_reason="",
                usd_month=None, seniority="lead", description="")
    base.update(kw)
    return base


def test_floor_from_profile():
    assert FLOOR == 6000


@pytest.mark.parametrize("title, tier", [
    ("GTM Engineer", 3), ("Senior RevOps Analyst", 3), ("HubSpot Administrator", 3),
    ("Growth Marketing Manager", 2), ("Account Executive, EMEA", 2),
    ("Sales Representative", 1),
    ("Office Manager", 0),
    ("Senior Software Engineer, Growth", -1),   # the exclude list wins over "growth"
])
def test_title_tiers(title, tier):
    assert title_tier(title, PROFILE["titles"]) == tier


def test_perfect_fit_scores_100():
    s = score_posting(posting(usd_month=8000), PROFILE, FLOOR)
    assert s.points == 100 and not s.disqualified


def test_unknowns_score_partial_credit():
    s = score_posting(posting(remote_eligible=None, usd_month=None), PROFILE, FLOOR)
    # title 40 + remote 10 + pay 10 + seniority 10
    assert s.points == 70 and not s.disqualified
    assert "remote region unclear" in s.why and "pay not listed" in s.why


def test_locked_remote_disqualifies_and_says_why():
    s = score_posting(posting(remote_eligible=False, remote_reason="title names a territory: 'US'"),
                      PROFILE, FLOOR)
    assert s.disqualified
    assert "not open to South Africa" in s.why and "'US'" in s.why


def test_below_floor_disqualifies_by_default_and_penalises_if_set():
    assert score_posting(posting(usd_month=3000), PROFILE, FLOOR).disqualified
    soft = dict(PROFILE, pay=dict(PROFILE["pay"], below_floor="penalise"))
    s = score_posting(posting(usd_month=3000), soft, FLOOR)
    assert not s.disqualified and s.points == 80


def test_off_target_title_and_commission_only():
    assert score_posting(posting(title="Office Manager"), PROFILE, FLOOR).disqualified
    s = score_posting(posting(description="This is a commission-only role."), PROFILE, FLOOR)
    assert s.disqualified and "commission only" in s.why


def test_tier_two_title_scores_less_than_tier_three():
    a = score_posting(posting(title="RevOps Manager"), PROFILE, FLOOR).points
    b = score_posting(posting(title="Growth Manager"), PROFILE, FLOOR).points
    assert a > b


@pytest.mark.parametrize("title, level", [
    ("Head of Revenue Operations", "exec"), ("Senior RevOps Manager", "senior"),
    ("RevOps Manager", "lead"), ("Junior SDR", "junior"), ("GTM Engineer", "mid"),
])
def test_seniority(title, level):
    assert seniority(title) == level


def test_company_key_and_dedupe_prefers_board_with_scope():
    assert company_key("Acme, Inc.") == company_key("ACME (YC W24)") == "acme"
    a = normalise(dict(site="indeed", title="RevOps Manager", company="Acme Inc", job_url="u1"))
    b = normalise(dict(site="himalayas", title="RevOps Manager", company="Acme", job_url="u2",
                       board_scope="Worldwide"))
    c = normalise(dict(site="glassdoor", title="RevOps Manager", company="Acme", job_url="u1"))
    out = dedupe([a, b, c])
    assert len(out) == 1
    assert out[0]["site"] == "himalayas"
    assert out[0]["seen_on"] == "glassdoor, himalayas, indeed"


def test_normalise_fixes_double_encoded_text_and_strips_html():
    r = normalise(dict(title="Product Manager Â· New York", company="Acme",
                       description="<p>Hello&nbsp;<b>world</b></p>"))
    assert r["title"] == "Product Manager · New York"
    assert r["description"] == "Hello world"


def test_pipeline_end_to_end():
    raw = [
        dict(site="himalayas", title="RevOps Manager", company="Acme", board_scope="Worldwide",
             min_amount=90000, max_amount=110000, currency="USD", interval="yearly", job_url="a"),
        dict(site="himalayas", title="Growth Manager", company="Acme", board_scope="Worldwide",
             job_url="a2"),
        dict(site="indeed", title="Account Executive, US East", company="Beta",
             location="Remote", job_url="b"),
        dict(site="jobicy", title="GTM Engineer", company="Gamma", board_scope="USA", job_url="c"),
        dict(site="remotive", title="Sales Ops Lead", company="Delta", board_scope="EMEA",
             min_amount=20000, currency="USD", interval="yearly", job_url="d"),
    ]
    ranked, shortlist, summary = run(raw, PROFILE, RATES)
    assert summary["unique_postings"] == 5
    assert summary["remote_locked"] == 2 and summary["pct_locked"] == 40.0
    assert [p["company"] for p in shortlist] == ["Acme"]       # Delta is below floor
    assert shortlist[0]["other_roles"] == 1
    assert shortlist[0]["zar_month"] == round(110000 / 12 * 18)
