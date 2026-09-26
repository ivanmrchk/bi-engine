"""Customers of the fictional company: who they are and where they live.

This module describes the *truth*. Each data source (Housecall Pro, call
tracking, ...) later renders these customers in its own format, with its
own quirks, which is exactly what the ingestion layer has to untangle.
"""

import random
from dataclasses import dataclass
from itertools import count

from faker import Faker

from synthetic_data.calibration import LOCATIONS, SECOND_PHONE_SHARE, Location, ServiceArea


@dataclass(frozen=True)
class Customer:
    customer_id: str
    first_name: str
    last_name: str
    email: str
    phone_numbers: tuple[str, ...]  # E.164 format (+14255550142), primary first
    street_address: str
    location: Location
    service_area: ServiceArea
    zip_code: str

    @property
    def primary_phone(self) -> str:
        return self.phone_numbers[0]


class CustomerFactory:
    """Creates believable, unique customers spread across a location's cities."""

    def __init__(self, randomness: random.Random, fake: Faker):
        self._randomness = randomness
        self._fake = fake
        self._next_customer_number = count(start=1)
        # Business lines are taken, so no customer can share one.
        self._phone_numbers_in_use = {location.business_phone_number for location in LOCATIONS}

    def create_customer(self, location: Location) -> Customer:
        service_area = self._pick_service_area(location)
        first_name = self._fake.first_name()
        last_name = self._fake.last_name()

        phone_numbers = [self._new_phone_number(service_area.phone_area_code)]
        if self._randomness.random() < SECOND_PHONE_SHARE:
            phone_numbers.append(self._new_phone_number(service_area.phone_area_code))

        return Customer(
            customer_id=f"cus_{next(self._next_customer_number):05d}",
            first_name=first_name,
            last_name=last_name,
            email=self._email_for(first_name, last_name),
            phone_numbers=tuple(phone_numbers),
            street_address=self._fake.street_address(),
            location=location,
            service_area=service_area,
            zip_code=self._randomness.choice(service_area.zip_codes),
        )

    def _pick_service_area(self, location: Location) -> ServiceArea:
        weights = [area.share_of_location_customers for area in location.service_areas]
        return self._randomness.choices(location.service_areas, weights=weights)[0]

    def _new_phone_number(self, area_code: str) -> str:
        """A unique number on the 555 exchange, which is reserved for fiction."""
        while True:
            phone_number = f"+1{area_code}555{self._randomness.randint(0, 9999):04d}"
            if phone_number not in self._phone_numbers_in_use:
                self._phone_numbers_in_use.add(phone_number)
                return phone_number

    def _email_for(self, first_name: str, last_name: str) -> str:
        """example.com and friends are reserved domains, so no email is ever real."""
        domain = self._randomness.choice(("example.com", "example.net", "example.org"))
        suffix = self._randomness.randint(1, 99)
        return f"{first_name}.{last_name}{suffix}@{domain}".lower()
