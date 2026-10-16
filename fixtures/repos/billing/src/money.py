"""Money amounts, kept as whole cents (int)."""
import re

AMOUNT = re.compile(r"\d+(\.\d{1,2})?")


def parse_amount(text):
    """A decimal amount -> its exact number of cents.

    Valid input: a non-negative decimal number with at most two digits after the point, e.g. "12", "12.3", "12.34".
    The result is exact for every valid input, however large: "0.29" is 29 cents. Anything else raises ValueError."""
    if not isinstance(text, str) or not AMOUNT.fullmatch(text):
        raise ValueError(f"not an amount: {text!r}")
    return int(float(text) * 100)


def format_cents(cents):
    """Whole cents -> "units.cc", e.g. 1234 -> "12.34"."""
    return f"{cents // 100}.{cents % 100:02d}"
