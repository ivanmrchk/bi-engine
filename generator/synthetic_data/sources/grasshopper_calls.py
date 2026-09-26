"""What the Grasshopper phone system did: every call, broken into legs.

Grasshopper doesn't log conversations, it logs *legs*. A customer calling
in is one inbound leg, plus an outbound leg each time the call is
forwarded: first to the owner's cell and, if nobody picks up, on to
Housecall Pro's AI call taker. A call the owner places from the Grasshopper
app shows up as an inbound leg *from the owner's own cell* plus an
outbound leg to the other party.
"""

import math
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum

from synthetic_data.calibration import LOCATIONS, Location
from synthetic_data.customers import Customer
from synthetic_data.jobs import CompanyHistory, ContactMethod, Job, Lead
from synthetic_data.timeline import (
    random_moment_in_month,
    random_moment_on_day,
    simulated_days,
    simulated_months,
)

OWNER_CELL_NUMBER = "+13605550100"
AI_CALL_TAKER_NUMBER = "+15415550100"
AI_CALL_TAKER_ADOPTED_ON = date(2025, 6, 1)

EXTENSION_BY_LOCATION = {
    "Eastside": "0 - Default Extension",
    "South Sound": "2 - New Extension",
}

# How an inbound call goes. Whatever is left over (30%) goes to voicemail,
# or to the AI call taker once the company adopted it.
OWNER_ANSWERS_SHARE = 0.55
CALLER_HANGS_UP_WHILE_RINGING_SHARE = 0.15

MISSED_CALL_RETURNED_SHARE = 0.80
WEB_LEAD_CALLED_BACK_SHARE = 0.85
VISIT_DAY_CALL_SHARE = 0.30
OUTBOUND_CALL_CONNECTS_SHARE = 0.85
SECOND_PHONE_USED_SHARE = 0.35

# Existing customers call about work that is booked or just finished:
# scheduling, "running late?", invoices. The window closes this long after.
JOB_RELATED_CALLS_PER_JOB_WEIGHTS = {0: 20, 1: 35, 2: 25, 3: 20}
JOB_RELATED_WINDOW_AFTER_COMPLETION = timedelta(days=14)
CUSTOMER_STARTS_JOB_RELATED_CALL_SHARE = 0.60

# Now and then a past customer calls long after the job: a warranty
# question, a price check. Nothing gets booked.
LATER_QUESTION_SHARE = 0.08

# Suppliers, inspectors, subcontractors. Local numbers that call and get
# called for years but never become customers. Nobody keeps a list of them.
BUSINESS_CONTACTS_PER_LOCATION = {"Eastside": 16, "South Sound": 4}
BUSINESS_CONTACT_CALLS_PER_MONTH_RANGE = (1, 6)
BUSINESS_CONTACT_CALLS_IN_SHARE = 0.50

SPAM_CALLS_PER_DAY_WEIGHTS = {0: 60, 1: 30, 2: 10}  # for each open location
SPAM_AREA_CODES = ("800", "888", "877", "213", "305", "702", "646", "312", "480")

FORWARDING_DELAY_SECONDS = 11
BILLING_INCREMENT_SECONDS = 6
MINIMUM_BILLED_SECONDS = 18


class Direction(StrEnum):
    IN = "In"
    OUT = "Out"


class LegType(StrEnum):
    INBOUND_FORWARDED = "Inbound leg of forwarded call"
    FORWARD_CONNECTED = "Forwarded call connected"
    HANGUP = "Hangup"
    VOICE_MAIL = "Voice mail"
    MOBILE_INBOUND = "Mobile Inbound"
    MOBILE_OUTBOUND_CONNECTED = "Mobile Outbound Connected"
    MOBILE_OUTBOUND_NOT_CONNECTED = "Mobile Outbound Not Connected"


class CallPurpose(StrEnum):
    """Why a call really happened: the label attribution will be graded on."""

    NEW_CUSTOMER_LEAD = "new_customer_lead"
    RETURNING_CUSTOMER_LEAD = "returning_customer_lead"
    MISSED_CALL_CALLBACK = "missed_call_callback"
    WEB_FORM_FOLLOW_UP = "web_form_follow_up"
    VISIT_DAY = "visit_day"
    JOB_RELATED = "job_related"
    EXISTING_CUSTOMER_OTHER = "existing_customer_other"
    BUSINESS_CONTACT = "business_contact"
    SPAM = "spam"


@dataclass(frozen=True)
class OutsideParty:
    """Whoever is on the other end of a call, and which line they deal with."""

    phone_number: str
    location: Location
    customer_id: str | None = None
    lead_id: str | None = None


@dataclass(frozen=True)
class CallLeg:
    """One row of the Grasshopper export."""

    started_at: datetime
    business_line: str  # "VPS Number": the company line involved
    extension: str
    direction: Direction
    caller_id: str | None  # exported as "Unknown" when None
    connecting_number: str | None  # exported as "Unknown" when None
    billed_seconds: int
    leg_type: LegType


@dataclass(frozen=True)
class CallSession:
    """One real conversation (or attempt) and the legs logged for it.

    `purpose`, `customer_id`, and `lead_id` are the answer key for
    attribution. They never appear in the export; ingestion has to work
    them out from the legs alone.
    """

    purpose: CallPurpose
    external_number: str
    customer_id: str | None
    lead_id: str | None
    legs: tuple[CallLeg, ...]


def billed_seconds(actual_seconds: int) -> int:
    """Grasshopper bills in 6-second steps with an 18-second minimum."""
    if actual_seconds == 0:
        return 0
    rounded_up = math.ceil(actual_seconds / BILLING_INCREMENT_SECONDS) * BILLING_INCREMENT_SECONDS
    return max(MINIMUM_BILLED_SECONDS, rounded_up)


class PhoneSystemSimulator:
    """Turns the company history into the calls Grasshopper would have logged."""

    def __init__(self, randomness: random.Random):
        self._randomness = randomness

    def simulate(self, history: CompanyHistory) -> list[CallSession]:
        sessions: list[CallSession] = []

        for lead in history.leads:
            sessions.extend(self._calls_about_lead(lead))

        for job in history.jobs:
            sessions.extend(self._calls_about_job(job))

        for contact in self._invent_business_contacts(history):
            sessions.extend(self._calls_with_business_contact(contact))

        for day in simulated_days():
            for location in LOCATIONS:
                if day >= location.opened_month:
                    sessions.extend(self._spam_calls_on(day, location))

        return sessions

    # --- Leads -----------------------------------------------------------

    def _calls_about_lead(self, lead: Lead) -> list[CallSession]:
        if lead.contact_method is ContactMethod.PHONE_CALL:
            purpose = (
                CallPurpose.RETURNING_CUSTOMER_LEAD
                if lead.is_returning_customer
                else CallPurpose.NEW_CUSTOMER_LEAD
            )
            return self._inbound_call(
                self._customer_calling(lead.customer, lead),
                lead.created_at,
                purpose,
                callback_purpose=CallPurpose.MISSED_CALL_CALLBACK,
            )

        if self._chance(WEB_LEAD_CALLED_BACK_SHARE):
            called_at = lead.created_at + self._minutes_between(10, 240)
            return [self._owner_calls(self._customer_dialed(lead.customer, lead), called_at, CallPurpose.WEB_FORM_FOLLOW_UP)]

        return []

    # --- Existing customers ----------------------------------------------

    def _calls_about_job(self, job: Job) -> list[CallSession]:
        customer = job.lead.customer
        sessions: list[CallSession] = []

        for called_at in self._moments_during_job_window(job):
            if self._chance(CUSTOMER_STARTS_JOB_RELATED_CALL_SHARE):
                sessions.extend(
                    self._inbound_call(self._customer_calling(customer, job.lead), called_at, CallPurpose.JOB_RELATED)
                )
            else:
                sessions.append(
                    self._owner_calls(self._customer_dialed(customer, job.lead), called_at, CallPurpose.JOB_RELATED)
                )

        if job.completed_at is None:
            return sessions

        if self._chance(VISIT_DAY_CALL_SHARE):
            called_at = job.scheduled_start - self._minutes_between(30, 90)
            sessions.append(self._owner_calls(self._customer_dialed(customer, job.lead), called_at, CallPurpose.VISIT_DAY))

        if self._chance(LATER_QUESTION_SHARE):
            called_at = job.completed_at + timedelta(days=self._randomness.randint(60, 300))
            sessions.extend(
                self._inbound_call(self._customer_calling(customer, job.lead), called_at, CallPurpose.EXISTING_CUSTOMER_OTHER)
            )

        return sessions

    def _moments_during_job_window(self, job: Job) -> list[datetime]:
        """From the day after booking until the visit (canceled jobs) or two weeks after it."""
        window_ends_at = (
            job.completed_at + JOB_RELATED_WINDOW_AFTER_COMPLETION
            if job.completed_at is not None
            else job.scheduled_start
        )
        first_day = job.lead.created_at.date() + timedelta(days=1)
        days_in_window = max((window_ends_at.date() - first_day).days, 0)

        call_counts = list(JOB_RELATED_CALLS_PER_JOB_WEIGHTS)
        weights = list(JOB_RELATED_CALLS_PER_JOB_WEIGHTS.values())
        call_count = self._randomness.choices(call_counts, weights=weights)[0]
        return [
            random_moment_on_day(first_day + timedelta(days=self._randomness.randint(0, days_in_window)), self._randomness)
            for _ in range(call_count)
        ]

    def _customer_calling(self, customer: Customer, lead: Lead) -> OutsideParty:
        """Customers sometimes call from their second phone."""
        phone_number = customer.primary_phone
        if len(customer.phone_numbers) > 1 and self._chance(SECOND_PHONE_USED_SHARE):
            phone_number = customer.phone_numbers[1]
        return OutsideParty(phone_number, customer.location, customer.customer_id, lead.lead_id)

    def _customer_dialed(self, customer: Customer, lead: Lead) -> OutsideParty:
        """The owner dials the number on file, which is the primary one."""
        return OutsideParty(customer.primary_phone, customer.location, customer.customer_id, lead.lead_id)

    # --- Business contacts -----------------------------------------------

    def _invent_business_contacts(self, history: CompanyHistory) -> list[OutsideParty]:
        numbers_taken = {number for customer in history.customers for number in customer.phone_numbers}
        numbers_taken |= {location.business_phone_number for location in LOCATIONS}

        contacts = []
        for location in LOCATIONS:
            area_codes = sorted({area.phone_area_code for area in location.service_areas})
            for _ in range(BUSINESS_CONTACTS_PER_LOCATION[location.name]):
                phone_number = self._unused_local_number(self._randomness.choice(area_codes), numbers_taken)
                contacts.append(OutsideParty(phone_number, location))
        return contacts

    def _unused_local_number(self, area_code: str, numbers_taken: set[str]) -> str:
        while True:
            phone_number = f"+1{area_code}555{self._randomness.randint(0, 9999):04d}"
            if phone_number not in numbers_taken:
                numbers_taken.add(phone_number)
                return phone_number

    def _calls_with_business_contact(self, contact: OutsideParty) -> list[CallSession]:
        sessions: list[CallSession] = []
        for month in simulated_months():
            if month < contact.location.opened_month:
                continue
            for _ in range(self._randomness.randint(*BUSINESS_CONTACT_CALLS_PER_MONTH_RANGE)):
                called_at = random_moment_in_month(month, self._randomness)
                if self._chance(BUSINESS_CONTACT_CALLS_IN_SHARE):
                    sessions.extend(self._inbound_call(contact, called_at, CallPurpose.BUSINESS_CONTACT))
                else:
                    sessions.append(self._owner_calls(contact, called_at, CallPurpose.BUSINESS_CONTACT))
        return sessions

    # --- Spam, robocalls, wrong numbers ----------------------------------

    def _spam_calls_on(self, day: date, location: Location) -> list[CallSession]:
        call_counts = list(SPAM_CALLS_PER_DAY_WEIGHTS)
        weights = list(SPAM_CALLS_PER_DAY_WEIGHTS.values())
        call_count = self._randomness.choices(call_counts, weights=weights)[0]
        return [self._spam_call(day, location) for _ in range(call_count)]

    def _spam_call(self, day: date, location: Location) -> CallSession:
        area_code = self._randomness.choice(SPAM_AREA_CODES)
        spammer = OutsideParty(f"+1{area_code}555{self._randomness.randint(0, 9999):04d}", location)
        called_at = random_moment_on_day(day, self._randomness)
        if self._chance(0.5):
            legs = (self._leg(location, called_at, Direction.IN, spammer.phone_number, None,
                              self._randomness.randint(0, 15), LegType.HANGUP),)
        else:
            legs = self._answered_by_owner(spammer, called_at, talk_seconds=self._randomness.randint(5, 40))
        return self._session(CallPurpose.SPAM, spammer, legs)

    # --- Placing and routing calls ---------------------------------------

    def _inbound_call(
        self,
        caller: OutsideParty,
        called_at: datetime,
        purpose: CallPurpose,
        callback_purpose: CallPurpose | None = None,
    ) -> list[CallSession]:
        """An incoming call, plus the owner's callback if it was missed.

        The callback shares the call's purpose unless told otherwise: calling
        back a supplier is still supplier business.
        """
        legs, call_was_missed = self._route_inbound_call(caller, called_at)
        sessions = [self._session(purpose, caller, legs)]
        if call_was_missed and self._chance(MISSED_CALL_RETURNED_SHARE):
            callback_at = called_at + self._minutes_between(2, 90)
            sessions.append(self._owner_calls(caller, callback_at, callback_purpose or purpose))
        return sessions

    def _route_inbound_call(self, caller: OutsideParty, called_at: datetime) -> tuple[tuple[CallLeg, ...], bool]:
        """The legs Grasshopper logged, and whether the call was missed."""
        talk_seconds = self._talk_seconds(typical_seconds=150)
        roll = self._randomness.random()
        if roll < OWNER_ANSWERS_SHARE:
            return self._answered_by_owner(caller, called_at, talk_seconds), False
        if roll < OWNER_ANSWERS_SHARE + CALLER_HANGS_UP_WHILE_RINGING_SHARE:
            return self._caller_hung_up_while_ringing(caller, called_at), True
        if called_at.date() >= AI_CALL_TAKER_ADOPTED_ON:
            return self._rolled_over_to_ai_call_taker(caller, called_at, talk_seconds), False
        return self._went_to_voicemail(caller, called_at), True

    def _owner_calls(self, callee: OutsideParty, called_at: datetime, purpose: CallPurpose) -> CallSession:
        """A call placed from the Grasshopper app: the owner's cell rings in, then dials out."""
        location = callee.location
        connected = self._chance(OUTBOUND_CALL_CONNECTS_SHARE)
        talk_seconds = self._talk_seconds(typical_seconds=90) if connected else 0
        dialing_seconds = self._randomness.randint(1, 18)
        outbound_leg_type = (
            LegType.MOBILE_OUTBOUND_CONNECTED if connected else LegType.MOBILE_OUTBOUND_NOT_CONNECTED
        )
        legs = (
            self._leg(location, called_at, Direction.IN, OWNER_CELL_NUMBER, None,
                      talk_seconds + dialing_seconds, LegType.MOBILE_INBOUND),
            self._leg(location, called_at + timedelta(seconds=1), Direction.OUT, None, callee.phone_number,
                      talk_seconds, outbound_leg_type),
        )
        return self._session(purpose, callee, legs)

    def _answered_by_owner(self, caller: OutsideParty, called_at: datetime, talk_seconds: int) -> tuple[CallLeg, ...]:
        location = caller.location
        forwarded_at = called_at + timedelta(seconds=FORWARDING_DELAY_SECONDS)
        return (
            self._leg(location, called_at, Direction.IN, caller.phone_number, None,
                      talk_seconds + FORWARDING_DELAY_SECONDS, LegType.INBOUND_FORWARDED),
            self._leg(location, forwarded_at, Direction.OUT, None, OWNER_CELL_NUMBER,
                      talk_seconds, LegType.FORWARD_CONNECTED),
        )

    def _caller_hung_up_while_ringing(self, caller: OutsideParty, called_at: datetime) -> tuple[CallLeg, ...]:
        return (
            self._leg(caller.location, called_at, Direction.IN, caller.phone_number, None,
                      self._randomness.randint(4, 20), LegType.INBOUND_FORWARDED),
        )

    def _went_to_voicemail(self, caller: OutsideParty, called_at: datetime) -> tuple[CallLeg, ...]:
        location = caller.location
        forwarded_at = called_at + timedelta(seconds=FORWARDING_DELAY_SECONDS)
        return (
            self._leg(location, called_at, Direction.IN, caller.phone_number, None,
                      self._randomness.randint(30, 120), LegType.VOICE_MAIL),
            self._leg(location, forwarded_at, Direction.OUT, None, OWNER_CELL_NUMBER,
                      self._randomness.randint(5, 18), LegType.HANGUP),
        )

    def _rolled_over_to_ai_call_taker(
        self, caller: OutsideParty, called_at: datetime, talk_seconds: int
    ) -> tuple[CallLeg, ...]:
        location = caller.location
        owner_rang_at = called_at + timedelta(seconds=FORWARDING_DELAY_SECONDS)
        ai_answered_at = owner_rang_at + timedelta(seconds=self._randomness.randint(6, 30))
        seconds_before_ai = int((ai_answered_at - called_at).total_seconds())
        return (
            self._leg(location, called_at, Direction.IN, caller.phone_number, None,
                      seconds_before_ai + talk_seconds, LegType.INBOUND_FORWARDED),
            self._leg(location, owner_rang_at, Direction.OUT, None, OWNER_CELL_NUMBER,
                      self._randomness.randint(5, 18), LegType.HANGUP),
            self._leg(location, ai_answered_at, Direction.OUT, None, AI_CALL_TAKER_NUMBER,
                      talk_seconds, LegType.FORWARD_CONNECTED),
        )

    # --- Small building blocks -------------------------------------------

    def _session(self, purpose: CallPurpose, party: OutsideParty, legs: tuple[CallLeg, ...]) -> CallSession:
        return CallSession(purpose, party.phone_number, party.customer_id, party.lead_id, legs)

    def _leg(self, location, started_at, direction, caller_id, connecting_number, actual_seconds, leg_type) -> CallLeg:
        return CallLeg(
            started_at=started_at,
            business_line=location.business_phone_number,
            extension=EXTENSION_BY_LOCATION[location.name],
            direction=direction,
            caller_id=caller_id,
            connecting_number=connecting_number,
            billed_seconds=billed_seconds(actual_seconds),
            leg_type=leg_type,
        )

    def _talk_seconds(self, typical_seconds: int) -> int:
        """Mostly short calls, with the occasional long one; capped at 30 minutes."""
        seconds = self._randomness.lognormvariate(mu=math.log(typical_seconds), sigma=0.7)
        return min(round(seconds), 30 * 60)

    def _minutes_between(self, fewest: int, most: int) -> timedelta:
        return timedelta(minutes=self._randomness.randint(fewest, most), seconds=self._randomness.randint(0, 59))

    def _chance(self, probability: float) -> bool:
        return self._randomness.random() < probability
