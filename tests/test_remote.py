import pytest

from jobhunt.remote import check_remote_eligibility as check


@pytest.mark.parametrize("title, location, description, scope, expected, reason_has", [
    # 1. A territory in the title beats everything, even a "Worldwide" board label.
    ("Account Executive, US East", "", "", "Worldwide", False, "territory"),
    ("RevOps Manager - DACH", "Remote", "", None, False, "dach"),
    # 2. Residence, permit and clearance clauses in the ad text.
    ("RevOps Manager", "Remote", "You must be authorized to work in the United States.", None, False, "authorized"),
    ("Growth Lead", "", "Remote (US only). Great benefits.", None, False, "remote (us only"),
    ("Sales Ops Analyst", "", "Candidates must reside in Canada or the UK.", None, False, "must reside"),
    ("CRM Specialist", "", "This role requires an active security clearance.", None, False, "clearance"),
    ("GTM Engineer", "", "We are hiring anywhere in the United States.", None, False, "anywhere in the united states"),
    ("Account Manager", "", "We offer no visa sponsorship.", None, False, "visa"),
    # 3. A board's structured scope field.
    ("RevOps Lead", "", "", "Worldwide", True, "worldwide"),
    ("RevOps Lead", "", "", "EMEA, Americas", True, "emea"),
    ("RevOps Lead", "", "", "USA", False, "usa"),
    ("RevOps Lead", "", "", "Germany, Poland", False, "germany"),
    # 4. The free-text location field.
    ("Growth Marketer", "Johannesburg, South Africa", "", None, True, "south africa"),
    ("Growth Marketer", "Austin, TX, US", "", None, False, "us"),
    ("Growth Marketer", "London, England, UK", "", None, False, "london"),
    # 5. The ad text names the region.
    ("Lifecycle Manager", "Remote", "We hire across EMEA.", None, True, "emea"),
    ("Lifecycle Manager", "", "Work from anywhere in the world.", None, True, "work from anywhere"),
])
def test_verdicts(title, location, description, scope, expected, reason_has):
    v = check(title, location, description, scope)
    assert v.eligible is expected, v.reason
    assert reason_has in v.reason.lower()


def test_boilerplate_global_in_text_is_not_evidence():
    # "a global team" is in half of all US ads; it must not open the job.
    v = check("RevOps Manager", "Remote", "Join our global team of 500 people.", None)
    assert v.eligible is None
    assert v.label == "unclear"


def test_must_reside_in_your_own_region_is_not_a_lock():
    v = check("Sales Ops", "", "You must reside in South Africa.", None)
    assert v.eligible is True


def test_nothing_stated_is_unclear_not_open():
    v = check("RevOps Manager", "Remote", "Great team, great product.", None)
    assert v.eligible is None
    assert "read the ad" in v.reason


def test_custom_region_markers():
    # Someone in Brazil would configure their own markers.
    v = check("Growth Lead", "", "", "LATAM", open_markers=["latam", "worldwide"])
    assert v.eligible is True


def test_lock_clause_beats_open_scope():
    v = check("RevOps Lead", "", "Must be authorised to work in the UK.", "Worldwide")
    assert v.eligible is False


@pytest.mark.parametrize("description", [
    "We serve 80,000 customers worldwide.",
    "Our platform is used by millions of people worldwide.",
    "Headquartered in Milan with 22 plants worldwide.",
    "We run tours to Africa, Egypt and the Middle East.",
])
def test_company_boilerplate_does_not_open_the_job(description):
    # Found in a live run: most "worldwide" hits in ad text describe the company, not the hire.
    assert check("RevOps Manager", "", description, None).eligible is None


@pytest.mark.parametrize("description", [
    "Location: Worldwide. Full-time.",
    "Marketing Specialist, Remote Worldwide, full-time.",
    "Headquarters: Remote - EMEA",
    "We are hiring candidates based in South Africa.",
    "We are a fully distributed team.",
])
def test_hiring_context_opens_the_job(description):
    assert check("RevOps Manager", "", description, None).eligible is True


@pytest.mark.parametrize("title", [
    "Patient Services Coordinator - US Healthcare | EST",
    "Bookkeeper | USA Hours",
    "Director of Client Operations, Remote, US Company",
    "Account Manager for UK clients",
])
def test_client_market_in_title_is_not_a_territory(title):
    # Seen on the South African board: SA-based seats serving US or UK clients.
    assert check(title, "", "", "South Africa").eligible is True


def test_real_territory_still_locks_even_with_client_word_elsewhere():
    assert check("Account Executive, US East (healthcare)", "", "", "Worldwide").eligible is False


def test_title_word_inside_another_word_is_not_a_territory():
    # "Business" contains "us"; "Nash" contains "na". Word boundaries matter.
    v = check("Business Development Manager", "", "", "Worldwide")
    assert v.eligible is True
