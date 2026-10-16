"""Parse inventory CSV text: one "sku,quantity" pair per line."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Row:
    line: int
    sku: str
    qty: int


@dataclass(frozen=True)
class Problem:
    line: int
    reason: str


def parse(text):
    """(rows, problems). Blank lines are skipped. A line that is not exactly two comma-separated fields, or whose
    quantity is not a whole number, becomes a Problem; parsing never raises. Line numbers start at 1."""
    rows, problems = [], []
    for n, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        parts = [p.strip() for p in raw.split(",")]
        if len(parts) != 2:
            problems.append(Problem(n, "expected two fields: sku,quantity"))
            continue
        sku, qty = parts
        try:
            rows.append(Row(n, sku, int(qty)))
        except ValueError:
            problems.append(Problem(n, f"quantity {qty!r} is not a whole number"))
    return rows, problems
