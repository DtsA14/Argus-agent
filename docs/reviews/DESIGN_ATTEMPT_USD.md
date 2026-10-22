# D1: anggaran attempt dalam USD, dengan batas masukan per panggilan (spesifikasi untuk review)

Status 2026-10-22: **spesifikasi; K1–K6 diputuskan (bagian 8).** Implementasi di PR terpisah. Asal: `pilots/m6_pilot3/3a/CONTEXT_DESIGN.md` (D1, dikoreksi di bagian 7). Menyentuh
aturan uang (`AGENTS.md`, "Budget and money"), jadi proses paling ketat: tes yang gagal di kode lama, mutan, `verify.sh` penuh, replay tanpa biaya, baru
satu run live setelah D3 juga ada (K4 D2).

## 1. Masalah (dari buku besar dua run live 3a)

Satu attempt dicadangkan sebagai **token kumulatif** (`attempt_tokens`, profil `large` = 45.000), lalu dihargai seolah semua token adalah output:
`attempt_usd = attempt_tokens × max(harga input, harga output)` = 45.000 × $10/M = $0,45 (`codetask/run.py:113–118`). Hampir semua token sebenarnya
input ($2/M) yang dikirim ulang tiap langkah. Akibatnya:

- `pilot3a` attempt 0 berhenti `reservation_exhausted` setelah 42.951 token, tetapi hanya membayar **$0,1128** dari $0,45 yang dicadangkan.
- Empat dari empat attempt di dua run berhenti karena token, tidak satu pun karena uang. Simulasi (`CONTEXT_DESIGN.md` bagian 3 dan 7) menunjukkan tidak ada kebijakan
  konteks yang membuat trajektori ini muat di 45.000 token, sedangkan anggaran USD $0,45 per attempt memuat attempt yang sama sampai selesai bila
  digabung dengan validasi otomatis (D3).

Token kumulatif adalah proksi biaya yang buruk; yang ingin dibatasi adalah uang (batas keras) dan ukuran konteks per panggilan (kualitas).

## 2. Mekanisme sekarang (tiga tempat)

| Tempat | Apa yang diperiksa | Kode |
|---|---|---|
| Reservasi attempt | tiap panggilan: masukan + `max_tokens` ≤ sisa token **dan** USD kasus terburuk ≤ sisa USD; kalau tidak, ditolak sebelum dikirim (`ReservationExhausted`) | `codetask/agent.py:164–170` (`reservation_from_ledger(tokens=attempt_tokens, usd=attempt_usd)`), `harness/llm.py:283–312` |
| Guard node `agent` | node melapor lebih dari `attempt_tokens` token atau `attempt_usd` → `EstimateExceeded` (kesalahan harness) | `codetask/run.py:311–312`, `harness/guard.py:76–83` |
| Admission run | attempt baru hanya bila token terpakai + `attempt_tokens` ≤ `budget.max_tokens` (200.000) **dan** USD terpakai + `attempt_usd` ≤ cap | `codetask/run.py:127–134` |

Pengecekan USD per panggilan **sudah ada** (`_output_cap`: `usd_left − USD(masukan) ≥ max_tokens × harga output`). D1 tidak menambah mekanisme uang baru; ia
memisahkan dua besaran yang sekarang terikat satu rumus.

## 3. Perubahan yang diusulkan

1. **Profil boleh menyatakan `attempt_usd` sendiri.** Bila ada, reservasi USD attempt = nilai itu; bila tidak, rumus lama (`attempt_tokens × harga termahal`). Profil
   `default` dan `large` yang ada **tidak diubah**, jadi semua kontrak yang sudah disetujui (yang membekukan nama profil) dan semua config pilot tetap berperilaku sama.
2. **Profil baru** (nama: K1), misalnya `large_usd`: `attempt_usd: 0.45`, `attempt_tokens: 400000` (batas token per attempt sebagai pengaman, bukan proksi biaya),
   `max_output_tokens: 8192`, `max_input_tokens: 40000`.
3. **Batas masukan per panggilan (`max_input_tokens`, opsional di profil).** Panggilan yang taksiran masukannya melebihi batas ditolak **sebelum dikirim**, dicatat di buku
   besar sebagai `refused` dengan alasan tersendiri (`input_limit`), dan attempt berakhir dengan alasan tersendiri (`context_limit`, K5), bukan `reservation_exhausted`.
   Tempatnya di `LLMCaller` (`harness/llm.py`) lewat medan baru di `Reservation`, supaya penolakan dan pencatatannya satu jalur dengan penolakan anggaran.
4. **Guard dan admission memakai besaran yang sama:** guard node `agent` memakai `attempt_tokens` dan `attempt_usd` profil (sudah begitu, hanya nilainya berubah);
   admission run tetap `USD terpakai + attempt_usd ≤ cap`. Untuk token run-level (`budget.max_tokens`): K3.
5. **Laporan:** `budget_profile` di `result.json` dan event `budget_profile` mencatat `attempt_usd` dan `max_input_tokens` bila ada.

## 4. Jaminan uang yang tetap berlaku (dicek terhadap `AGENTS.md`)

- Setiap panggilan tetap lewat `LLMCaller.call`; ditolak sebelum dikirim bila USD kasus terburuk (masukan × harga input + `max_tokens` × harga output, dengan
  pengali puncak) tidak muat di sisa USD attempt. Cap run tetap min(`budget.max_usd`, kontrak).
- `llm_call_started` sebelum kirim, `llm_call` sesudah; `unknown_after_crash` tetap dibebankan kasus terburuk; reservasi dimulai dari buku besar (`reservation_from_ledger`).
- Model tanpa harga tetap ditolak selama `max_usd` terbatas; biaya yang tak diketahui tetap `null`.
- **Batas yang tidak boleh dilebih-lebihkan:** untuk provider selain Anthropic, masukan dihitung heuristik (margin 1,2), jadi USD kasus terburuk di sana bukan batas
  keuangan absolut. Untuk Anthropic penghitungnya eksak.
- Yang berubah secara nyata: attempt yang dulu berhenti di ±$0,11 karena token sekarang boleh berjalan sampai $0,45. **Uang per attempt yang bisa dipakai naik ±4×
  pada cap yang sama** (K2).

## 5. Kompatibilitas

- Kontrak yang sudah disetujui membekukan **nama** profil (`fix_run_inspectors`, `fix_is_peak`, `fix_window_strict`: `large`). Karena `large` tidak berubah, perilaku
  mereka tidak berubah. Run 3a berikutnya dengan profil baru butuh **versi kontrak baru** yang disetujui ulang (K4); itu jujur karena anggarannya memang berubah.
- Config pilot lama (`config_pilot3a.yaml`, dst.) menyalin bagian `profiles`; profil baru tidak ada di sana, dan gerbang `go_live.sh` sudah menolak config lama sejak D2.
- Memo dan `prompt_hash` tidak berubah oleh D1 (hanya admission). Replay run lama dengan config lama tetap identik.

## 6. Tes (gagal di kode lama karena assertion) dan mutan

Wajib:
- T1 profil dengan `attempt_usd: 0.45` dan `attempt_tokens: 400000`: model berharga terskrip (penghitung terkalibrasi) yang memakai > 45.000 token kumulatif tetapi < $0,45
  menjalankan semua panggilannya; dengan profil `large` lama, panggilan yang sama ditolak (`reservation_exhausted`).
- T2 panggilan yang USD kasus terburuknya melebihi sisa USD attempt ditolak **sebelum dikirim** (tidak ada `llm_call_started`), buku besar mencatat `refused`.
- T3 masukan di atas `max_input_tokens` ditolak sebelum dikirim dengan alasan `input_limit`, attempt berakhir `context_limit`; tepat di batas diterima.
- T4 admission run: attempt berikutnya diterima tepat bila USD terpakai + `attempt_usd` ≤ cap (batas ± satu nano-dolar).
- T5 guard: node yang melapor > 45.000 token tetapi ≤ `attempt_tokens` profil baru tidak memicu `EstimateExceeded`; melebihi `attempt_usd` tetap memicunya.
- T6 profil tanpa `attempt_usd` memberi `attempt_usd` persis seperti rumus lama (perlindungan kompatibilitas).

Penjaga: tes profil yang ada (`test_a_profile_changes_only_the_attempt_reservation_and_the_output_cap`, `test_choosing_a_profile_never_changes_the_cost_cap`,
`test_large_at_*`) tetap lulus tanpa diubah; tes crash-resume dan buku besar yang ada tetap lulus.

Mutan: harga input dan output tertukar di kasus terburuk; suku masukan dihapus dari kasus terburuk; `attempt_usd` profil diabaikan (kembali ke rumus lama); batas masukan
meleset satu (`>` jadi `>=`); penolakan batas masukan tidak dicatat di buku besar; admission memakai rumus lama untuk profil baru; guard memakai 45.000 tetap.

## 7. Verifikasi tanpa biaya

`replay_3a.py` dengan config yang memetakan profil `large` ke nilai profil baru **hanya untuk replay** (attempt_usd 0,45, token 400.000, masukan 40.000): panggilan
`it0 s3` (27.252 token masukan, tercatat ditolak) harus **diterima**. Balasannya tidak pernah direkam, jadi responder replay gagal di sana dan attempt berakhir
`llm_failed`, dengan `requests_the_live_run_never_made` ≥ 1, bukan `reservation_exhausted`. Itu bukti bahwa batas bergeser ke tempat yang benar, tanpa memanggil model.

## 8. Keputusan (diputuskan Atha, 2026-10-22)

1. **K1:** profil baru `large_usd`; `large` tidak diubah (bagian 5).
2. **K2:** `attempt_usd` $0,45, `attempt_tokens` 400.000 (hanya pengaman: 400.000 token termurah pun $0,80 pada harga Sonnet, jadi batas USD selalu mengikat
   lebih dulu), `max_input_tokens` 40.000, `max_output_tokens` 8.192. Diterima: uang per attempt yang bisa dipakai naik dari ±$0,11 ke paling banyak $0,45.
   **Konsekuensi yang dicatat:** dengan cap $0,75, attempt kedua hanya diterima bila attempt pertama menghabiskan ≤ $0,30 (admission: terpakai + $0,45 ≤ cap),
   sedangkan simulasi D3 memberi ±$0,30–$0,37. Kalau attempt pertama gagal, run berhenti dengan jujur; cap tidak dinaikkan otomatis. Dua attempt penuh adalah
   keputusan terpisah saat kontrak `_v2` disetujui.
3. **K3:** `budget.max_tokens` dinaikkan **di config pilot** (1.200.000 = 3 × 400.000) dengan alasan tertulis; kode admission tidak mendapat cabang baru. Dengan
   `config.yaml` biasa (200.000) profil `large_usd` ditolak sebelum panggilan pertama (gagal tertutup). Gerbang `go_live.sh` perlu menerima selisih kedua ini
   saat config pilot `_v2` dibuat.
4. **K4:** run 3a berikutnya memakai `fix_run_inspectors_v2` (profil `large_usd`, sisanya sama: $0,75, 3 iterasi), disetujui ulang, setelah D3.
5. **K5:** `input_limit` (alasan penolakan di buku besar) dan `context_limit` (akhir attempt).
6. **K6:** `max_steps` tetap 12 (dengan D3 simulasi butuh 8; satu perubahan sekaligus).
