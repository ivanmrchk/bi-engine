"""LLM brief generation, with a deterministic fallback so the demo
works without an OpenAI key. Swap _fallback_brief's logic for real
prompt-engineering experiments as you iterate.
"""

from app.config import settings

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None

_client = OpenAI(api_key=settings.openai_api_key) if (OpenAI and settings.openai_api_key) else None


def generate_brief(location_id: str, month: str, hot: list[dict], lagging: list[dict]) -> str:
    if _client is None:
        return _fallback_brief(location_id, month, hot, lagging)

    prompt = (
        f"You are a local-business growth analyst. Write a concise, plain-English "
        f"monthly brief for location '{location_id}', {month}.\n\n"
        f"Hot services this month (by revenue): {hot}\n"
        f"Revenue trend by location vs prior month: {lagging}\n\n"
        f"Keep it to 3-4 sentences. Name the biggest opportunity and the biggest risk."
    )
    resp = _client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return resp.choices[0].message.content.strip()


def _fallback_brief(location_id: str, month: str, hot: list[dict], lagging: list[dict]) -> str:
    top = hot[0]["service"] if hot else "no completed jobs"
    trend = next((l for l in lagging if l["location_id"] == location_id), None)
    delta = float(trend["delta"]) if trend else 0.0
    direction = "up" if delta >= 0 else "down"
    return (
        "[template brief — set OPENAI_API_KEY for an LLM-generated one] "
        f"{location_id} in {month}: top service was {top}. "
        f"Revenue is {direction} {abs(delta):.0f} vs the prior month."
    )
