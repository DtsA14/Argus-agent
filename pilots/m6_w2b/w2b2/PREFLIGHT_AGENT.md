# Pilot W2b-2, langkah agen: preflight (ditulis sebelum run)

Status 2026-10-23: **task disetujui; agen belum jalan.** Bagian dari `w2b2/PREFLIGHT.md` (kriteria bagian 5 tetap
berlaku).

## 1. Jalan sampai di sini

| Run | Hasil | Biaya |
|---|---|---|
| `w2b2d1` | `DRAFTED`; disetujui sebagai `pr_title`, lalu ditemukan mustahil dikerjakan (tanpa `edit_file`, file 30 KB, output 4.096); agen **tidak** dijalankan (`live/w2b2d1/RESULT.md`) | $0,0933 |
| `w2b2d2` | `NO_DRAFT submits_exhausted`: cek tulis ulang bekerja; dua submit habis untuk regresi yang butuh `git` dan tes yang sudah lulus di `must_pass` (`live/w2b2d2/`) | $0,1874 |
| `w2b2d3` | **`DRAFTED`** di submit ke-5 (dari 5): argumen keliru, cek tulis ulang lalu `edit_file`, regresi `git` lagi, tes penjaga di `must_pass` lalu mengikuti petunjuk, diterima (`live/w2b2d3/`) | $0,1844 |
| **Drafter total** | | **$0,4651** |

Perbaikan harness di antaranya: PR #157 (`edit_file` dan cek tulis ulang) dan PR #158 (batas sandbox di prompt,
petunjuk tes penjaga, 5 submit).

## 2. Task yang disetujui

Atha menyetujui ("approve"): `approve_draft.py --draft runs/w2b2d3/draft.json --task pr_title2 --issue-file
runs/w2b2d3/issue.txt --max-usd 0.5 --max-iterations 3 --no-reference --approve` (`live/w2b2d3/approve_output.txt`).

| | |
|---|---|
| Record | `fixtures/intake/pr_title2.json`: `kind: task`, `feasibility: unproven`, basis `argus_p7`, tambahan `tests/test_review_pr_title.py` |
| Kontrak | `fixtures/contracts/pr_title2.json`, sha **`4de6373c659a`**: writable `codetask/review.py`, protected `tests/**`, tool tambahan `edit_file`, profil `default`, $0,50 dan 3 attempt |
| Validasi | `target` = `tests/test_review_pr_title.py` (9 tes, 5 wajib; 4 penjaga yang sudah lulus tetap harus lulus). **Tanpa validasi regresi**: tes lama paket review butuh `git`, yang tidak ada di sandbox. Penjaganya `verify.sh` saat patch diterapkan |
| Nilai yang diharapkan | Dicek Claude terhadap aturan issue, satu per satu: cocok |

## 3. Config dan gerbang

- `w2b2/config_w2b2_agent.yaml`: `config.yaml` dengan dua selisih, `code_task.auto_validate` true dan
  `llm.prompt_cache.enabled` true, seperti setup 3b tanpa kenaikan cap atau token.
- `w2b2/go_live_agent.sh`, dari gerbang 3b:
  - kontrak `pr_title2` dengan sha `4de6373c659a`, profil `default`, $0,50/3, satu berkas writable, `edit_file`, dan record
    `unproven`;
  - config persis dua selisih;
  - batas efektif: 30.000 token per attempt (dicadangkan $0,30), output 4.096, cap $0,50, attempt kedua hanya bila yang
    pertama ≤ $0,20;
  - tanpa `ARGUS_LIVE` ditolak, run id `w2b2a[1-9]`, bentuk kunci dicek, dan waktu terminal dicatat ke
    `~/argus-supervision.log`.
- Tes gerbang: `w2b2/gl_test_agent_output.txt`.

## 4. Ekspektasi (sebelum run)

Agen kemungkinan membaca `codetask/review.py` (±7.500 token) dan tes baru, lalu satu `EditFile` di `render_pr`.
Validasi otomatis jalan setelah perubahan. Risikonya profil `default`: input yang terakumulasi (system, tes, review.py,
hasil validasi) bisa mendekati 30.000 token sebelum `Finish`. Bila attempt pertama berakhir `reservation_exhausted`
setelah edit, workspace dipertahankan, dan attempt kedua (diizinkan bila yang pertama ≤ $0,20) tinggal memeriksa dan
`Finish`. Perkiraan **$0,05–0,20**, 1–2 attempt.

## 5. Kriteria

Tetap `w2b2/PREFLIGHT.md` bagian 5, nomor 3. **W2b-2 berhasil** bila agen `DONE`, paket review valid, patch diterapkan
ke `main` tanpa perubahan, dan `verify.sh` lulus. Selain itu: gagal, dicatat, berhenti.
