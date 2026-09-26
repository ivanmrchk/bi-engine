"""Builds the whole synthetic dataset from a single seed.

Each part gets its own random stream derived from the seed, so changing
how one source is generated never shifts the numbers in another.
"""

import random
from dataclasses import dataclass

from faker import Faker

from synthetic_data.customers import CustomerFactory
from synthetic_data.jobs import CompanyHistory, CompanyHistoryGenerator
from synthetic_data.sources.grasshopper_calls import CallSession, PhoneSystemSimulator
from synthetic_data.sources.grasshopper_csv import ExportFile, export_grasshopper_reports
from synthetic_data.sources.housecall_pro import HousecallProExport, export_housecall_pro
from synthetic_data.sources.search_console import SearchConsoleDay, export_search_console
from synthetic_data.sources.website_leads import WebsiteLeadsExport, export_website_leads


@dataclass(frozen=True)
class Dataset:
    history: CompanyHistory
    call_sessions: list[CallSession]
    housecall_pro: HousecallProExport
    grasshopper_reports: list[ExportFile]
    website_leads: WebsiteLeadsExport
    search_console_days: list[SearchConsoleDay]


def build_dataset(seed: int) -> Dataset:
    def randomness_for(part: str) -> random.Random:
        return random.Random(f"{seed}:{part}")

    fake = Faker("en_US")
    fake.seed_instance(seed)

    customer_factory = CustomerFactory(randomness_for("customers"), fake)
    history = CompanyHistoryGenerator(randomness_for("history"), customer_factory).generate()
    call_sessions = PhoneSystemSimulator(randomness_for("phone_system")).simulate(history)

    return Dataset(
        history=history,
        call_sessions=call_sessions,
        housecall_pro=export_housecall_pro(history, randomness_for("housecall_pro")),
        grasshopper_reports=export_grasshopper_reports(call_sessions, randomness_for("grasshopper_reports")),
        website_leads=export_website_leads(history, randomness_for("website_leads")),
        search_console_days=export_search_console(randomness_for("search_console")),
    )
