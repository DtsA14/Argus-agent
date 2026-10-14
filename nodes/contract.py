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


def required_outputs(contract):
    return sorted(k for k, v in contract["outputs"].items() if v["required"])


def allowed_outputs(contract):
    return sorted(contract["outputs"])
