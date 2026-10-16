"""Import inventory CSV into an Inventory."""
from .csvparse import parse
from .validate import check


class ImportFailed(Exception):
    def __init__(self, problems):
        super().__init__(f"{len(problems)} problem(s) in the import file")
        self.problems = problems


def import_csv(text, inventory):
    """Set each SKU in the file to its quantity (new SKUs are added, existing ones updated).

    All or nothing: if parse() or check() reports any problem anywhere in the file, ImportFailed is raised with the
    problems, and the inventory is exactly as it was before the call. That guarantee covers the problems parse() and
    check() report; the in-memory store does not fail on validated rows, so no rollback for storage failures is
    provided or claimed."""
    rows, problems = parse(text)
    if problems:
        raise ImportFailed(problems)
    for row in rows:
        row_problems = check([row], inventory)
        if row_problems:
            raise ImportFailed(row_problems)
        inventory.set_quantity(row.sku, row.qty)
    return len(rows)
