"""Catches numbers a draft invented.

A draft may only use numbers that appear in its facts or notes. Numbers
are compared after normalizing how they're written: '$45,221' and '45221'
match, and '-42%' matches '42%', since prose drops the sign ('down 42%').
"""

import re

NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def invented_numbers(draft: str, source_text: str) -> list[str]:
    """Numbers in the draft that appear nowhere in the source, in order of appearance."""
    allowed = {_normalized(number) for number in NUMBER.findall(source_text)}
    invented = []
    for number in NUMBER.findall(draft):
        if _normalized(number) not in allowed and number not in invented:
            invented.append(number)
    return invented


def _normalized(number: str) -> str:
    """'1,208' -> '1208'; '42.0' -> '42'."""
    plain = number.replace(",", "")
    if "." in plain:
        plain = plain.rstrip("0").rstrip(".")
    return plain
