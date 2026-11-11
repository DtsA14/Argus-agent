> Verbatim copy of Fable's first draft `SPEC_REPORT_CONFLICT.md` (session B1), pasted by Atha on 2026-11-11 and not edited, apart from this note.
> **Draft, not approved.** Parts of it are replaced by [`FABLE_SPEC_REPORT_CONFLICT_v2.md`](FABLE_SPEC_REPORT_CONFLICT_v2.md) (R1, R2.7-9, R3, R6, R7 and section 3);
> the rest stays. Claude's reading is in section 10 of [`FABLE_REVIEW_2026-11-11.md`](FABLE_REVIEW_2026-11-11.md).

# Spek: `ReportConflict`, jalan keluar agen saat tes lama terkunci bertentangan dengan implementasi yang benar

Status: **usulan Fable 2026-11-11** (FABLE_REVIEW B5, B9). Jalur ketat: tool agen, verdict acceptance, state run dan job.
Tanpa model baru. Dikerjakan sesudah D1 (run wedge).

## 1. Masalah (bukti)

Agen hanya bisa `Finish`. Bila tes lama terkunci menolak implementasi yang benar, ia membengkokkan kode produksi: `097d`,
`1808`, 021 t1, injeksi V4, `j20261111_112252_11b3` (kode produksi mengenali pytest).

## 2. Usul

**R1. Tool.** `ReportConflict(tests, reason)`, sendirian dalam balasannya seperti `Finish`. `tests`: 1-5 node id
(`PYTEST_NODE`/`VITEST_NODE`) dari paling banyak 3 berkas. `reason`: paling banyak 300 karakter. Tool menulis `SUMMARY.json`
dengan `claims: []` dan mengakhiri attempt (`end = "conflict_reported"`). Implementasi agen **tetap di workspace**.

**R2. Verifikasi oleh harness** (`acceptance/conflict.py`, dipanggil node acceptance sesudah `evaluate`). Laporan
*terkonfirmasi* hanya bila semuanya benar, dari bukti harness sendiri:

1. Kriteria scope, `scope:no_test_detection`, artifact dan `workspace:unchanged_during_evaluation` lulus.
2. Setiap validasi selesai dengan laporan konsisten (tanpa timeout, terpotong, atau "inconsistent").
3. Himpunan node merah menurut parser harness **sama persis** dengan `tests`.
4. Setiap node merah ada di berkas yang ada di intake, digest-nya tidak berubah, cocok glob protected (kontrak atau
   `.argus/protected`), dan bukan `new_tests`/`changed_tests` draf.
5. Setiap `must_pass` milik tes baru draf hijau (fiturnya ada).
6. Diff terhadap intake tidak kosong di berkas writable.
7. **Baseline:** node yang sama dijalankan harness pada salinan input yang tak disentuh (read-only): semua lulus.
8. **Merah karena assertion:** `red_check` pada workspace: `AssertionError`, bukan error impor atau koleksi.
9. Butir 7 dan 8 dijalankan dua kali; keempat hasil harus sama (tes flaky).

Yang terbukti hanya bentuknya. Apakah tes lama yang salah tetap keputusan manusia.

**R3. State run.** Terkonfirmasi → `BLOCKED`, `blocked_reason: "test_conflict"` (ditambah ke `BLOCKED_REASONS`),
`verdict.conflict = {tests, checks}`. Tidak terkonfirmasi → attempt gagal biasa: umpan balik berisi butir R2 yang gagal, dan
tool tidak ditawarkan lagi di run itu.

**R4. State job.** `AGENT_RUNNING → CONFLICT` (baru). Dari `CONFLICT` hanya: `redraft --from-conflict`, `reject`,
`abandon`. `retry` ditolak. `applied` menolak (bukan `REVIEW_READY`).

**R5. Layar.** `status` pada `CONFLICT`:
- `conflict (checked by the harness): <node>` per node, dengan baris assertion pertamanya (berlabel data sandbox, lewat `clean`);
- `agent's reason (not verified): <reason>`;
- `next: argus redraft <job> --from-conflict | argus reject | argus abandon`.

**R6. Jalan kembali.** `redraft --from-conflict` memulai stage drafter baru dengan catatan **buatan harness** (node dan
assertion, bukan teks agen): drafter wajib memasukkan berkas itu ke `changed_tests`. Approval lama gugur. Layar approve
menambah `resolves conflict: <node>`, dan approve menolak draf yang `changed_tests`-nya tidak memuat berkas itu (gerbang di
approve, seperti SPEC_CONFLICT_GATE C1). Vitest (tes lama belum bisa diubah draf): "ubah tes itu dengan commit Anda, lalu job baru".

**R7. Batas per job.** Satu laporan per run; satu `--from-conflict` per job, di dalam cap job; verifikasi paling banyak empat
run sandbox, tanpa uang.

## 3. Crash-resume

- Hasil tool di-commit dengan `tool_step_key` biasa (versi `"1"`, parent = langkah LLM): `{content, finished: true, conflict}`.
  Resume memutar ulang dari memo.
- `attempt.conflict` ikut hasil node agen yang di-commit `guard`; "tool sudah dipakai" dibaca dari event `attempt_summary`.
- Crash di acceptance sebelum commit: verifikasi dijalankan ulang (sandbox read-only, idempoten), `verdict_<i>.json` ditimpa
  atomik. Butir 9 menjaga agar jalan ulang tidak membalik keputusan.

## 4. Penyalahgunaan

| Kasus | Mitigasi |
|---|---|
| Jalan keluar malas (tes lama benar) | Butir 5-6 memaksa fitur ada; manusia melihat diff tes lama di approve |
| Instruksi tertanam di teks repo | Laporan hanya berhasil bila bukti R2 ada; `reason` tak pernah tampil sebagai fakta |
| Tes lama flaky | Butir 9 |
| Agen melapor di setiap job | Laporan tak terkonfirmasi = attempt gagal; tool dicabut sesudah satu pemakaian |

## 5. Tes (gagal di kode lama) dan mutan

1. Tes lama pecah karena fitur, agen melapor → run `BLOCKED/test_conflict`, job `CONFLICT`, `retry` ditolak.
2. Satu tes merah lain yang tidak disebut → tidak terkonfirmasi; umpan balik menyebut butir 3.
3. Node yang disebut adalah tes baru draf, atau berkasnya tidak protected → tidak terkonfirmasi.
4. Tes itu sudah merah di baseline → tidak terkonfirmasi.
5. `must_pass` merah, diff kosong, hit `no_test_detection`, merah karena `ImportError` → tidak terkonfirmasi (satu kasus masing-masing).
6. Baseline hijau lalu merah (flaky tiruan) → tidak terkonfirmasi.
7. Laporan kedua dalam satu run: tool tidak ditawarkan.
8. Crash sesudah tool, dan sesudah verdict: resume memberi state yang sama, tanpa panggilan model.
9. `status` memuat baris R5; `reason` berisi escape ANSI tampil bersih.
10. `redraft --from-conflict`: approve menolak draf tanpa berkas itu di `changed_tests`; kedua kalinya ditolak.

Mutan: tiap butir R2 dibuang satu per satu; `==` jadi `⊆`; ulangan jadi sekali; `retry` diizinkan; tool tetap ditawarkan;
`reason` tanpa `clean`; batas 5 dibuang; gerbang approve dibuang.

## 6. Proses

Seperti AGENTS.md: tes merah → kode → `/code-review medium` + `/security-review` → mutan → satu `verify_at` → "merge" Atha.
Dua PR: (a) tool, verifikasi, state; (b) `--from-conflict` dan layar.

## 7. Di luar cakupan

Mengubah tes lama secara otomatis; menilai tes mana yang benar; perbaikan verdict (kanari, nonce); putaran otomatis ke
penulis issue (dicatat saja di `job.json`).

## 8. Dua pertanyaan

**(1) Sebelum perbaikan verdict?** Bisa. Konflik terkonfirmasi tidak pernah menjadi pass atau applied, jadi pemalsu hanya
memperoleh berhenti. Sampai kanari dan nonce ada, jangan percaya sebagai bukti: butir 2, 3, 5 dan 8 (dibaca dari proses yang
memuat kode agen). Yang kuat sekarang: butir 4, 6, dan 7 (baseline tanpa kode
agen). Maka: tidak ada perubahan tes tanpa approve manusia.

**(2) Hit gerbang deteksi tes?** Jadikan terminal sesudah `ReportConflict` hidup: `FAILED_ACCEPTANCE`, `stop_reason:
test_detection`, hit ditampilkan ke manusia dan tidak diumpankan ke agen. Umpan balik mengajari pola mana yang harus
dihindari; jalan keluar yang sah sudah ada. PR tersendiri.
