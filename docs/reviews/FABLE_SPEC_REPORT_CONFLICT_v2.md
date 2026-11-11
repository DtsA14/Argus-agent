> Verbatim copy of Fable's `SPEC_REPORT_CONFLICT_v2.md` and its replay table (session B1 follow-up), pasted by Atha on 2026-11-11 and not edited,
> apart from this note. **Draft, not approved.** It replaces parts of [`FABLE_SPEC_REPORT_CONFLICT_v1.md`](FABLE_SPEC_REPORT_CONFLICT_v1.md) (R1, R2.7-9,
> R3, R6, R7 and section 3). Fable's covering message: the replay is on paper from `PENDING.md`, `SPEC_CONFLICT_GATE`, `SPEC_JUDGE`, the injection pilot and
> the chain-probe result; the job records were not in its checkout, so "which tests would be red under a correct implementation" is inference in every row.
> Claude's reading, and which code claims were re-checked, is in section 10 of [`FABLE_REVIEW_2026-11-11.md`](FABLE_REVIEW_2026-11-11.md).

# Spek v2: `ReportConflict` (koreksi atas v1, replay, dan MVP)

Status: **usulan Fable 2026-11-11**, menggantikan R1, R2.7-9, R3, R6, R7 dan §3 dari v1; sisanya tetap. Dibaca ulang di
3d3b078: `acceptance/validation.py` (red check, vitest), `acceptance/changed.py`, `acceptance/draft.py`, `router/job.py`
(approve, redraft, retry), `codetask/tools.py`, `config.yaml`. Tidak ada yang dijalankan.

## 1. Tool tetap di allowlist (ganti R3, R7, §3)

**A1. Gerbang.** `ReportConflict` masuk `GATED` sebagai `report_conflict` (`codetask/tools.py:124-126`) dan ke `tools.coder`
(`config.yaml:282`). Allowlist dibekukan di setup (`run.py:308`) dan dipakai apa adanya (`run.py:323-327`). Run yang dimulai
sebelum deploy tidak memilikinya, jadi skema tool dan kunci memo langkahnya (`steps.py:34`) tidak berubah.

**A2. Selalu ditawarkan.** Sepanjang run, juga sesudah laporan tak terkonfirmasi. Pemakaian kedua ditolak **di balasan tool**:
`Refused: ReportConflict was already used in this run and was not confirmed (<butir>); fix the code or call Finish.`,
`finished: false`, di-commit dengan `tool_step_key` seperti hasil tool lain. Panggilan berbentuk salah (`Rejected`) tidak
menghabiskan jatah.

**A3. State "sudah dipakai".** Field baru di state graf: `conflict = {files, unconfirmed: [...]}`, ditulis oleh hasil node
acceptance (di-commit `guard` ke memo, lalu checkpoint `sync`). Node agen meneruskannya ke `Toolbox` (`run.py:338`). Karena
state itu sudah di-commit sebelum attempt berikutnya mulai, resume memberi balasan tool yang sama. Tidak ada yang dibaca
dari memori proses.

**A4. Crash.**
- Sesudah tool, sebelum commit: tool jalan lagi; `SUMMARY.json` ditulis atomik (`fs.py:105-130`), hasil sama.
- Di acceptance sebelum commit: verifikasi diulang (sandbox read-only); `verdict_<i>.json` ditimpa atomik.
- Sesudah commit: `memo_hit`, tidak ada yang diulang.
- `versions["ReportConflict"] = "1"` (`run.py:208`).

**A5. Batas.** Satu laporan sah per run. Laporan tak terkonfirmasi = attempt gagal biasa, dihitung `max_iterations`.

## 2. Asumsi v1 terhadap kode

| v1 | Kode | Koreksi |
|---|---|---|
| R2.7 baseline dijalankan harness | Input run = `root / contract["inputs"]["workspace"]` (`run.py:262`), dicek tak berubah di setup (`run.py:249`). Approve sudah menuntut "hanya tes baru wajib yang merah, tak ada error" (`draft.py:423-428`, diulang di `job.py:873`) | Bukti baseline **sudah ada** sejak approve. Di acceptance cukup satu jalan ulang pada input, untuk flaky |
| R2.8 `red_check` pada node lama | Menerima node apa pun (`validation.py:644-670`); gagal baca → `(None, why)`. Record: `outcome, type, assertion, path` (`612-625`). Vitest: `runner="vitest"`, menjalankan seluruh berkas (`872`); `assertion` hanya untuk `AssertionError` (`849`) | `(None, why)` atau node tak ada di record → tak terkonfirmasi. Syarat diubah (lihat §3) |
| R2.9 dua kali | – | Dua `red_check` pada workspace, satu pada input: tiga run |
| R6 `changed_tests` | Hanya `test_*.py` yang ada, paling banyak 5 berkas (`changed.py:26`, `56`); vitest ditolak (`draft.py:167-169`) | `--from-conflict` hanya untuk pytest dan nama `test_*.py`; selain itu commit manusia |
| R6 redraft | Hanya dari `DRAFT_FAILED`/`AWAITING_APPROVAL` (`job.py:1232`); `LEGAL` tak punya jalan dari `AGENT_FAILED` ke `DRAFTING` (`job.py:73-76`). Catatan drafter sudah ada: `note`, ≤ 1000 karakter, menandai `human_steered` (`job.py:669`, `697-699`, `1223-1236`) | Pasangan `LEGAL` baru; catatan harness memakai jalur `note` dengan penanda sendiri, bukan `human_steered` |
| R6 gerbang approve | `_conflict_refusal` sebelum apa pun (`job.py:839-841`); layar lewat `changed_lines` (`job.py:785-795`, `858`) | Gerbang baru di tempat yang sama |
| R4 | Setiap non-DONE menjadi `AGENT_FAILED` (`job.py:939-940`); `retry` menuntut `AGENT_FAILED` (`job.py:1180`) | Lihat MVP |

## 3. Perubahan dari replay

Lima insiden diputar ulang di atas kertas (tabel di akhir berkas). Tiga koreksi:

**B1. Agen menyebut berkas, bukan node.** `files`: 1-5 berkas tes lama. Harness sendiri yang mengambil himpunan node merah;
semuanya harus berada di berkas itu. Alasan: di `c4be` jumlah tes yang pecah di `test_api.py` tidak diketahui, dan batas
5 node bisa menolak konflik yang benar. Lebih dari 50 node merah (`MAX_NODES`, `validation.py:54`) → tak terkonfirmasi.

**B2. "Merah karena assertion" terlalu sempit.** Di `097d` tes lama akan gagal karena query satu halaman menemukan dua
elemen: error pustaka, bukan `AssertionError`. Syarat baru: `outcome == "failed"` dan `path` record = berkas tes itu sendiri
(gagal di frame tes, bukan error muat atau koleksi). `type` ditampilkan ke manusia.

**B3. Laporan tak terkonfirmasi tetap terlihat.** `status` menampilkan `agent reported a conflict (not confirmed): <files>;
failed checks: <butir>`. Alasan: V4 (tes baru draf yang cacat) dan mungkin 021 t1 bukan "tes lama merah", jadi ditolak
dengan benar menurut definisi, tetapi petunjuk bagi manusia tidak boleh hilang.

**Jawaban salah yang ditemukan:**
- 097d dengan v1 (B2 memperbaikinya).
- 021 t1 **tidak bisa ditentukan** dari catatan (`PENDING.md` L80-82): bila yang merah adalah tes baru karena state bocor dari
  tes lama, laporan ditolak walau konfliknya nyata.
- V4 di luar cakupan: agen tetap tanpa jalan keluar untuk tes baru yang cacat.

## 4. MVP (PR pertama)

**Isi:**
- tool tergerbang (A1-A5) dan satu kalimat di prompt (`agent.py:172`);
- `acceptance/conflict.py`: R2.1-6, satu jalan ulang baseline, `red_check` dua kali dengan syarat B2;
- `BLOCKED`/`test_conflict` di `status.py:29`, `verdict.conflict`;
- baris `status` (terkonfirmasi dan B3);
- `retry` ditolak bila run terakhir `test_conflict` (di samping `job.py:1183`).

**Tidak ada:** state job `CONFLICT` (job tetap `AGENT_FAILED`), `redraft --from-conflict`, gerbang approve, catatan untuk
penulis issue.

**Manusia sementara itu:** `abandon`, lalu job baru yang issue-nya menyebut berkas tes itu (yang dilakukan pada job ketiga
probe rantai, `chain_probe_v0/RESULT.md:9-11`); untuk vitest, commit pada tes lama lebih dulu.

**Perkiraan:** 6 berkas kode + config, sekitar 230 baris: `tools.py` +45, `agent.py` +15, `run.py` +30, `status.py` +2,
`conflict.py` baru ±110, `job.py` +30. Tes ±350 baris, skrip mutan ±120.

**Paling berisiko:** cabang baru di node acceptance (`run.py:366-387`): keputusan status di jalur ketat, bertemu
`max_iterations`, stagnasi dan resume. Kedua: himpunan node merah dibaca dari proses yang memuat kode agen (AUDIT D5).

**Batas klaim:** MVP memberi jalan keluar; ia tidak memaksa agen memakainya. Gerbang deteksi dan pembaca patch tetap.

## Replay table (v2 rules; "checks" refers to R2 items 1-9 with the B1/B2 changes)

| Incident | True conflict? | Checks under a correct implementation | Confirmed? | What the human would see |
|---|---|---|---|---|
| `097d` (viewer issue 003, vitest) | Yes. The protected `jobs-list` test used a page-wide query; it was later fixed by hand (`56b7e00`). | Scope, detection, old-and-protected, must_pass, baseline all pass. Red-in-own-frame passes under B2; under v1's "AssertionError only" it fails. | v1: no (wrong answer). v2: yes. | `jobs-list.test.jsx` named, the error type and message, "change that test by a commit of yours, then a new job" (vitest drafts cannot change old tests). |
| `1808` (shadow batch 2, vitest) | Yes. The drafter itself flagged two conflicts correctly. | All pass; the old tests fail on a count mismatch, an ordinary assertion. | Yes, but not reached today: the approve gate (#275) now refuses such a draft before the agent runs. | Today the `conflict:` lines at approve. Without that gate, the same screen as `097d`. |
| 021 t1 (`j20261106_133421_1459`, vitest) | Yes, by the notes: the protected `jobs-sort` test leaked address state. | Unknown which tests go red. If other old tests: all pass. If the draft's new tests: must_pass fails and the red tests are not old. | Undetermined. In the second case the report is refused although the conflict is real. | Second case: only the B3 line, "agent reported a conflict (not confirmed)", with the failed checks. |
| Injection V4 (`j20261106_170438_f594`, pytest) | No old-test conflict. The draft's own new test demanded a 1000-byte CSV from a 647-byte fixture. | Old-and-protected fails (the red test is a new draft test); must_pass fails. | No, correctly by definition. The agent still has no exit for a defective new test. | The B3 line. Claude's draft notes had already said the draft should be rejected. |
| `j20261111_112252_11b3` (ledger, pytest) | Yes. `test_title_in_jobs.py` holds an exact key list; the drafter missed it. | All pass, provided nothing else is red; the failure is a list-equality assertion in the test's own frame. | Yes. | `tests/test_title_in_jobs.py` and its assertion. Full version: `redraft --from-conflict` with that file in `changed_tests`. MVP: abandon and a new job naming the file. |
| `j20261111_113723_c4be` (sibling) | Yes. This draft changed `test_title_in_jobs.py` but missed `test_api.py` (exact dict comparison). | All pass. The number of red tests in `test_api.py` is not recorded, which is why B1 names files. | Yes under v2; possibly no under v1's five-node limit. | `tests/test_api.py` and its assertions; same next step as above. The agent ended `FAILED_ACCEPTANCE` honestly here, so the gain is the named file, not a prevented cheat. |
