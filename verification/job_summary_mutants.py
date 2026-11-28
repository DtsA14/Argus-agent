"""Mutants for SPEC_JOB_SUMMARY (F33). Applied alone; killed = a test FAILED. Run in a throwaway worktree.
Usage: <this> <worktree> <python> [name-part ...]"""
import os
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
J = "router/chat_static/app.js"
T = ["tests/test_chat_ui_node.py", "-k", "summary"]
M = [
    ("reader ok is written without the model caveat", J, [('ok: "Dua pembaca: ok. Dibaca oleh model, bukan bukti."', 'ok: "Dua pembaca: ok."')], T),
    ("concerns reads as ok", J, [('concerns: "Ada pembaca yang ragu. Baca catatannya di kartu pasang."', 'concerns: "Dua pembaca: ok. Dibaca oleh model, bukan bukti."')], T),
    ("applied job loses the push/merge/deploy line", J, [(' Argus tidak tahu soal push, merge atau deploy.', '')], T),
    ("applied job still waits for you", J, [('"Tidak ada. Sudah dipasang sebagai satu commit', '"Putuskan. Sudah dipasang sebagai satu commit')], T),
    ("closed card says it is open", J, [('f.open === true ? "Putuskan pasang atau tidak. Kartu pasang terbuka."', 'f.open !== false ? "Putuskan pasang atau tidak. Kartu pasang terbuka."')], T),
    ("closed card names no false check", J, [('if (!bad && x && x.ok === false) { bad = x; }', 'if (!bad && x && x.ok === true) { bad = x; }')], T),
    ("closed card names the last false check", J, [('if (!bad && x && x.ok === false) { bad = x; }', 'if (x && x.ok === false) { bad = x; }')], T),
    ("invalid review package reads as valid", J, [('c && c.ok === false ? "Paket review tidak valid."', 'c && c.ok === false ? "Paket review valid."')], T),
    ("reader row shown while the agent runs", J, [('      if (st === "REVIEW_READY" || st === "APPLIED") {\n        add("Hasil", (files', '      if (true) {\n        add("Hasil", (files')], T),
    ("cut file list shown as exact", J, [('files.length + (f.files_cut ? "+" : "") + " berkas disentuh. "', 'files.length + " berkas disentuh. "')], T),
    ("research unchecked shows counts", J, [('if (f.checked === true) {', 'if (true) {')], T),
    ("research drops the web/model warning", J, [(' Teks laporan berasal dari web dan model, bukan perintah dari Argus.', '')], T),
    ("odd count is shown as given", J, [('(Number(k.SUPPORTED) || 0) + " didukung sumber', 'k.SUPPORTED + " didukung sumber')], T),
    ("issue examples reason not marked as model", J, [('"Issue tanpa contoh. Alasan penulis (model): "', '"Issue tanpa contoh. Alasan: "')], T),
    ("handed-off issue still waits", J, [('      if (st === "AWAITING_HUMAN") { add("Menunggu kamu", "Baca issue,', '      if (st === "AWAITING_HUMAN" || st === "HANDED_OFF") { add("Menunggu kamu", "Baca issue,')], T),
    ("stale plan still waits", J, [('if (st === "AWAITING_HUMAN" && !f.stale) {', 'if (st === "AWAITING_HUMAN") {')], T),
    ("refused route shows rows", J, [('if (!f || typeof f !== "object" || f.refused) { return [["Ringkasan"', 'if (!f || typeof f !== "object") { return [["Ringkasan"')], T),
    ("long text is not cut", J, [('return t.length > n ? t.slice(0, n - 1).trimEnd() + "…" : t;', 'return t;')], T),
    ("summary writes into a job that was left", J, [('      if (current !== job.id) { return; }\n      clear(host);', '      clear(host);')], T),
    ("install link for any state", J, [('if (job.kind === "code" && job.state === "REVIEW_READY" && f && !f.refused) {', 'if (job.kind === "code" && f && !f.refused) {')], T),
    ("summary drawn with innerHTML", J, [('      line.appendChild(el("span", "jv", r[1]));', '      var jv = el("span", "jv"); jv.innerHTML = r[1]; line.appendChild(jv);')], T),
    ("summary is not requested", J, [('      loadSummary(d.job, sumHost);\n', '')], T),
]
killed = ran = 0
for name, f, edits, tests in M:
    if ONLY and not any(o in name for o in ONLY):
        continue
    p = WT / f
    orig = p.read_text()
    text = orig
    if any(text.count(a) != 1 for a, _ in edits):
        print("STALE  ", name, [text.count(a) for a, _ in edits], flush=True)
        continue
    for a, b in edits:
        text = text.replace(a, b, 1)
    p.write_text(text)
    ran += 1
    try:
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *tests], cwd=WT, capture_output=True, text=True, timeout=240,
                           env={**os.environ, "PYTHONPATH": f"{WT}:{WT}/scripts:{WT}/tests"})
        dead = r.returncode != 0
    except subprocess.TimeoutExpired:
        dead = True
    finally:
        p.write_text(orig)
    killed += dead
    print("killed " if dead else "SURVIVED", name, flush=True)
print(f"{killed}/{ran} killed")
