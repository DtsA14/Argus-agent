"""Phase 3b: the fact table and the rules that tie every number in a recommendation to a fact.

Contract: docs/MILESTONE3_PLAN.md, section 3.6. The model may write; the harness verifies.
- The fact table is built by the harness, never by the model. Derived facts use Decimal (no float) and are left
  out when their denominator is zero, so a reference to them fails as "unknown fact".
- Every rendered text (`text` and `action`) may only contain numbers in the canonical format, and each must match
  a fact the recommendation references. Anything else is rejected with an error that names the right format.
The same functions check the writer's output (against facts from the workers' results) and, in the evaluator,
the provenance of the finished report (against facts recomputed from the data).
"""
import re
from decimal import ROUND_HALF_UP, Decimal

MONTH_TOKEN = re.compile(r"(?<!\d)(\d{4})-(\d{2})(?!\d)")
DIGIT_RUN = re.compile(r"\d[\d.,]*")                  # every digit, including separators that make it ambiguous
CANONICAL = re.compile(r"\d+(?:\.\d)?")               # plain digits, or one decimal (percentages only)
MIN_RECS, MAX_RECS = 2, 5
MAX_TEXT, MAX_ACTION = 300, 200
FORMAT_HELP = ("write months as YYYY-MM, rupiah as plain digits without separators (4200000), and percentages "
               "with % and at most one decimal, using a dot (72% or 72.4%)")


def round_half_up(value, places):
    return Decimal(value).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def _fact(fid, value, unit, source, **extra):
    return fid, {"id": fid, "value": value, "unit": unit, "source": source, **extra}


def build_facts(top3, trend):
    """{fact_id: fact} from Top 3 [[product, revenue], ...] and trend [[YYYY-MM, revenue], ...] (oldest first)."""
    facts = {}
    for i, (product, revenue) in enumerate(top3 or [], 1):
        facts.update([_fact(f"top3.{i}.product", str(product), "product", "top3"),
                      _fact(f"top3.{i}.revenue", int(revenue), "IDR", "top3")])
    for month, revenue in trend or []:
        facts.update([_fact(f"trend.{month}.revenue", int(revenue), "IDR", "trend", month=str(month))])

    if top3 and len(top3) >= 2:
        total = sum(Decimal(int(v)) for _, v in top3)
        if total != 0:
            share = (Decimal(int(top3[0][1])) + Decimal(int(top3[1][1]))) / total * 100
            facts.update([_fact("top3.top2_share_of_top3_pct", share, "pct",
                                "(top3.1.revenue + top3.2.revenue) / sum of Top 3 revenue x 100")])
    if trend and len(trend) >= 2:
        first, last = Decimal(int(trend[0][1])), Decimal(int(trend[-1][1]))
        if first != 0:
            facts.update([_fact("trend.first_to_last_growth_pct", (last - first) / first * 100, "pct",
                                f"(revenue {trend[-1][0]} - revenue {trend[0][0]}) / revenue {trend[0][0]} x 100")])
    return facts


def fact_line(f):
    """How a fact is shown to the model: percentages rounded to one decimal (the exact value stays in the table)."""
    value = f"{round_half_up(f['value'], 1)}%" if f["unit"] == "pct" else f["value"]
    return f"{f['id']} = {value}" + ("" if f["unit"] in ("pct", "product") else f" ({f['unit']})")


def check_numbers(text, facts, refs):
    """Errors for every number in `text` that is not canonical or matches no referenced fact."""
    errors = []
    referenced = [facts[r] for r in refs if r in facts]
    months = {f["month"] for f in referenced if "month" in f}
    # GPT review 3b: a product name may contain digits ("Model 3", "iPhone 15"). Digits inside the exact name of a
    # referenced product fact are backed by that fact, so the name is masked out first (longest first, so a longer
    # name is never half-masked by a shorter one). Unreferenced, partial or re-cased names are not masked, and the
    # name must stand as its own token (GPT re-review: "Model 3x" or "XModel 3" is not the product "Model 3").
    for name in sorted((f["value"] for f in referenced if f["unit"] == "product"), key=len, reverse=True):
        text = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", " ", text)
    for m in MONTH_TOKEN.finditer(text):
        token, month = m.group(0), int(m.group(2))
        if not 1 <= month <= 12:
            errors.append(f"{token!r} is not a month (write months as YYYY-MM)")
        elif token not in months:
            errors.append(f"month {token} is not one of the referenced trend facts")
    rest = MONTH_TOKEN.sub(" ", text)
    # Every run of digits is checked, wherever it stands: a number glued to letters ("Rp4200000", "top3") must
    # not slip past a word-boundary regex.
    for m in DIGIT_RUN.finditer(rest):
        digits = m.group(0).rstrip(".,")                       # sentence punctuation after a number
        start, end = m.start(), m.start() + len(digits)
        pct = "%" if rest[end:end + 1] == "%" else ""
        before = rest[start - 1:start] if start else ""
        sign = "-" if before == "-" and (start < 2 or rest[start - 2] in " (") else ""
        token = sign + digits + pct
        if not CANONICAL.fullmatch(digits) or ("." in digits and not pct):
            errors.append(f"{token!r} is not canonical; {FORMAT_HELP}")
            continue
        value = Decimal(sign + digits)
        if pct:
            places = len(digits.split(".")[1]) if "." in digits else 0
            ok = any(f["unit"] == "pct" and round_half_up(f["value"], places) == value for f in referenced)
            if not ok:
                errors.append(f"{token} matches no referenced percentage fact")
        elif sign or not any(f["unit"] == "IDR" and Decimal(f["value"]) == value for f in referenced):
            errors.append(f"{token} matches no referenced fact (rupiah must equal a fact exactly; percentages need %)")
    return errors


def validate_recommendations(args, facts):
    """(recommendations, []) when every rule holds, else (None, [error, ...]) the model can act on."""
    recs = (args or {}).get("recommendations")
    if not isinstance(recs, list):
        return None, ["'recommendations' must be a list"]
    errors = []
    if not MIN_RECS <= len(recs) <= MAX_RECS:
        errors.append(f"{len(recs)} recommendations; give {MIN_RECS} to {MAX_RECS}")
    seen = set()
    for i, r in enumerate(recs, 1):
        if not isinstance(r, dict):
            errors.append(f"recommendation {i}: must be an object with text, action and facts")
            continue
        text, action, refs = r.get("text"), r.get("action"), r.get("facts")
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
            errors.append(f"recommendation {i}: 'text' must be 1 to {MAX_TEXT} characters")
            text = text if isinstance(text, str) else ""
        if not isinstance(action, str) or not action.strip() or len(action) > MAX_ACTION:
            errors.append(f"recommendation {i}: 'action' must be 1 to {MAX_ACTION} characters")
            action = action if isinstance(action, str) else ""
        if "\n" in text or "\n" in action:
            errors.append(f"recommendation {i}: text and action must be single lines")
        if not isinstance(refs, list) or not refs or not all(isinstance(x, str) for x in refs):
            errors.append(f"recommendation {i}: 'facts' must list at least one fact id")
            refs = []
        unknown = [x for x in refs if x not in facts]
        if unknown:
            errors.append(f"recommendation {i}: unknown fact ids {unknown}")
        for where, s in (("text", text), ("action", action)):    # both are rendered, so both are checked
            errors += [f"recommendation {i} {where}: {e}" for e in check_numbers(s, facts, refs)]
        key = " ".join(text.lower().split())
        if key and key in seen:
            errors.append(f"recommendation {i}: repeats an earlier recommendation")
        seen.add(key)
    if errors:
        return None, errors
    return [{"text": r["text"].strip(), "action": r["action"].strip(), "facts": list(r["facts"])} for r in recs], []


def render_line(i, rec):
    return f"{i}. {rec['text']} Aksi: {rec['action']}"
