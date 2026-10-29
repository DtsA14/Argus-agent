# Dev set 1 (sesudah batch 4): hasil apa adanya

2026-10-28. Instance yang sudah gagal sebelumnya, dijalankan ulang di harness yang diubah sesudah batch 4. **Bukan klaim:**
instance ini sudah pernah dilihat (batch 3–4), dan harness diubah karena kegagalannya. Angka resolve rate tetap dari batch
dengan instance baru dan harness beku. DeepSeek V4.1 Flash, cap $1,00 per job.

## Run 1: harness `5466b94` (#215: ReadFile rentang baris, ListFiles dibatasi, issue 8.000, `max_steps` 30)

| Instance | Sebelumnya | Hasil | Biaya job |
|---|---|---|---|
| `23824` gamma | harness-blocked (issue 2.103 > 2.000) | **resolved** (1/1, 2/2), 1 attempt, 5 langkah. Tes draf di atas patch maintainer: lulus | $0,0133 |
| `21379` subs/Piecewise (`sympy_py39`) | 4 attempt `max_steps`/`context_limit` tanpa menulis | **resolved** (1/1, 91/91), 1 attempt, 14 langkah. Tes draf di atas patch maintainer: lulus | $0,0399 |
| `24562` Rational | 4 attempt `max_steps` tanpa menulis | gagal: a1 3 attempt (menulis di 2 attempt), retry a2 berakhir `FAILED_BUDGET` (184 token lewat plafon 400.000, di $0,036 dari $0,45) | $0,1610 |

Approve: "y" Atha untuk ketiganya (satu balasan). Retry otomatis atas "Auto retry aja bro".

Patch agen vs maintainer (dibuka sesudah grading):
- `21379`: sama dengan upstream: `PolynomialError` ditangkap di `gcd` dalam `Mod.eval` (`sympy/core/mod.py`). Writable
  draf 4 berkas di 3 paket; agen hanya menyentuh `mod.py`.
- `23824`: satu baris (`reversed(range(0, first_dum_pos))`), setara dengan fix upstream dengan cara lain.

Sesudah run 1: #216 (timeout validasi router 120 s) dan #217 (margin input heuristik DeepSeek 2,5, plafon `large_usd`
1,2 juta; `docs/reviews/SPEC_HEURISTIC_INPUT_MARGIN.md`).

## Run 2: harness `1a6c14a` (sesudah #216, #217), hanya `24562`

- Draf `d1` $0,0222, 4 submit, writable `sympy/core/numbers.py`, memuat kasus issue (`Rational('0.5','100') == 1/200`).
  **Di-approve oleh Claude atas delegasi "full auto" Atha**, bukan "y" Atha (tanpa red flag: writable satu berkas, tidak
  ada tes lama diubah, merah karena assertion).
- `a1` gagal (`FAILED_ACCEPTANCE`, $0,1801, 882 s): attempt 1 selesai di 16 langkah, sebagian tes target masih merah;
  attempt 2–3 (28 dan 30 langkah) membuat `numbers.py` tidak bisa di-import (pytest exit code 4 di semua validasi).
- **Tidak ada `budget_violation`**: satu panggilan ditolak sebelum kirim, dan job berakhir wajar, bukan `FAILED_BUDGET`
  (#217 bekerja).
- Retry `a2` **dihentikan atas permintaan Atha** setelah attempt 1 (`context_limit` sesudah 13 langkah, tanpa menulis);
  job di-`abandon`. Total job $0,2826 (ledger).
- Waktu: a1 882 s, 702 s di antaranya menunggu model (76 panggilan × ±9 s); 37 validasi, 0 timeout.

## Total dev set 1

2 dari 3 resolved (`23824`, `21379`). Biaya: run 1 $0,2142 + run 2 $0,2826 = **$0,4968**.

## Yang dipelajari

1. Alat baca adalah penghalang utama di batch 3–4: dengan rentang baris, dua instance yang dulu tidak pernah menulis
   selesai dalam 5–14 langkah.
2. `24562` sekarang gagal karena **mutu patch**, bukan karena alat atau budget: agen membaca dan menulis, tapi merusak
   `numbers.py` (4.487 baris) di attempt yang lebih panjang.
3. Kandidat jalur cepat: validasi dengan pytest exit code 4 (gagal collect/import) diberi umpan balik khusus ke agen
   ("berkasmu tidak bisa di-import"), supaya langkah tidak habis dengan berkas yang rusak.
4. Waktu run didominasi latensi model (±9 s per panggilan thinking). 30 langkah × 3 attempt bisa ±15 menit per stage.

## Koreksi diagnosis (2026-10-29, sesudah batch 5)

`24562` (`j20261028_051232_d2e8`, `j20261028_065812_5cb1`): `EditFile` menolak `sympy/core/numbers.py` (136 KB) 17 dan 14 kali.
"Mutu patch" (butir 2) adalah akibatnya: tanpa `EditFile` agen menulis ulang berkas 4.487 baris dengan `WriteFile` dan merusaknya.
Perbaikan: `EditFile` sampai 2 MB (PR sesudah batch 5).

## Koreksi: `24562` run 1 a2 harness-affected (2026-10-29, `SPEC_ESTIMATE_REASONING.md`)

`FAILED_BUDGET` di retry `a2` (`j20261028_051232_d2e8`, 400.184 dari 400.000 token) disebabkan bug harness: counter heuristik
tidak menghitung `reasoning_content` yang dikirim balik ke DeepSeek (79.307 karakter sebelum langkah 18), jadi langkah itu
lolos cek sebelum kirim lalu melewati reservasi. Dicatat **harness-affected**, terpisah dari kegagalan model (aturan sama
dengan `23824`). Run 1 juga sudah harness-affected oleh batas `EditFile` 100 KB (koreksi di atas). Angka tidak berubah;
tidak dijalankan ulang di dev set ini.
