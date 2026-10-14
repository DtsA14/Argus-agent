"""What a task must deliver, defined by the harness (not by the model).

The orchestrator may split the work however it likes, but its plan must cover every required output
exactly once. Synthesize and the evaluator look results up by output name, so task ids are free to
change between iterations.
"""

SALES_REPORT = {
    "name": "sales_report",
    "data": {
        "file": "penjualan.csv",
        "columns": {"month": "YYYY-MM", "product": "product name", "omzet": "revenue in rupiah (integer)"},
        "notes": "One row per (month, product). Revenue must be summed, never averaged.",
    },
    "outputs": {
        "data_check": {
            "required": False,
            "description": "Validation summary: row count, distinct months, distinct products, missing values.",
        },
        "top3": {
            "required": True,
            "description": "The 3 products with the highest total revenue over all months, as a list of "
                           "[product, total_revenue] pairs, highest first.",
        },
        "trend": {
            "required": True,
            "description": "Total revenue per month for every month in the data, as a list of "
                           "[YYYY-MM, total_revenue] pairs, oldest first.",
        },
    },
    "report": "laporan.md with sections: Top 3 Produk, Tren Bulanan, Rekomendasi (2 recommendations backed by numbers).",
}


def _pairs(value, name, *, first, exact=None):
    """A list of [label, non-negative int] pairs; returns error strings."""
    if not isinstance(value, list) or not value:
        return [f"{name} must be a non-empty list of [{first}, total_revenue] pairs"]
    errors = []
    if exact is not None and len(value) != exact:
        errors.append(f"{name} must have exactly {exact} entries, got {len(value)}")
    for i, item in enumerate(value):
        if not (isinstance(item, list) and len(item) == 2):
            errors.append(f"{name}[{i}] must be a [{first}, total_revenue] pair")
            continue
        label, amount = item
        if not isinstance(label, str) or not label:
            errors.append(f"{name}[{i}][0] must be a non-empty string")
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            errors.append(f"{name}[{i}][1] must be a non-negative integer (rupiah, not a float)")
    return errors


def validate_output(name, value):
    """Shape checks the harness applies to a worker's SubmitResult. Correctness is the evaluator's job."""
    import re
    if name == "top3":
        errors = _pairs(value, "top3", first="product", exact=3)
        if not errors and [v for _, v in value] != sorted((v for _, v in value), reverse=True):
            errors.append("top3 must be ordered from highest to lowest revenue")
        return errors
    if name == "trend":
        errors = _pairs(value, "trend", first="YYYY-MM")
        if not errors:
            months = [m for m, _ in value]
            bad = [m for m in months if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", m)]
            if bad:
                errors.append(f"trend months must be YYYY-MM, got {bad}")
            elif months != sorted(months) or len(set(months)) != len(months):
                errors.append("trend months must be unique and ordered oldest first")
        return errors
    if name == "data_check":
        return [] if isinstance(value, dict) and value else ["data_check must be a non-empty object"]
    return [f"unknown output {name!r}"]


def required_outputs(contract):
    return sorted(k for k, v in contract["outputs"].items() if v["required"])


def allowed_outputs(contract):
    return sorted(contract["outputs"])
