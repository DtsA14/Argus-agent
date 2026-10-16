"""Display formatting for amounts."""


def amount(cents, currency):
    """'EUR 1245.50' style text for an amount in cents (negative amounts get a leading '-')."""
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{currency} {sign}{cents // 100}.{cents % 100:02d}"
