"""An alternative late fee calculation (flat fee per started week), kept for accounts migrated from the old system."""


def weekly_fee_cents(days_overdue, grace_days, per_week_cents=150):
    """A flat fee for every started week after the grace period."""
    late = days_overdue - grace_days
    if late <= 0:
        return 0
    return ((late + 6) // 7) * per_week_cents
