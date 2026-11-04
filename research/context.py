"""SPEC_FROM_RESEARCH 3-4: the research context of `argus code --from-research`, built by the harness from a finished
research job's files (no model). Only report items e1 judged SUPPORTED go in, each with the quotes it cites (which
passed G1 and G2 in that run); every model and web text is fenced. Nothing is cut: too large is refused."""
import hashlib
import json
from pathlib import Path

from acceptance import contract as ct
from codetask.review import fence

from .report import check_items

FILES = ("job.json", "report.json", "check.json", "findings.json")
SUPPORTED = "SUPPORTED"


class ContextError(Exception):
    pass


def _load(raw, d, name):
    """The bytes already read (and hashed) for the record, parsed: never a second read."""
    try:
        return json.loads(raw[name].decode("utf-8"))
    except ValueError as e:
        raise ContextError(f"research job {d.name}: {name} cannot be read ({e})") from e


def build(job_dir, items=None):
    """(text, record) for the research job at job_dir. items: ids to take among the SUPPORTED ones; None takes them
    all. ContextError when the job is not a finished, checked research job, an item is not SUPPORTED or does not exist,
    or the text is longer than ct.MAX_RESEARCH."""
    from router.research import REPORT_READY             # router imports this module; imported here to avoid a cycle
    d = Path(job_dir)
    raw = {}
    for name in FILES:
        try:
            raw[name] = (d / name).read_bytes()
        except OSError as e:
            raise ContextError(f"research job {d.name}: no {name} ({e.strerror})") from e
    job = _load(raw, d, "job.json")
    if job.get("kind") != "research":
        raise ContextError(f"job {d.name} is a {job.get('kind')!r} job, not a research job")
    if job.get("state") != REPORT_READY:
        raise ContextError(f"research job {d.name} is {job.get('state')}, not {REPORT_READY}")
    check = _load(raw, d, "check.json")
    if check.get("status") != "CHECKED":
        raise ContextError(f"research job {d.name}: its report was not checked by e1 ({check.get('status')})")
    report, findings = _load(raw, d, "report.json"), _load(raw, d, "findings.json")
    verdicts = check.get("verdicts") or {}
    every = check_items(report)
    supported = [it["id"] for it in every if (verdicts.get(it["id"]) or {}).get("verdict") == SUPPORTED]
    if items is None:
        chosen = supported
        if not chosen:
            raise ContextError(f"research job {d.name}: e1 judged no item SUPPORTED")
    else:
        chosen = list(dict.fromkeys(items))
        bad = [i for i in chosen if i not in supported]
        if not chosen:
            raise ContextError(f"no items were given; choose among the SUPPORTED ones ({', '.join(supported) or 'none'}) "
                               "or leave out --items to take them all")
        if bad:
            raise ContextError(f"items must be among the SUPPORTED ones ({', '.join(supported) or 'none'}); "
                               f"{', '.join(bad)} is not")
    left_out = [it["id"] for it in every if it["id"] not in supported]
    by_id = {f["id"]: f for w in findings.get("workers") or [] for f in w.get("findings") or []}
    taken = [it for it in every if it["id"] in chosen]
    cited = list(dict.fromkeys(c for it in taken for c in it["cites"]))
    missing = [c for c in cited if c not in by_id]
    if missing:
        raise ContextError(f"research job {d.name}: the report cites {', '.join(missing)}, which findings.json lacks")

    def quote_lines(fid):
        out = []
        for s in by_id[fid]["sources"]:
            # the URL is chosen by a worker model: fenced with its quote, never beside the harness's own words
            out += [f"- {fid}:", fence(f"{s['url']}\nfetched {s.get('fetched_at')}\n\n{s['quote']}", "text")]
        return out

    lines = [f"Research job {d.name}. Question:", fence(findings.get("question") or "", "text"), "",
             "Every quote below was checked by the harness in that run: its page was fetched there and the quote is in "
             "the part that was read. Every claim below was judged SUPPORTED by its quotes by the research checker (e1).",
             "Left out (e1 did not judge them SUPPORTED): " + (", ".join(left_out) or "none") + "."
             + ("" if items is None else " Not chosen: " + (", ".join(i for i in supported if i not in chosen)
                                                             or "none") + "."), "", "Claims:"]
    for it in taken:
        lines += [f"- {it['id']} (cites {', '.join(it['cites']) or 'nothing'}):", fence(it["text"], "text")]
    lines += ["", "Quotes:"]
    for fid in cited:
        lines += quote_lines(fid)
    text = "\n".join(lines)
    if len(text) > ct.MAX_RESEARCH:
        sizes = ", ".join(f"{it['id']} {len(it['text']) + sum(len(s['quote']) for c in it['cites'] for s in by_id[c]['sources'])}"
                          for it in taken)
        raise ContextError(f"the research context has {len(text)} characters, more than {ct.MAX_RESEARCH}; choose "
                           f"items with --items (characters per item with its quotes: {sizes})")
    record = {"job": d.name, "items": [it["id"] for it in taken], "left_out": left_out, "chars": len(text),
              "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
              "files": {n: hashlib.sha256(raw[n]).hexdigest() for n in FILES}}
    return text, record
