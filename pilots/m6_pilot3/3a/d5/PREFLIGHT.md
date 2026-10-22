# Pilot 3a D5: preflight (ditulis sebelum run)

Status 2026-10-22: **persiapan; belum ada run live.** Spesifikasi: `docs/reviews/SPEC_D5_prompt_caching.md` bagian 8. Pertanyaannya:
dengan prompt caching, berapa biaya trajektori seperti `pilot3a4`, dan apakah **dua putaran perbaikan** muat dalam satu attempt. Kalau tidak,
baru lanjut ke D4.

## 1. Sama dengan `pilot3a4`, kecuali satu hal

| | `pilot3a4` | D5 |
|---|---|---|
| Kontrak | `fix_run_inspectors_v2` (`ca8a521eb8b7`), profil `large_usd`, $0,75, 3 iterasi | **sama** (tidak disetujui ulang) |
| Model, issue, scope, alat, validasi | Sonnet 5.5, … | **sama** |
| Anggaran | attempt $0,45, masukan ≤ 40.000 per panggilan, keluaran 8.192, 12 langkah, validasi otomatis 4 | **sama** |
| Config | `config.yaml` + `max_usd` 0,75, `max_tokens` 1.200.000, `auto_validate` true | yang sama **+ `llm.prompt_cache.enabled` true** |

Selisih `d5/config_pilot3a_d5.yaml` terhadap config yang dipakai `pilot3a4` (`v2/config_pilot3a_v2.yaml`): hanya `llm.prompt_cache` dan kolom
cache di tabel harga (tarif write baru; Sonnet `cache_read` 0,20 → 0,10 yang sudah dikoreksi). Kolom cache itu tidak pernah terpakai di
`pilot3a4` (tanpa caching, read dan write 0), jadi biaya `pilot3a4` sama di bawah tabel mana pun.

## 2. Apa yang berubah di run karena caching (dan yang tidak)

- Penanda cache dipasang hanya di request yang dikirim: blok sistem (alat + sistem di-cache bersama) dan blok terakhir (prefix bergulir).
  Diperiksa tanpa API (`d5/payload_check.py`, keluaran `payload_check_output.txt`): untuk request pertama, setelah langkah alat (`tool_result`),
  dan setelah pesan validasi otomatis D3, penanda ada tepat di blok sistem dan blok terakhir, ≤ 4, dan pesan yang disimpan harness tanpa penanda.
- **Penolakan sebelum kirim lebih ketat:** tiap token masukan dicadangkan dengan tarif write $2,50/M (tanpa caching $2/M). Pada masukan
  35.000: ±$0,0875 masukan + keluaran. Penghematan baru terlihat di biaya aktual di buku besar, yang membuat sisa attempt lebih longgar.
- Hash prompt, kunci memo, dan audit tidak berubah (diuji di D5).

## 3. Ekspektasi (sebelum run)

Perkiraan bila agen mengulang 8 panggilan `pilot3a4` (masukan 3.097 → 32.617) dan cache bekerja seperti loop yang sehat (tiap panggilan
membaca seluruh prefix sebelumnya dan menulis bagian barunya saja; minimum 512 token terlampaui): masukan ±$0,096 + keluaran ±$0,040 =
**±$0,14 untuk 8 panggilan** (`pilot3a4`: $0,3947). Langkah eksplorasi sebelum tulisan pertama (s0–s5): **±$0,08** (`pilot3a4`: $0,2364).
Dengan sisa ±$0,30 di attempt, ada ruang untuk beberapa putaran perbaikan; `max_steps` 12 bisa menjadi batas yang mengikat (itu hasil, bukan
alasan menaikkannya). Agen tidak deterministik: jalur langkahnya bisa berbeda dari `pilot3a4`.

## 4. Kriteria (ditetapkan sebelum run, tidak diubah sesudahnya)

**A. Caching bekerja (syarat D5):**
1. `cache_read > 0` di setiap panggilan mulai panggilan kedua tiap attempt; `cache_creation` tercatat (bukan `null`); tidak ada
   `cache_ttl_unexpected`.
2. Penghematan: `result.json` `cache.usd_saved_estimate` ≥ 50% dari biaya tanpa cache untuk panggilan yang sama
   (`usd_saved_estimate / (usd_billed + usd_saved_estimate)` ≥ 0,5).
3. Aturan uang: tidak ada `budget_violation` atau `estimate_overrun`; `usd_complete` true; `audit_run.py` 0 mismatch.

**B. Pertanyaan D5:** apakah **≥ 2 putaran perbaikan** (validasi otomatis sesudah tulisan kedua dan ketiga) terjadi di attempt 0, dan berapa
tes wajib yang masih gagal sesudahnya. Jawabannya ya atau tidak, dengan angka. Kalau tidak, langkah berikutnya D4.

**C. Dicatat, bukan lulus/gagal:** jumlah langkah eksplorasi sebelum tulisan pertama dan alat yang dipakai (dibanding `pilot3a4`: 6 langkah),
token masukan, read, dan write per panggilan, biaya per langkah, puncak masukan, status akhir, durasi sandbox per `origin`, dan apakah agen
memanggil `RunValidation` sesudah validasi otomatis. `DONE` bukan syarat D5.

Status apa pun (`FAILED_ACCEPTANCE`, `FAILED_BUDGET`, `BLOCKED`, `reservation_exhausted`, `context_limit`, `max_steps`) dicatat dan **berhenti**:
tidak ada run ulang, kenaikan cap, atau perubahan config tanpa persetujuan baru. `--resume` hanya untuk run yang mati.

## 5. Gerbang (`d5/go_live.sh`, diuji di `d5/gl_test.sh`)

1. Kontrak `fix_run_inspectors_v2`, sha256 `ca8a521eb8b7`, `large_usd`, $0,75 / 3 iterasi, tiga berkas writable.
2. Config: sha256 berkas yang direview; selisih dari `config.yaml` **persis empat** kunci (`max_usd`, `max_tokens`, `auto_validate`,
   `prompt_cache.enabled`).
3. Batas efektif dihitung dengan fungsi run: seperti `pilot3a4`, ditambah caching aktif untuk role coder (`prompt_cache_for`) dan harga Sonnet 5.5
   yang diverifikasi (2 / 10 / read 0,10 / write 5m 2,50 / write 1h 4).
4. Tanpa `ARGUS_LIVE=1` runner menolak tanpa membuat direktori run; id run `pilot3a[5-9]`; id yang sudah ada ditolak.
5. Kunci diketik Atha di prompt skrip; **paste sekali, lalu Enter**. Skrip mencetak panjang kunci (kunci Anthropic ±108 karakter; dua kali lipat
   berarti ter-paste dua kali: hentikan dengan Ctrl-C sebelum Enter berikutnya). Bila kunci salah, sejak PR #132 run berakhir `BLOCKED
   provider_failed` dengan $0.

## 6. Urutan

| # | Langkah | Persetujuan |
|---|---|---|
| 1 | Merge PR ini (config, gerbang, tes gerbang, cek payload, preflight) | Atha |
| 2 | Checkout live ke `main`, `go_live.sh --check-only` | |
| 3 | Run live **satu kali**: `bash ~/pilot3a_live/pilots/m6_pilot3/3a/d5/go_live.sh pilot3a5` | **Atha, "go live"** |
| 4 | Laporan menurut bagian 4 | |
