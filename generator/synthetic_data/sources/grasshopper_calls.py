"""What the Grasshopper phone system did: every call, broken into legs.

Grasshopper doesn't log conversations, it logs *legs*. A customer calling
in is one inbound leg, plus an outbound leg each time the call is
forwarded: first to the owner's cell and, if nobody picks up, on to
Housecall Pro's AI call taker. A call the owner places from the Grasshopper
app shows up as an inbound leg *from the owner's own cell* plus an
outbound leg to the customer.
"""

import math
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum

from synthetic_data.calibration import LOCATIONS, Location
from synthetic_data.customers import Customer
from synthetic_data.jobs import CompanyHistory, ContactMethod, Job, Lead
from synthetic_data.timeline import random_moment_on_day, simulated_days

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
    NEW_LEAD = "new_lead"    # a lead phoning in
    CALLBACK = "callback"    # the owner returning a missed call or a web form
    VISIT_DAY = "visit_day"  # the owner calling ahead of a scheduled visit
    SPAM = "spam"


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

    `customer_id` and `lead_id` are the answer key for attribution. They
    never appear in the export; ingestion has to work them out.
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
            if lead.contact_method is ContactMethod.PHONE_CALL:
                sessions.extend(self._lead_phones_in(lead))
            elif self._chance(WEB_LEAD_CALLED_BACK_SHARE):
                sessions.append(self._owner_returns_web_form(lead))

        for job in history.jobs:
            if job.completed_at is not None and self._chance(VISIT_DAY_CALL_SHARE):
                sessions.append(self._owner_calls_ahead_of_visit(job))

        for day in simulated_days():
            for location in LOCATIONS:
                if day >= location.opened_month:
                    sessions.extend(self._spam_calls_on(day, location))

        return sessions

    # --- Calls from customers --------------------------------------------

    def _lead_phones_in(self, lead: Lead) -> list[CallSession]:
        """The lead's call, followed by the owner's callback if it was missed."""
        customer = lead.customer
        location = customer.location
        caller_number = self._number_customer_calls_from(customer)
        called_at = lead.created_at
        talk_seconds = self._talk_seconds(typical_seconds=150)

        roll = self._randomness.random()
        call_was_missed = False
        if roll < OWNER_ANSWERS_SHARE:
            legs = self._answered_by_owner(location, caller_number, called_at, talk_seconds)
        elif roll < OWNER_ANSWERS_SHARE + CALLER_HANGS_UP_WHILE_RINGING_SHARE:
            legs = self._caller_hung_up_while_ringing(location, caller_number, called_at)
            call_was_missed = True
        elif called_at.date() >= AI_CALL_TAKER_ADOPTED_ON:
            legs = self._rolled_over_to_ai_call_taker(location, caller_number, called_at, talk_seconds)
        else:
            legs = self._went_to_voicemail(location, caller_number, called_at)
            call_was_missed = True

        sessions = [CallSession(CallPurpose.NEW_LEAD, caller_number, customer.customer_id, lead.lead_id, legs)]
        if call_was_missed and self._chance(MISSED_CALL_RETURNED_SHARE):
            callback_at = called_at + self._minutes_between(2, 90)
            sessions.append(
                self._owner_calls(location, caller_number, callback_at, CallPurpose.CALLBACK, customer, lead)
            )
        return sessions

    def _number_customer_calls_from(self, customer: Customer) -> str:
        has_second_phone = len(customer.phone_numbers) > 1
        if has_second_phone and self._chance(SECOND_PHONE_USED_SHARE):
            return customer.phone_numbers[1]
        return customer.primary_phone

    # --- Calls from the owner --------------------------------------------

    def _owner_returns_web_form(self, lead: Lead) -> CallSession:
        called_at = lead.created_at + self._minutes_between(10, 240)
        customer = lead.customer
        return self._owner_calls(
            customer.location, customer.primary_phone, called_at, CallPurpose.CALLBACK, customer, lead
        )

    def _owner_calls_ahead_of_visit(self, job: Job) -> CallSession:
        called_at = job.scheduled_start - self._minutes_between(30, 90)
        customer = job.lead.customer
        return self._owner_calls(
            customer.location, customer.primary_phone, called_at, CallPurpose.VISIT_DAY, customer, job.lead
        )

    def _owner_calls(
        self,
        location: Location,
        customer_number: str,
        called_at: datetime,
        purpose: CallPurpose,
        customer: Customer,
        lead: Lead,
    ) -> CallSession:
        """A call placed from the Grasshopper app: the owner's cell rings in, then dials out."""
        connected = self._chance(OUTBOUND_CALL_CONNECTS_SHARE)
        talk_seconds = self._talk_seconds(typical_seconds=90) if connected else 0
        dialing_seconds = self._randomness.randint(1, 18)
        legs = (
            self._leg(location, called_at, Direction.IN, OWNER_CELL_NUMBER, None,
                      talk_seconds + dialing_seconds, LegType.MOBILE_INBOUND),
            self._leg(location, called_at + timedelta(seconds=1), Direction.OUT, None, customer_number,
                      talk_seconds,
                      LegType.MOBILE_OUTBOUND_CONNECTED if connected else LegType.MOBILE_OUTBOUND_NOT_CONNECTED),
        )
        return CallSession(purpose, customer_number, customer.customer_id, lead.lead_id, legs)

    # --- Spam, robocalls, wrong numbers ----------------------------------

    def _spam_calls_on(self, day: date, location: Location) -> list[CallSession]:
        call_counts = list(SPAM_CALLS_PER_DAY_WEIGHTS)
        weights = list(SPAM_CALLS_PER_DAY_WEIGHTS.values())
        call_count = self._randomness.choices(call_counts, weights=weights)[0]
        return [self._spam_call(day, location) for _ in range(call_count)]

    def _spam_call(self, day: date, location: Location) -> CallSession:
        area_code = self._randomness.choice(SPAM_AREA_CODES)
        caller_number = f"+1{area_code}555{self._randomness.randint(0, 9999):04d}"
        called_at = random_moment_on_day(day, self._randomness)
        if self._chance(0.5):
            legs = (self._leg(location, called_at, Direction.IN, caller_number, None,
                              self._randomness.randint(0, 15), LegType.HANGUP),)
        else:
            talk_seconds = self._randomness.randint(5, 40)
            legs = self._answered_by_owner(location, caller_number, called_at, talk_seconds)
        return CallSession(CallPurpose.SPAM, caller_number, None, None, legs)

    # --- How an inbound call is routed, leg by leg ------------------------

    def _answered_by_owner(self, location, caller_number, called_at, talk_seconds) -> tuple[CallLeg, ...]:
        forwarded_at = called_at + timedelta(seconds=FORWARDING_DELAY_SECONDS)
        return (
            self._leg(location, called_at, Direction.IN, caller_number, None,
                      talk_seconds + FORWARDING_DELAY_SECONDS, LegType.INBOUND_FORWARDED),
            self._leg(location, forwarded_at, Direction.OUT, None, OWNER_CELL_NUMBER,
                      talk_seconds, LegType.FORWARD_CONNECTED),
        )

    def _caller_hung_up_while_ringing(self, location, caller_number, called_at) -> tuple[CallLeg, ...]:
        return (
            self._leg(location, called_at, Direction.IN, caller_number, None,
                      self._randomness.randint(4, 20), LegType.INBOUND_FORWARDED),
        )

    def _went_to_voicemail(self, location, caller_number, called_at) -> tuple[CallLeg, ...]:
        forwarded_at = called_at + timedelta(seconds=FORWARDING_DELAY_SECONDS)
        return (
            self._leg(location, called_at, Direction.IN, caller_number, None,
                      self._randomness.randint(30, 120), LegType.VOICE_MAIL),
            self._leg(location, forwarded_at, Direction.OUT, None, OWNER_CELL_NUMBER,
                      self._randomness.randint(5, 18), LegType.HANGUP),
        )

    def _rolled_over_to_ai_call_taker(self, location, caller_number, called_at, talk_seconds) -> tuple[CallLeg, ...]:
        owner_rang_at = called_at + timedelta(seconds=FORWARDING_DELAY_SECONDS)
        ai_answered_at = owner_rang_at + timedelta(seconds=self._randomness.randint(6, 30))
        seconds_before_ai = int((ai_answered_at - called_at).total_seconds())
        return (
            self._leg(location, called_at, Direction.IN, caller_number, None,
                      seconds_before_ai + talk_seconds, LegType.INBOUND_FORWARDED),
            self._leg(location, owner_rang_at, Direction.OUT, None, OWNER_CELL_NUMBER,
                      self._randomness.randint(5, 18), LegType.HANGUP),
            self._leg(location, ai_answered_at, Direction.OUT, None, AI_CALL_TAKER_NUMBER,
                      talk_seconds, LegType.FORWARD_CONNECTED),
        )

    # --- Small building blocks -------------------------------------------

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
