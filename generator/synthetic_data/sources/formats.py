"""How real systems and real people distort clean values.

The truth stores every phone number as E.164 and every city with one
spelling. Real exports don't, and these helpers reproduce that mess.
"""

import random
import re
from datetime import datetime, timezone


def url_slug(text: str) -> str:
    """'Outlet & Switch Installation' -> 'outlet-and-switch-installation'."""
    text = text.lower().replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def utc_timestamp(moment: datetime | None) -> str | None:
    """ISO 8601 in UTC with a trailing Z, the way most JSON APIs send time."""
    if moment is None:
        return None
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def phone_as_typed_by_a_person(e164_phone: str, randomness: random.Random) -> str:
    """+14255550142 rewritten in one of the formats people actually type."""
    area_code, exchange, line = e164_phone[2:5], e164_phone[5:8], e164_phone[8:]
    formats_and_weights = (
        (f"{area_code}{exchange}{line}", 50),
        (f"({area_code}) {exchange}-{line}", 15),
        (f"{area_code}-{exchange}-{line}", 15),
        (f"{area_code}.{exchange}.{line}", 10),
        (f"+1 {area_code} {exchange} {line}", 5),
        (f"1{area_code}{exchange}{line}", 5),
    )
    formats = [phone for phone, _ in formats_and_weights]
    weights = [weight for _, weight in formats_and_weights]
    return randomness.choices(formats, weights=weights)[0]


def city_as_typed_by_a_person(city: str, randomness: random.Random) -> str | None:
    """Mostly correct, sometimes SHOUTED, lowercased, padded, or missing."""
    roll = randomness.random()
    if roll < 0.03:
        return None
    if roll < 0.13:
        return city.upper()
    if roll < 0.18:
        return city.lower()
    if roll < 0.21:
        return f"{city} "
    return city
