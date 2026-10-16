# Pekerjaan tervalidasi yang hilang di langkah terakhir: desain (untuk review, belum ada perubahan kode)

Status: **draf desain**, 2026-10-16. Baseline: eksperimen live search-value #1 (`docs/reviews/SEARCH_LIVE_1.md`, PR #58).
Belum ada perubahan harness, kenaikan budget, maupun run live baru.

## 1. Masalah, dari data baseline

Enam dari sembilan run memperbaiki bug dengan benar, tapi tidak satu pun sempat memanggil `Finish`:

| Run | Panggilan ke-5 (menulis fix) | Kumulatif setelah fix | Input yang dibutuhkan `Finish` | Kekurangan | Verdict attempt 1 |
|---|---|---|---|---|---|
| c2 | input 7.604 | 23.605 | 9.775 | 3.444 | hanya `SUMMARY.json` dan `claims` gagal |
| a2 | 7.857 | 25.065 | 9.951 | 5.080 | sama |
| b1 | 7.031 | 23.122 | 9.181 | 2.367 | sama |
| c3 | 7.630 | 23.983 | 9.780 | 3.827 | sama |
| b2 | 7.245 | 24.090 | 7.604 | 1.758 | sama |
| c1 | 7.629 | 24.293 | 9.779 | 4.136 | sama |

Setelah attempt pertama, **harness sudah tahu** bahwa kedua validasi lulus dan file mana yang berubah. Semua itu ada di
`verdict_0.json`:
- `validation:*` dengan jumlah tes dan status setiap tes wajib;
- `scope:writable` dengan `diff.modified`.

Tapi umpan balik ke attempt berikutnya (`feedback_from`) hanya berisi kriteria yang gagal:
`SUMMARY.json is missing` dan `no valid SUMMARY.json…`. Agen tidak diberi tahu bahwa validasinya sudah lulus. Ia
memulai diagnosis dari nol dan kehabisan reservasi lagi.

## 2. Dua mekanisme yang diusulkan review, diuji dengan data

### 2.1 Resume dari bukti tervalidasi (usul utama)

Umpan balik untuk attempt berikutnya ditambah satu bagian, **"keadaan workspace menurut pemeriksaan harness"**. Isinya
diambil dari verdict attempt sebelumnya (pemeriksaan harness sendiri, ditulis atomik sebelum umpan balik dibuat).

Contoh untuk c2:

```
The previous attempt did not meet the contract. The harness found:
  - artifact:SUMMARY.json: SUMMARY.json is missing
  - claims: no valid SUMMARY.json, so no completion claim can be checked
The harness's own checks of the current workspace (it is kept between attempts):
  - validation:unit: pass (8 tests, 0 failures, 0 skipped)
  - validation:target: pass (5 tests; required tests: 5 ok)
  - files changed from the original: src/steps/prepare.py
```

- **Tidak menandai DONE lebih awal.** Acceptance tidak berubah. Setelah `Finish`, harness tetap menjalankan semua
  validasi dari awal, memeriksa scope, dan memeriksa setiap klaim terhadap buktinya sendiri. Jika workspace berubah
  setelah umpan balik, verdict baru yang berlaku.
- **Jujur terhadap kegagalan.**
  - Kalau validasi gagal, umpan baliknya bilang gagal, dengan alasan dari verdict.
  - Klaim `issue_fixed` tanpa bukti tetap menggagalkan task dan tercatat sebagai klaim palsu.
  - Kalau budget tidak cukup untuk attempt berikutnya, hasilnya tetap `FAILED_ACCEPTANCE`.
- **Teks hanya berisi fakta dari verdict:** status, jumlah tes, dan path. Tidak ada saran ("you may call Finish"), supaya
  tidak mendorong klaim. Agen tetap memutuskan sendiri.
- **Crash-resume.**
  - Umpan balik dibangun deterministik dari `verdict_<i>.json` dan disimpan di state yang di-checkpoint (`feedback`,
    sudah ada).
  - Teksnya masuk ke `HumanMessage`, jadi ikut identitas input setiap step key.
  - Tidak ada efek samping baru, panggilan model baru, atau perubahan reservasi dan ledger.
- **Perbandingan dengan baseline.** Prompt attempt pertama tidak berubah. Hanya attempt ke-2 dan seterusnya yang
  menerima bagian baru. Prompt sistem juga tidak berubah.
- **Batas ukuran.** Daftar path dibatasi (misalnya 20 path, sisanya "… and N more"). Tidak ada isi diff, karena agen
  bisa membaca file sendiri.

**Perkiraan dampak pada baseline (hipotesis, belum diuji):** attempt kedua cukup satu panggilan `Finish` dengan konteks
awal sekitar 2.000–2.500 token, jauh di bawah reservasi. Keenam run akan berakhir `DONE` **jika** agen memilih
`Finish` dengan klaim yang didukung bukti, dan acceptance ulang lulus. Apakah agen memilih itu atau mendiagnosis ulang
adalah perilaku model, dan hanya live yang menjawab.

### 2.2 Completion reserve: versi naif merugikan; versi ringkas mungkin berguna

**Versi naif** (sisakan budget untuk satu `Finish` dengan konteks penuh) diuji pada baseline:

| Run | Kumulatif setelah fix | Kebutuhan `Finish` + 400 output | 30.000 − kebutuhan ≥ kumulatif? |
|---|---|---|---|
| c2 | 23.605 | 10.175 | **tidak** |
| a2 | 25.065 | 10.351 | **tidak** |
| b1 | 23.122 | 9.581 | **tidak** |
| c3 | 23.983 | 10.180 | **tidak** |
| b2 | 24.090 | 8.004 | **tidak** |
| c1 | 24.293 | 10.179 | **tidak** |

Dengan reserve sebesar itu, panggilan yang menulis fix **tidak akan diizinkan di satu pun run**. Reserve itu
mengganti "fix tanpa ringkasan" dengan "ringkasan tanpa fix", dan itu lebih buruk. Biaya `Finish` bukan konstan:
ia tumbuh bersama percakapan.

**Versi ringkas (opsional, tahap kedua).** Ketika panggilan biasa berikutnya tidak lagi muat, harness tidak langsung
mengakhiri attempt. Ia membuat satu panggilan penutup yang hanya menawarkan `Finish`, dengan **konteks baru yang
ringkas**:
- prompt sistem;
- task;
- keadaan workspace dari pemeriksaan harness seperti 2.1. Untuk itu harness perlu menjalankan validasi di dalam
  attempt.

Konteks itu sekitar 2.500 token, jadi reserve-nya sekitar 3.000. Di keenam run baseline, 30.000 − 3.000 = 27.000
lebih besar dari kumulatif setelah fix (23–25 ribu), sehingga fix dan penutupnya akan muat dalam attempt pertama.

Kekurangannya:
- mekanisme baru di dalam loop (panggilan penutup, validasi di tengah attempt, kunci memo baru);
- risiko mendorong agen menulis ringkasan sebelum pekerjaannya selesai.

### 2.3 Usul urutan

1. **2.1 dulu.** Paling kecil: hanya umpan balik antar-attempt, dari bukti yang sudah ada. Tanpa perubahan budget,
   reservasi, atau loop.
2. Ukur. Kalau agen tetap mendiagnosis ulang meski diberi bukti, atau kalau biaya attempt tambahan terlalu besar,
   baru desain 2.2 versi ringkas, dengan review sendiri.
3. **Versi naif 2.2 tidak dikerjakan**, karena data baseline menunjukkan ia memblokir perbaikan.

## 3. Tes yang direncanakan (model palsu, tanpa biaya)

| Kasus | Yang harus terjadi |
|---|---|
| Validasi lulus, `SUMMARY.json` hilang | attempt 2 menerima status validasi dan path yang berubah; model palsu langsung `Finish`; status `DONE` dengan 1 panggilan di attempt 2; acceptance menjalankan ulang semua validasi |
| Validasi gagal | umpan balik bilang gagal dengan alasannya; tidak ada teks "pass" untuk validasi yang gagal |
| Klaim tidak didukung bukti | umpan balik bilang target gagal; model palsu mengklaim `issue_fixed` → `FAILED_ACCEPTANCE` dan klaim palsu tercatat di honesty |
| Crash sebelum `Finish` di attempt 2 (`agent@after_llm`, `agent@after_tool:Finish`) | resume memakai umpan balik yang sama (step key sama); tidak ada panggilan model atau tool yang diulang setelah di-commit |
| Budget hampir habis | attempt 2 tidak muat di `max_usd` → tidak dijalankan; `FAILED_ACCEPTANCE` dengan alasan budget, bukan `DONE` |
| Workspace diubah agen di attempt 2 setelah umpan balik | verdict baru yang berlaku; umpan balik lama tidak pernah menjadi bukti acceptance |
| Attempt pertama | prompt attempt pertama identik dengan sebelumnya (hash dibandingkan) |

**Mutan yang harus tertangkap:**
- umpan balik melaporkan semua validasi lulus;
- umpan balik dari verdict attempt yang salah;
- bagian keadaan workspace hilang;
- umpan balik ikut dikirim ke attempt pertama.

## 4. Pengukuran setelah implementasi (perlu persetujuan terpisah)

Usul: ulangi seri yang sama (fixture `ledger`, A/B/C × 3, urutan dan cap identik dengan baseline), sehingga satu-satunya
perubahan adalah umpan balik attempt ke-2.

Dibandingkan dengan baseline #58:
- tingkat sukses task;
- biaya per task sukses;
- tingkat kegagalan jujur;
- diagnostik: berapa run yang `Finish` di attempt 2, berapa panggilan di attempt 2, dan apakah ada klaim palsu baru.

Hipotesis yang diuji: pekerjaan tervalidasi tidak lagi hilang di garis akhir. Hipotesis itu **tidak**
mengasumsikan bahwa search membantu.
