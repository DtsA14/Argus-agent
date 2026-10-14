"""Sales data loading and ground-truth computation (used by tools and the evaluator)."""
import csv
from collections import defaultdict
from pathlib import Path

CSV_PATH = Path(__file__).parent / "data" / "penjualan.csv"


def load_rows(path=CSV_PATH):
    with open(path, newline="", encoding="utf-8") as f:
        return [
            {"month": r["month"], "product": r["product"], "omzet": int(r["omzet"])}
            for r in csv.DictReader(f)
        ]


def product_totals(rows):
    totals = defaultdict(int)
    for r in rows:
        totals[r["product"]] += r["omzet"]
    return dict(totals)


def monthly_totals(rows):
    totals = defaultdict(int)
    for r in rows:
        totals[r["month"]] += r["omzet"]
    return dict(totals)


def truth(rows=None):
    rows = rows or load_rows()
    top3 = sorted(product_totals(rows).items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    trend = sorted(monthly_totals(rows).items())
    return {"top3": top3, "trend": trend, "products": sorted(product_totals(rows))}
