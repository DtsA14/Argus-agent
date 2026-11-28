"""Does the foreman remember? (SPEC_FOREMAN_MEMORY rev 1 section 10). Measurement, not a unit test: real model calls through `argus manager turn` (the production path).

A synthetic 30 turn conversation with 6 planted facts is written into a session job.json by code; per round ONE turn runs on it (with the compaction arm that is the turn
that compacts); then each of 7 questions (6 recall, 1 unplanted-fact control) runs on a FRESH COPY of that job, so answers cannot leak forward. Scored by code on a few
accepted forms per fact. Arms: `new` (this checkout's argus.py: compaction) and `old` (another checkout's argus.py, e.g. a worktree of main before phase A: the 4 KB cut).

Usage: python run.py ROOT --argus PATH/scripts/argus.py [--rounds 3] [--cap-usd 0.30] [--label new]     (ROOT is created; argus reads the key from its key file)"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
KEY = "openrouter=~/.config/argus/openrouter_key"

FILLER = ("Saya sedang memikirkan banyak hal soal aplikasi catatan harian dan bagaimana tampilan halaman utamanya sebaiknya diatur supaya enak dibaca di ponsel, "
          "termasuk jarak antar baris, ukuran huruf, warna latar, dan urutan menu. Tidak ada keputusan baru di bagian ini, hanya pikiran yang berputar. ")
FACTS = [  # (turn index of the human message, text of the fact, question, accepted regexes)
    (2, "Kita bahas repo bulking-app dulu ya, bukan yang lain.", "Repo mana yang tadi kita bahas?", [r"bulking-app"]),
    (5, "Kita sepakat buffer harganya 7 persen, jangan diubah lagi.", "Berapa persen buffer yang kita sepakati tadi?", [r"\b7\b", r"tujuh"]),
    (8, "Yang akan mereview hasilnya nanti adalah Pak Wirawan.", "Siapa yang akan mereview hasilnya?", [r"wirawan"]),
    (11, "Keputusannya: penyimpanan lokal pakai IndexedDB lewat Dexie.", "Library penyimpanan apa yang kita putuskan?", [r"dexie"]),
    (14, "Syarat utamanya aplikasi harus tetap jalan offline, tanpa jaringan sama sekali.", "Apa syarat utama soal koneksi yang kita tetapkan?", [r"offline", r"tanpa jaringan", r"tanpa internet"]),
    (17, "Pertanyaan yang belum terjawab: apakah ekspor CSV perlu kolom tanggal dalam format ISO?", "Apa pertanyaan yang masih terbuka untuk fitur ekspor?", [r"\biso\b", r"format tanggal", r"kolom tanggal"]),
]
CONTROL = ("Siapa nama vendor kontrak yang kita pilih?", [r"tidak ada", r"belum", r"tidak (pernah )?(ingat|disebut|tahu|ada)", r"nggak", r"tidak.*(vendor|menyebut|membahas)"])


def filler(i):
    return (f"[{i:02d}] " + FILLER * 8)[:1850]


def conversation():
    out = []
    facts = {f[0]: f[1] for f in FACTS}
    for i in range(30):
        text = (facts[i] + " " if i in facts else "") + filler(i)
        out.append({"from": "human", "at": "2026-11-28T10:00:00Z", "text": text[:1990]})
        out.append({"from": "manager", "at": "2026-11-28T10:00:01Z", "say": "Oke, dicatat. " + filler(i + 100)[:1800], "propose": None, "usd": 0.0, "calls": 1})
    return out


def argus(path, jobs, *args):
    return subprocess.run([sys.executable, path, "--jobs-dir", str(jobs), *args], capture_output=True, text=True, timeout=900, cwd=REPO)


def turn(path, jobs, job, message, tmp):
    f = Path(tmp) / "m.txt"
    f.write_text(message, encoding="utf-8")
    r = argus(path, jobs, "manager", "turn", job, "--message-file", str(f), "--via", "ui", "--key-file", KEY, "--yes")
    d = json.loads((Path(jobs) / job / "job.json").read_text())
    last = [e for e in d["conversation"] if e.get("from") == "manager"][-1]
    return last, d, r


def spent(jobs, job):
    from router import job as rj
    return rj.spent_nano(rj.open_job(job, jobs)) / 1e9


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--argus", required=True)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--cap-usd", type=float, default=0.30)
    ap.add_argument("--label", default="new")
    o = ap.parse_args()
    root = Path(o.root)
    root.mkdir(parents=True, exist_ok=False)
    sys.path[:0] = [str(REPO)]
    from router import job as rj
    from router import manager_job as mj
    from runner import load_config
    cfg = load_config()
    total, rows = 0.0, []
    for rnd in range(1, o.rounds + 1):
        base = root / f"r{rnd}_base"
        base.mkdir()
        deps = rj.Deps(confirm=lambda t: True, get_key=lambda: "sk-or-v1-notused0000000000000000", isatty=lambda: True, echo=lambda s: None)
        j = mj.new(cfg=cfg, deps=deps, jobs_dir=base, job_id=rj.new_job_id(), via="ui")
        p = base / j.id / "job.json"
        d = json.loads(p.read_text())
        d["conversation"] = conversation()
        p.write_text(json.dumps(d))
        last, d, r = turn(o.argus, base, j.id, "Terima kasih, lanjut ya.", root)             # the turn that compacts (new arm) or just answers (old arm)
        total += spent(base, j.id)
        compacted = any(e.get("from") == "summary" for e in d["conversation"])
        print(f"round {rnd}: first turn done, compacted={compacted}, failed={last.get('compaction_failed')}, spent so far ${total:.4f}", flush=True)
        for qi, (turn_i, fact, q, forms) in enumerate(FACTS + [(None, None, *CONTROL)]):
            if total > o.cap_usd:
                print("cap reached; stopping", flush=True)
                break
            copy = root / f"r{rnd}_q{qi}"
            shutil.copytree(base, copy)
            last, d2, r = turn(o.argus, copy, j.id, q, root)
            total += spent(copy, j.id) - spent(base, j.id)
            say = last.get("say") or ""
            ok = any(re.search(f, say, re.I) for f in forms)
            rows.append({"label": o.label, "round": rnd, "q": qi, "control": turn_i is None, "ok": ok, "say": say[:300], "error": last.get("error")})
            print(f"  q{qi} {'ok ' if ok else 'MISS'} {say[:110]!r}", flush=True)
    (root / "rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    rec = [r for r in rows if not r["control"]]
    ctl = [r for r in rows if r["control"]]
    print(f"\n{o.label}: recall {sum(r['ok'] for r in rec)}/{len(rec)}; control (admits it does not know) {sum(r['ok'] for r in ctl)}/{len(ctl)}; spent about ${total:.4f}")
    per = {}
    for r in rec:
        per.setdefault(r["q"], []).append(r["ok"])
    print("per fact:", {FACTS[k][2]: f"{sum(v)}/{len(v)}" for k, v in per.items()})


main()
