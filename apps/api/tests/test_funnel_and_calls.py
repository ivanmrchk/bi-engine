from datetime import date

from app.analysis.call_handling import CallHandlingMonth
from app.analysis.channel_funnel import ChannelFunnel


def funnel(leads=100, booked=70, real=50, revenue_cents=100_000, from_dropdown=0) -> ChannelFunnel:
    return ChannelFunnel("chatgpt", leads, 60, 40, booked, real, revenue_cents, from_dropdown)


def test_funnel_rates_are_shares_of_all_leads():
    channel = funnel(leads=100, booked=70, real=50, revenue_cents=100_000)

    assert channel.booking_rate == 0.7
    assert channel.close_rate == 0.5
    assert channel.revenue_per_lead_cents == 1_000


def test_a_channel_with_no_leads_has_no_rates():
    channel = funnel(leads=0, booked=0, real=0, revenue_cents=0)

    assert channel.booking_rate is None
    assert channel.revenue_per_lead_cents is None


def test_channels_known_only_from_the_office_dropdown_are_flagged():
    assert funnel(from_dropdown=12).rates_are_inflated
    assert not funnel(from_dropdown=0).rates_are_inflated


def test_unanswered_calls_are_voicemails_plus_missed_calls():
    month = CallHandlingMonth(
        month=date(2025, 3, 1), calls=80, answered_by_owner=44, answered_by_ai=0,
        voicemail=24, missed=12, unanswered_returned=30, median_minutes_to_callback=42.0,
    )

    assert month.unanswered == 36
    assert month.unanswered_share == 36 / 80
    assert month.never_returned == 6
