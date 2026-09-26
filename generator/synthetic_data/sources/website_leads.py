"""Website quote-form submissions, as the site's leads plugin returns them.

Mirrors a WordPress REST endpoint (GET /wp-json/quick-quote-leads/v1/leads)
with `page`/`per_page` pagination. Each submission carries whatever
tracking the visitor's browser brought along: UTM tags, click ids, the
referring site, and the pages they moved through. Around one in seven
submissions is spam, and none of that is labeled.
"""

import json
import random
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from synthetic_data.jobs import CompanyHistory, ContactMethod, Lead
from synthetic_data.sources.formats import phone_as_typed_by_a_person
from synthetic_data.timeline import BUSINESS_TIMEZONE, random_moment_in_month

PAGE_SIZE = 100
SITE_URL = "https://www.brightwire-electric.example"  # .example is reserved, never real

QUICK_QUOTE_FORM_ID = 101
CONTACT_FORM_ID = 205

SPAM_SUBMISSIONS_PER_REAL_SUBMISSION = 0.18
DOUBLE_SUBMIT_SHARE = 0.03
BLANK_MESSAGE_SHARE = 0.25
VAGUE_MESSAGE_SHARE = 0.20
DIFFERENT_EMAIL_SHARE = 0.20
GBP_LINK_IS_TAGGED_SHARE = 0.60

ACQUISITION_PARAM_NAMES = (
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "msclkid", "twclid", "ttclid", "ref", "campaign",
)

# What people type into the message box, by what they actually need.
CUSTOMER_MESSAGES = {
    "No-Power Troubleshooting": ("Half our house has no power, breaker looks fine", "Lost power to kitchen and garage outlets"),
    "Outlet & Switch Installation": ("Need a few outlets added in the basement", "Want to swap all switches to dimmers"),
    "Light Fixture Installation": ("Looking to install 8 recessed lights in living room", "Need a chandelier hung, 16ft ceiling"),
    "Diagnostic Visit": ("Lights flicker when the dryer runs", "Burning smell near an outlet, please help"),
    "EV Charger Installation": ("Need a quote for a Tesla wall connector in garage", "Just bought an EV, need a 240V charger"),
    "Panel Upgrade": ("Old Zinsco panel, want to upgrade to 200A", "Need panel upgrade for heat pump install"),
    "Heated Floor Wiring": ("Remodeling bathroom, need heated floor wired", "Floor heat thermostat install"),
    "Commercial Electrical Work": ("Office lighting retrofit, 3000 sq ft", "Need circuits added for restaurant equipment"),
    "Generator Installation": ("Want a generator inlet before winter storms", "Quote for standby generator install"),
    "Hot Tub Wiring": ("New hot tub arriving next month, need 50A circuit", "Hot tub wiring and disconnect"),
    "Circuit Breaker Replacement": ("Breaker won't reset", "Need a couple of breakers replaced"),
}
VAGUE_MESSAGES = ("Please call me", "Need a quote", "Looking for an electrician", "Call me back asap", "Hi")

SPAM_MESSAGES = (
    "We can get your business to #1 on Google in 30 days. Reply for a free audit.",
    "Pre-approved business funding up to $250,000. No credit check.",
    "Trusted residential electrician serving the Seattle area.",
    "I noticed your website could use a redesign. Can we set up a quick call?",
    "Exclusive electrical leads in your area, pay per lead. Interested?",
)
SPAM_SENDER_NAMES = ("SEO Team", "Jessica", "Business Funding Dept", "Mark Thompson", "Web Solutions")

USER_AGENTS = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
)


@dataclass(frozen=True)
class WebsiteLeadsExport:
    pages: list[dict]
    true_lead_id_by_submission_id: dict[int, str | None]  # answer key; None means spam


@dataclass(frozen=True)
class _Submission:
    submitted_at: datetime
    fields: dict
    true_lead_id: str | None


def export_website_leads(history: CompanyHistory, randomness: random.Random) -> WebsiteLeadsExport:
    submissions: list[_Submission] = []
    for lead in history.leads:
        if lead.contact_method is not ContactMethod.WEB_FORM:
            continue
        submission = _real_submission(lead, randomness)
        submissions.append(submission)
        if randomness.random() < DOUBLE_SUBMIT_SHARE:
            submissions.append(_double_submit_of(submission, randomness))
        if randomness.random() < SPAM_SUBMISSIONS_PER_REAL_SUBMISSION:
            submissions.append(_spam_submission(lead.created_at, randomness))

    # The plugin's ids are auto-incrementing, so they follow submission time.
    submissions.sort(key=lambda submission: submission.submitted_at)
    records = []
    answer_key = {}
    for submission_id, submission in enumerate(submissions, start=1):
        records.append({"id": submission_id, **submission.fields})
        answer_key[submission_id] = submission.true_lead_id

    return WebsiteLeadsExport(pages=_paginate(records), true_lead_id_by_submission_id=answer_key)


# --- Real submissions ----------------------------------------------------


def _real_submission(lead: Lead, randomness: random.Random) -> _Submission:
    customer = lead.customer
    entry_page = _entry_page(lead, randomness)
    submit_page = randomness.choices((entry_page, "/contact/", "/get-a-quote/"), weights=(60, 20, 20))[0]
    fields = {
        "cf7_form_id": CONTACT_FORM_ID if submit_page == "/contact/" else QUICK_QUOTE_FORM_ID,
        "name": f"{customer.first_name} {customer.last_name}",
        "phone": phone_as_typed_by_a_person(customer.primary_phone, randomness),
        "email": _email_given(customer.email, customer.last_name, randomness),
        "zipcode": customer.zip_code if randomness.random() < 0.9 else "",
        "message": _message(lead, randomness),
        "acquisition_params": _acquisition_params(lead, randomness),
        "session_navigation": json.dumps(_pages_visited(entry_page, submit_page)),
        "entry_page": entry_page,
        "submit_page": submit_page,
        "page_url": f"{SITE_URL}{submit_page}",
        "ip_address": _documentation_ip_address(randomness),
        "user_agent": randomness.choice(USER_AGENTS),
        "mail_status": "sent",
        "created_at": _site_timestamp(lead.created_at),
    }
    return _Submission(lead.created_at, fields, lead.lead_id)


def _double_submit_of(submission: _Submission, randomness: random.Random) -> _Submission:
    """The same form sent twice a few seconds apart (an impatient double click)."""
    resubmitted_at = submission.submitted_at + timedelta(seconds=randomness.randint(1, 8))
    fields = {**submission.fields, "created_at": _site_timestamp(resubmitted_at)}
    return _Submission(resubmitted_at, fields, submission.true_lead_id)


def _message(lead: Lead, randomness: random.Random) -> str:
    roll = randomness.random()
    if roll < BLANK_MESSAGE_SHARE:
        return ""
    if roll < BLANK_MESSAGE_SHARE + VAGUE_MESSAGE_SHARE:
        return randomness.choice(VAGUE_MESSAGES)
    return randomness.choice(CUSTOMER_MESSAGES[lead.service.name])


def _email_given(email_on_file: str, last_name: str, randomness: random.Random) -> str:
    """Sometimes people use a different address than the one on file."""
    if randomness.random() < DIFFERENT_EMAIL_SHARE:
        return f"{last_name.lower()}.home{randomness.randint(1, 99)}@example.net"
    return email_on_file


# --- Where the visitor came from -----------------------------------------


def _acquisition_params(lead: Lead, randomness: random.Random) -> dict:
    """Tracking parameters by channel. Untracked fields are empty strings, not
    nulls, because that's how the plugin stores a parameter that wasn't there."""
    params = dict.fromkeys(ACQUISITION_PARAM_NAMES, "")
    channel = lead.marketing_channel.name
    service_slug = _slug(lead.service.name)
    location_slug = _slug(lead.customer.location.name)

    if channel == "google_ads":
        params.update(utm_source="google", utm_medium="cpc",
                      utm_campaign=f"{service_slug}-{location_slug}", gclid=_click_id(randomness))
        params["ref"] = "https://www.google.com/"
    elif channel == "google_business_profile":
        if randomness.random() < GBP_LINK_IS_TAGGED_SHARE:
            params.update(utm_source="google", utm_medium="organic", utm_campaign="gbp-listing")
        params["ref"] = "https://www.google.com/"
    elif channel == "organic_search":
        params["ref"] = "https://www.google.com/"
    elif channel == "chatgpt":
        params["utm_source"] = "chatgpt.com"
        params["ref"] = randomness.choice(("https://chatgpt.com/", ""))
    elif channel == "referral":
        if randomness.random() < 0.2:
            params.update(utm_source="fb", fbclid=_click_id(randomness))
            params["ref"] = "https://www.facebook.com/"
        else:
            params["ref"] = randomness.choice(("", "", "https://nextdoor.com/"))
    return params


def _click_id(randomness: random.Random) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
    return "".join(randomness.choice(alphabet) for _ in range(40))


def _entry_page(lead: Lead, randomness: random.Random) -> str:
    service_slug = _slug(lead.service.name)
    city_slug = _slug(lead.customer.service_area.city)
    return randomness.choices(
        ("/", f"/{service_slug}/", f"/{service_slug}-{city_slug}-wa/"),
        weights=(30, 35, 35),
    )[0]


def _pages_visited(entry_page: str, submit_page: str) -> list[str]:
    return [entry_page] if entry_page == submit_page else [entry_page, submit_page]


# --- Spam ----------------------------------------------------------------


def _spam_submission(around: datetime, randomness: random.Random) -> _Submission:
    submitted_at = random_moment_in_month(around.date().replace(day=1), randomness)
    area_code = randomness.choice(("800", "213", "305", "646", "702"))
    fields = {
        "cf7_form_id": randomness.choice((QUICK_QUOTE_FORM_ID, CONTACT_FORM_ID)),
        "name": randomness.choice(SPAM_SENDER_NAMES),
        "phone": randomness.choice((f"{area_code}555{randomness.randint(0, 9999):04d}", "")),
        "email": f"outreach{randomness.randint(1, 999)}@example.org",
        "zipcode": "",
        "message": randomness.choice(SPAM_MESSAGES),
        "acquisition_params": dict.fromkeys(ACQUISITION_PARAM_NAMES, ""),
        "session_navigation": json.dumps(["/contact/"]),
        "entry_page": "/contact/",
        "submit_page": "/contact/",
        "page_url": f"{SITE_URL}/contact/",
        "ip_address": _documentation_ip_address(randomness),
        "user_agent": randomness.choice(USER_AGENTS),
        "mail_status": "sent",
        "created_at": _site_timestamp(submitted_at),
    }
    return _Submission(submitted_at, fields, true_lead_id=None)


# --- Formatting ----------------------------------------------------------


def _slug(text: str) -> str:
    """'Outlet & Switch Installation' -> 'outlet-and-switch-installation'."""
    text = text.lower().replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def _site_timestamp(moment: datetime) -> str:
    """WordPress stores local site time with no timezone: 2026-06-29 16:05:34."""
    return moment.astimezone(BUSINESS_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")


def _documentation_ip_address(randomness: random.Random) -> str:
    """Addresses from the blocks reserved for documentation (RFC 5737)."""
    network = randomness.choice(("192.0.2", "198.51.100", "203.0.113"))
    return f"{network}.{randomness.randint(1, 254)}"


def _paginate(records: list[dict]) -> list[dict]:
    """Pages shaped like the plugin's responses: the client derives the page
    count from `total` and `per_page`, since there is no `total_pages`."""
    chunks = [records[start : start + PAGE_SIZE] for start in range(0, len(records), PAGE_SIZE)]
    chunks = chunks or [[]]
    return [
        {"leads": chunk, "total": len(records), "per_page": PAGE_SIZE, "page": page_number}
        for page_number, chunk in enumerate(chunks, start=1)
    ]
