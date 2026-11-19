#!/usr/bin/env python3
"""T3a of docs/reviews/SPEC_KARTU_SETUJU.md section 8: can Atha, without reading code and without calculating, reject the cards that are wrong in purpose, cost, scope
or audit and accept the good ones? This file builds 12 cards (6 defect, 6 good) as files of real jobs in a SEPARATE directory (never pilot3a_live/jobs), hides the key
behind a hash, prints the order in which Atha is to look at them (kind and id, never the class), records his replies word for word and scores them.

The cards: plan cards (4 defect: two where the writer's summary and issue are about something else than the request, two whose cost per issue is far above the usual
cap; 3 good) and install cards (2 defect: one patch that touches a file the issue did not name, one whose audit failed; 3 good). All numbers on all cards are right and
the readers' notes are `ok` (fixtures), so Atha is not tested on what is not his task. The cost ratio is the machine's (usual job cap 1.0 per issue: defects 4x and 6x, good
1x), the scope mark is the machine's. Each card is one PRD job (plan card) or one queue whose item 1 is a code job (install card: in the chat, open the queue, then
"Kartu pasang").

Serve it with `argus --jobs-dir <root>/jobs --queues-dir <root>/queues chat serve --port 8712` and open it through an SSH forward of 8712.
Reply: `reply <root> --card N --verdict terima|tolak [--class tujuan|biaya|cakupan|audit] --text "..."`: written as given, with the time, before anyone explains a card.
Pass: every defect card is rejected with its right class, and at most one good card is rejected (rejecting everything fails by itself). N is a usability measure, not a
statistic; the builder and the cards' author are the same model family, so the defects are the ones Claude thought of.
"""
import argparse
import hashlib
import json
import random
import secrets
import shutil
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import t3b_fixtures as t3  # noqa: E402
from router import example_gate as eg  # noqa: E402
from router import examples_read as er  # noqa: E402

KEY_FILE, REPLIES = "t3a_key.json", "t3a_replies.jsonl"
CLASSES = ("tujuan", "biaya", "cakupan", "audit")
SNAP = "5" * 64
NOW = "2026-11-19T01:00:00Z"
DEPS = SimpleNamespace(clock=lambda: NOW)
CAP = 1.0                                           # the usual cap of a code job: the cost reference (three applied jobs carry it)
CHEAP, DEAR_1, DEAR_2 = 1.0, 4.0, 6.0               # the plan's proposal per issue (one issue per plan): 1x, 4x, 6x the usual cap


def ex(i, tier, says, fn, args, expect):
    return t3.ex_(i, tier, says, fn, args, expect)


# (key, kind, class, request, writer reply, title, body, examples, extra); kind: defect|good; extra: {"card": plan|install, "usd": proposal, "files": [...]}
PURPOSE = ("Tambah diskon member 3 persen dari harga.", "Saya tambahkan poin loyalitas: tiap belanja Rp10.000 member dapat 1 poin.", "Poin loyalitas member",
           "Belanja member menambah poin loyalitas.", [ex(1, "after", "Belanja Rp100.000 menambah 10 poin", "lots", "100000, 10000", 10)])
CASES = [
    ("p1", "defect", "tujuan", *PURPOSE, {"card": "plan", "usd": CHEAP}),
    ("p2", "defect", "tujuan", "Tampilkan sisa batas rugi harian, jangan diubah batasnya.", "Saya naikkan batas rugi harian menjadi Rp20.000.000.", "Naikkan batas harian",
     "Batas rugi harian menjadi dua kali lipat.", [ex(1, "after", "Batas harian 20.000.000", "price_idr", "20000000, 1", 20000000)], {"card": "plan", "usd": CHEAP}),
    ("p3", "defect", "biaya", "Jumlah beli dibulatkan ke bawah ke kelipatan 100.", "Saya tambahkan pembulatan jumlah beli.", "Bulatkan jumlah beli",
     "Jumlah beli dibulatkan ke bawah.", [ex(1, "after", "1.990 menjadi 1.900", "round_down", "1990, 100", 1900)], {"card": "plan", "usd": DEAR_1}),
    ("p4", "defect", "biaya", "Harga sepatu itu Rp1.500.000, tampilkan dalam rupiah penuh.", "Saya tambahkan harga dalam rupiah.", "Harga dalam rupiah",
     "Harga ditulis dalam rupiah penuh.", [ex(1, "after", "Harga sepatu 1.500.000 rupiah", "price_idr", "1500000, 1", 1500000)], {"card": "plan", "usd": DEAR_2}),
    ("p5", "good", "baik", "Diskon member itu 3 persen dari harga.", "Saya tambahkan diskon member.", "Diskon member", "Harga dikurangi diskon member.",
     [ex(1, "after", "Harga Rp200.000 dengan diskon member menjadi 194.000", "discount", "200000, 3", 194000)], {"card": "plan", "usd": CHEAP}),
    ("p6", "good", "baik", "Batas rugi harian Rp10.000.000, sudah terpakai Rp3.000.000; tampilkan sisanya.", "Saya tambahkan sisa batas.", "Sisa batas harian",
     "Sisa batas ditampilkan.", [ex(1, "after", "Sisa batas 7.000.000", "remaining", "10000000, 3000000", 7000000)], {"card": "plan", "usd": CHEAP}),
    ("p7", "good", "baik", "Pembelian saham harus dalam kelipatan 1 lot, dan 1 lot itu 100 lembar.", "Saya tambahkan hitungan lot.", "Hitung lot",
     "Jumlah lembar diubah menjadi jumlah lot.", [ex(1, "after", "1.000 lembar adalah 10 lot", "lots", "1000, 100", 10)], {"card": "plan", "usd": CHEAP}),
    # install cards: a PRD with one issue (a `same` and an `after` example), a queue whose item 1 is the code job with its patch
    ("i1", "defect", "cakupan", "Jumlah beli dibulatkan ke bawah ke kelipatan 100.", "Saya tambahkan pembulatan jumlah beli.", "Bulatkan jumlah beli",
     "Jumlah beli dibulatkan ke bawah.", [ex(1, "same", "100 tetap 100", "round_down", "100, 100", 100), ex(2, "after", "1.990 menjadi 1.900", "round_down", "1990, 100", 1900)],
     {"card": "install", "files": ["src/shop.py", "src/other.py"]}),
    ("i2", "defect", "audit", "Diskon member itu 3 persen dari harga.", "Saya tambahkan diskon member.", "Diskon member", "Harga dikurangi diskon member.",
     [ex(1, "same", "Harga Rp100.000 tanpa diskon tetap 100.000", "discount", "100000, 0", 100000), ex(2, "after", "Harga Rp200.000 dengan diskon member menjadi 194.000", "discount", "200000, 3", 194000)],
     {"card": "install", "files": ["src/shop.py"], "audit": "fail"}),
    ("i3", "good", "baik", "Batas rugi harian Rp10.000.000, sudah terpakai Rp3.000.000; tampilkan sisanya.", "Saya tambahkan sisa batas.", "Sisa batas harian",
     "Sisa batas ditampilkan.", [ex(1, "same", "Batas 10.000.000 belum terpakai: sisa 10.000.000", "remaining", "10000000, 0", 10000000),
                                 ex(2, "after", "Sisa batas 7.000.000", "remaining", "10000000, 3000000", 7000000)], {"card": "install", "files": ["src/shop.py"]}),
    ("i4", "good", "baik", "Jumlah lembar ditampilkan juga sebagai jumlah lot (1 lot = 100 lembar).", "Saya tambahkan hitungan lot.", "Hitung lot",
     "Jumlah lembar diubah menjadi jumlah lot.", [ex(1, "same", "100 lembar adalah 1 lot", "lots", "100, 100", 1), ex(2, "after", "1.000 lembar adalah 10 lot", "lots", "1000, 100", 10)],
     {"card": "install", "files": ["src/shop.py"]}),
    ("i5", "good", "baik", "Harga sepatu itu Rp1.500.000, tampilkan dalam rupiah penuh.", "Saya tambahkan harga dalam rupiah.", "Harga dalam rupiah",
     "Harga ditulis dalam rupiah penuh.", [ex(1, "same", "Harga 1 tetap 1", "price_idr", "1, 1", 1), ex(2, "after", "Harga sepatu 1.500.000 rupiah", "price_idr", "1500000, 1", 1500000)],
     {"card": "install", "files": ["src/shop.py"]}),
]


def patch_of(files):
    return "".join(f"diff --git a/{p} b/{p}\n--- a/{p}\n+++ b/{p}\n@@ -1 +1 @@\n-x\n+{'def x' if p == 'src/shop.py' else 'y'}\n" for p in files).encode()


def opaque(taken):
    while True:
        j = "j" + time.strftime("%Y%m%d_%H%M%S") + "_" + secrets.token_hex(2)
        if j not in taken:
            taken.add(j)
            return j


def set_usd(jobs, jid, usd):
    p = jobs / jid / "job.json"
    j = json.loads(p.read_text())
    j["prd_turns"][-1]["max_usd"] = usd
    p.write_text(json.dumps(j))


def domain_notes(jobs, jid):
    """The numbers of the fixture are right: two `ok` notes of two readers, written through the real path (labelled as Claude's on the card)."""
    _, info = er.bundle(jobs, jid, 1)
    er.record(jid, 1, "ok", info["bundle_sha256"], "fixture-a", ["permintaan Atha"], "the numbers fit the request", deps=DEPS, jobs_dir=jobs)
    er.record(jid, 1, "ok", info["bundle_sha256"], "fixture-b", ["permintaan Atha"], "the numbers fit the request", deps=DEPS, jobs_dir=jobs, second=True)


def seed_applied(jobs, taken):
    for _ in range(3):                                                 # the cost reference: applied code jobs and their caps
        jid = opaque(taken)
        d = jobs / jid
        d.mkdir()
        (d / "job.json").write_text(json.dumps({"job": jid, "kind": "code", "state": "APPLIED", "max_usd": CAP, "created_at": "2026-11-10T01:00:00Z",
                                                "inputs": {"repo": "/nonexistent/t3a", "repo_name": "toko", "commit": "b" * 40}, "stages": {"a1": {"kind": "agent", "usd": 0.04}}, "log": []}))


def code_job(jobs, queues, taken, prd_job, spec):
    """A code job as the files of a real one (REVIEW_READY, review package, intake, audit, two `ok` notes of the patch reader) and the queue that names it."""
    key, extra = spec[0], spec[8]
    text = (jobs / prd_job / "prd-w1" / "issue-1.md").read_text().strip()
    parsed = eg.extract(text)[1]
    jid, sid = opaque(taken), "a1"
    run = f"{jid}-{sid}"
    patch = patch_of(extra["files"])
    psha = hashlib.sha256(patch).hexdigest()
    d = jobs / jid
    rev = d / "runs" / run / "review"
    rev.mkdir(parents=True)
    (rev / "changes.patch").write_bytes(patch)
    (rev / "provenance.json").write_text(json.dumps({"patch": {"sha256": psha, "files": [{"path": p} for p in extra["files"]]}}))
    tree = d / "runs" / run / "workspace" / "src"
    tree.mkdir(parents=True)
    (tree / "__init__.py").write_text("")
    (tree / "shop.py").write_text(t3.SHOP)
    job = {"job": jid, "kind": "code", "state": "REVIEW_READY", "max_usd": CAP, "created_at": "2026-11-19T00:30:00Z",
           "inputs": {"repo": "/nonexistent/t3a", "repo_name": "toko", "commit": "c" * 40, "issue": text, "environment": "py312"},
           "intake": {"snapshot_sha256": SNAP, "commit": "c" * 40},
           "stages": {"d1": {"kind": "draft", "status": "DRAFTED", "run_id": f"{jid}-d1", "draft_sha256": "d" * 64, "usd": 0.01},
                      sid: {"kind": "agent", "status": "DONE", "run_id": run, "usd": 0.04,
                            "review": {"valid": True, "problems": [], "dir": f"/x/{run}/review", "patch_sha256": psha}}},
           "approval": {"draft_sha256": "d" * 64, "contract_sha256": "e" * 64, "max_usd": CAP, "at": NOW, "by": "ubuntu"},
           "protected_repo": {"globs": []}, "log": []}
    (d / "job.json").write_text(json.dumps(job))
    base = [{"id": e["id"], "tier": e["tier"], "status": "unchecked", "base_actual": 0} if e["tier"] == "after"
            else {"id": e["id"], "tier": e["tier"], "status": "pass", "actual": e["expect"]} for e in parsed]
    eg.store(d / eg.INTAKE_FILE, eg.intake_key(SNAP, parsed), results=base)
    fail = extra.get("audit") == "fail"
    rows = [{"id": e["id"], "tier": e["tier"], "status": "fail" if fail and e["tier"] == "after" else "pass", "actual": 0 if fail and e["tier"] == "after" else e["expect"]} for e in parsed]
    eg.store(eg.audit_file(d, sid), eg.audit_key(psha, parsed), results=rows)
    from router import patch_read as pr
    note = {"verdict": "ok", "note": "read the diff against the issue: nothing else changed", "at": NOW, "reader": {"kind": "claude", "id": "fixture-a"}}
    (d / f"patch_read_{sid}.json").write_text(json.dumps({"key": pr.key(sid, psha), "sid": sid, "patch_sha256": psha, **note,
                                                          "second": {**note, "reader": {"kind": "claude", "id": "fixture-b"}}}))
    qid = "q" + time.strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(2)
    q = queues / qid
    q.mkdir(parents=True)
    prd = json.loads((jobs / prd_job / "job.json").read_text())["prd_turns"][-1]
    (q / "queue.json").write_text(json.dumps({"id": qid, "repo": "/nonexistent/t3a", "name": "toko", "base_commit": "c" * 40, "jobs_dir": str(jobs), "max_usd": 2.0,
                                              "job_cap_usd": CAP, "environment": "py312", "approved": True,
                                              "items": [{"n": 1, "issue_sha256": hashlib.sha256(text.encode()).hexdigest(), "job": jid}],
                                              "prd": {"sha": prd["folder_sha"], "dir": str(jobs / prd_job / "prd-w1")}}))
    (q / "issue-1.md").write_text(text)
    return jid, qid


def keydir(root):
    return Path(str(Path(root).resolve()) + ".key")


def build(root, seed=None):
    root = Path(root)
    if "pilot3a_live" in str(root.resolve()):
        raise SystemExit("the T3a cards never go into the live jobs directory")
    kd = keydir(root)
    if (root.exists() and any(root.iterdir())) or kd.exists():
        raise SystemExit(f"{root} or {kd} exists already")
    try:
        return _build(root, kd, seed)
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(kd, ignore_errors=True)
        raise


def _build(root, kd, seed):
    jobs, queues = root / "jobs", root / "queues"
    jobs.mkdir(parents=True)
    queues.mkdir()
    kd.mkdir()
    rng, taken = random.Random(seed), set()
    seed_applied(jobs, taken)
    order = list(CASES)
    rng.shuffle(order)
    cards = []
    for n, spec in enumerate(order, 1):
        extra = spec[8]
        prd = opaque(taken)
        t3.write_job(jobs, prd, spec[:8])
        set_usd(jobs, prd, extra.get("usd", CHEAP))
        domain_notes(jobs, prd)
        if extra["card"] == "plan":
            guide = {"where": "daftar kartu: PRD", "id": prd}
        else:
            jid, qid = code_job(jobs, queues, taken, prd, spec)
            guide = {"where": "daftar kartu: antrean, lalu item 1, lalu Kartu pasang", "id": qid}
        cards.append({"card": n, "set": spec[0], "kind": spec[1], "class": spec[2], "card_kind": extra["card"], **guide})
    body = json.dumps({"salt": secrets.token_hex(16), "cards": cards}, sort_keys=True)
    (kd / KEY_FILE).write_text(body)
    return cards, hashlib.sha256(body.encode()).hexdigest()


def guide(cards):
    return [f"Kartu {c['card']}: {'kartu rencana' if c['card_kind'] == 'plan' else 'kartu pasang'}; {c['where']} {c['id']}" for c in cards]


def reply(root, card, verdict, klass, text):
    key = json.loads((keydir(root) / KEY_FILE).read_text())["cards"]
    if not any(c["card"] == card for c in key):
        raise SystemExit(f"there is no card {card}")
    if verdict not in ("terima", "tolak") or (verdict == "tolak" and klass not in CLASSES) or (verdict == "terima" and klass):
        raise SystemExit(f"--verdict terima|tolak; a rejection names one class of {', '.join(CLASSES)}; an acceptance names none")
    p = keydir(root) / REPLIES
    if p.exists() and any(json.loads(l)["card"] == card for l in p.read_text().splitlines()):
        raise SystemExit(f"card {card} has a reply already; each card is answered once")
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps({"card": card, "verdict": verdict, "class": klass, "text": text, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, ensure_ascii=False) + "\n")


def score(root, printed_hash):
    """(passed, lines): the key must hash to what `build` printed; every card answered; every defect card rejected with its own class; at most one good card rejected."""
    body = (keydir(root) / KEY_FILE).read_text()
    if hashlib.sha256(body.encode()).hexdigest() != printed_hash:
        return False, ["the key file is not the one whose hash was printed before the replies"]
    key = json.loads(body)["cards"]
    p = keydir(root) / REPLIES
    got = {r["card"]: r for r in (json.loads(l) for l in p.read_text().splitlines())} if p.exists() else {}
    lines, missed, wrong, false_alarms, unanswered = [], 0, 0, 0, 0
    for c in sorted(key, key=lambda c: c["card"]):
        r = got.get(c["card"])
        if r is None:
            unanswered += 1
            lines.append(f"card {c['card']} ({c['set']}): not answered")
        elif c["kind"] == "defect":
            ok = r["verdict"] == "tolak" and r["class"] == c["class"]
            missed += r["verdict"] != "tolak"
            wrong += r["verdict"] == "tolak" and r["class"] != c["class"]
            lines.append(f"card {c['card']} ({c['set']}, defect {c['class']}): {r['verdict']} {r['class'] or ''}".rstrip() + ("" if ok else "  MISS"))
        else:
            false_alarms += r["verdict"] == "tolak"
            lines.append(f"card {c['card']} ({c['set']}, good): {r['verdict']} {r['class'] or ''}".rstrip() + ("  false alarm" if r["verdict"] == "tolak" else ""))
    conds = [("every card answered", unanswered == 0, unanswered), ("defect cards accepted: 0", missed == 0, missed),
             ("defect cards rejected with a wrong class: 0", wrong == 0, wrong), ("good cards rejected: at most 1", false_alarms <= 1, false_alarms)]
    for text, ok, n in conds:
        lines.append(f"{'ok  ' if ok else 'FAIL'} {text} (got {n})")
    passed = all(c[1] for c in conds)
    lines.append("PASS" if passed else "FAIL")
    return passed, lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("root")
    b.add_argument("--seed", type=int)
    r = sub.add_parser("reply")
    r.add_argument("root")
    r.add_argument("--card", type=int, required=True)
    r.add_argument("--verdict", choices=("terima", "tolak"), required=True)
    r.add_argument("--class", dest="klass", default=None)
    r.add_argument("--text", default="")
    s = sub.add_parser("score")
    s.add_argument("root")
    s.add_argument("--hash", required=True)
    o = ap.parse_args(argv)
    if o.cmd == "build":
        cards, h = build(o.root, o.seed)
        print(f"key hash (written before any reply; give it to `score --hash`): {h}")
        print(*guide(cards), sep="\n")
    elif o.cmd == "reply":
        reply(o.root, o.card, o.verdict, o.klass, o.text)
        print("recorded")
    else:
        passed, lines = score(o.root, o.hash)
        print(*lines, sep="\n")
        return 0 if passed else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
