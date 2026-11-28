# SPEC: install card check (h) for a job that is not a queue item (F36)

Status: draft for Opus read-only review. 2026-11-28.

## Problem (observed, job j20261128_035717_0f18)
A code job made through chat "New issue" (no queue, no PRD) reaches REVIEW_READY. Both patch readers wrote ok (check f green), but
check (h) "ada contoh perilaku yang baru" is false ("tidak ada contoh untuk perilaku yang baru; pernyataan 'tanpa angka ...' belum
tercatat di kartu rencana"), so `open` is false and `code_apply` is refused (F8). Checks a, b, d, i are already `null` for such a job.
(h) was written for PRD queue items, where the plan card either carries examples or a stated "no examples" reason.

## Change
1. `router/examples_read.py`: the two "job is not an item of a queue" results of `_chain` (no queues directory; job not in any queue of this
   jobs directory) carry an extra key `standalone: True`. No other result carries it. `applicable`/`ok`/`kind`/`why` unchanged.
2. `router/approve_code.py`: `res = er.chain(...)` is computed BEFORE (h). (h) becomes:
   - item unreadable or defects -> `false` (unchanged, wins over everything);
   - `counts.after + counts.whatif >= 1` -> `true` (unchanged);
   - else if `res.get("standalone") is True` -> `null`, why "tidak berlaku: job ini bukan item antrean PRD, tidak ada kartu rencana yang bisa memuat contoh; yang menjaga: dua pembaca patch dan Anda membaca seluruh patch";
   - else `false` (unchanged text).
   The `chain` call moves; its result is used by (i) as before; nothing else changes.

## Not changed
- Queue items (applicable True, or a queue file that names the job and is unusable, or not made from PRD folder / item without examples block): (h) as today.
- F8 rule: refused when any check other than (f) is `false`; `null` does not refuse. (f), (g), (c), (e) still gate. The page's tick and whole-diff display still gate.
- `argus apply` CLI, readers, audit lines, the page, pins.

## Risk
A standalone job can now be installed without any machine-checked example of new behaviour. What remains: (c) valid review package (tests re-run
incl. must_pass), (e) approved draft, (f) two readers ok, (g) one sha, human reads the whole diff and ticks. Acceptable for the "New issue" path,
which has no examples by construction. Fail closed: any error in `chain` is `applicable True` -> (h) false as today.

## Tests / mutants
- standalone job, readers ok, no examples -> (h) null, open True; with defects -> (h) false; queue item without examples -> (h) false (unchanged);
  unusable queue file naming the job -> (h) false; both standalone returns carry the key; no other return does.
- Mutants: key missing on either return; key on applicable result; `standalone` truthiness not `is True`; null placed before the defects check;
  null placed before the counts>=1 true branch (loses nothing, but check why text); chain moved after (h) not applied; (i) using stale res.
