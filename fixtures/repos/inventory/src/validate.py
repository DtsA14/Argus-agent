"""Rules every imported row must follow."""
from .csvparse import Problem


def check(rows, inventory):
    """Problems with these rows, or []. Rules:
    - the SKU is not empty;
    - the quantity is zero or more;
    - a SKU appears at most once among the rows (an import file may not set the same SKU twice).
    A SKU that already exists in the inventory may appear (once): the import updates it."""
    problems, seen = [], set()
    for row in rows:
        if not row.sku:
            problems.append(Problem(row.line, "empty SKU"))
        if row.qty < 0:
            problems.append(Problem(row.line, f"negative quantity for {row.sku}"))
        if row.sku in seen and inventory.has(row.sku):
            problems.append(Problem(row.line, f"SKU {row.sku} appears more than once"))
        seen.add(row.sku)
    return problems
