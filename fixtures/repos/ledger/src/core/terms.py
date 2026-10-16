"""Payment terms: a grace period, then a late fee."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Terms:
    grace_days: int
    fee_percent: int
    min_fee_cents: int


def terms_from(options):
    """Terms from an options dict that has every field."""
    return Terms(int(options["grace_days"]), int(options["fee_percent"]), int(options["min_fee_cents"]))


def late_fee_cents(amount_cents, days_overdue, terms):
    """The late fee on an unpaid amount: none within the grace period, then a percentage with a minimum."""
    if days_overdue <= terms.grace_days:
        return 0
    return max(terms.min_fee_cents, amount_cents * terms.fee_percent // 100)
