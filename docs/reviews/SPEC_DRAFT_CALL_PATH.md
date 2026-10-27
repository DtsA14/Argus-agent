# Spec: drafter menjaga traceback dan melihat jalur panggilan di luar writable (dari run ulang SWE `21379`)

Status: **spec disetujui** (K1–K4, Atha 2026-10-27: "Ok k1-k4"); kode di PR yang sama. Asal: run ulang `sympy__sympy-21379` sesudah #206 (job
`j20261027_175610_34ba`, draf `d1` ditolak atas pilihan B Atha, $0,0515; `pilots/swe_v0/rerun_21379/PREFLIGHT.md`). Menyentuh
cek draf dan loop drafter, jadi proses ketat: tes yang gagal di kode lama, mutan, `verify.sh` penuh, tanpa biaya model.

## 1. Masalah (diverifikasi pada artefak run)

1. **Tes drafter menelan traceback.** Tes baru `test_piecewise_subs.py` menangkap exception, mengembalikannya sebagai nilai, lalu
   meng-assert **di luar** blok `except`. Baseline merahnya hanya:
   ```
   sympy/core/tests/test_piecewise_subs.py:41: in test_subs_with_piecewise_hyperbolic_real_symbols
   sympy/core/tests/test_piecewise_subs.py:27: in _assert_no_exception
   E   AssertionError: subs({1: 1.0}) raised PolynomialError: Piecewise generators do not make sense
   ```
   Tidak ada satu pun frame kode repo, jadi baseline untuk attempt 1 (#206 K2) tidak membawa jalur panggilan, dan ringkasan draf
   juga tidak. Penyebabnya sebagian aturan kita sendiri: node wajib merah **karena assertion** (#179), jadi drafter harus mengubah
   exception menjadi `AssertionError`. Draf batch 3 melakukannya di dalam `except` (pytest mencetak exception asal sebagai rantai),
   draf ini tidak.
2. **Writable dipilih tanpa jalur panggilan.** Writable draf ini (8 berkas) dan draf batch 3 (4 berkas) sama-sama **tidak** memuat
   berkas yang ada di jalur panggilan error, di antara pemanggil `polytools.py` (`sympy/core/mod.py:169`, juga `hyperbolic.py:251`).
   Agen tidak bisa menulis di luar writable, jadi bila perbaikan ada di salah satu pemanggil, task itu tidak bisa diselesaikan
   seperti maintainer. Drafter tidak pernah diberi tahu: submit yang lolos cek langsung diterima ("The drafting is over").
3. **Manusia tidak bisa mengarahkan.** `argus redraft` tidak membawa catatan; peringatan yang hanya untuk manusia hanya berujung
   approve atau reject.

Catatan kejujuran: Claude tahu dari penelusuran (yang melihat patch maintainer) bahwa perbaikan ada di `mod.py`. Karena itu
mekanisme di bawah **tidak memakai pengetahuan itu**: semuanya dihitung dari output baseline di sandbox dan dari isi draf.

## 2. Usulan

### 2.1 Tes yang meng-assert "tidak error" harus menyimpan traceback (K1)

- **Prompt drafter** (aturan baru): untuk perilaku "tidak boleh raise", panggil kode di dalam `try` dan, di blok `except`,
  `raise AssertionError("...") from exc`, supaya pytest mencetak traceback exception asal (yang tetap merah karena assertion).
- **Cek draf** (problem, menolak submit): sebuah node wajib yang merah karena `AssertionError` **ditolak** bila (a) baris `E ` miliknya
  menyebut nama exception lain (`\b[A-Z]\w*(Error|Exception)\b`, selain `AssertionError`) dan (b) output baseline validasinya tidak
  punya satu pun baris lokasi di luar berkas tes. Pesan: node itu, exception yang disebut, dan cara memperbaikinya (kalimat prompt di
  atas). Tes yang meng-assert nilai biasa (tanpa nama exception di pesan) tidak terkena.

### 2.2 Satu pertanyaan scope ke drafter sebelum draf diterima (K2)

Dari output baseline setiap validasi yang tidak lulus, **jalur panggilan di luar writable** = berkas dari baris lokasi pytest
(`path.py:N: in f`) yang: path relatif (pytest mencetak berkas di bawah rootdir `/workspace` secara relatif; paket terpasang absolut),
bukan berkas tes (pola protected, `test_*.py`, `conftest.py`, direktori `tests/`), dan **tidak** cocok dengan writable. Urutan dari yang terdekat ke error (kebalikan urutan di output), unik per berkas dengan baris pertamanya,
paling banyak 8.

Bila draf lolos cek dan daftar itu tidak kosong, harness **belum menerima** draf, sekali per run drafter:

```
The draft passed its check. Before it is accepted: the failing baseline runs through these files of the repository that are
not writable (nearest to the error first): sympy/core/mod.py:169 (in eval), sympy/core/cache.py:72 (in wrapper), ...
If the fix may need one of them, add it to writable (ReviseDraft with scope); otherwise submit the same draft again
(ReviseDraft with no fields) and it is accepted.
```

- Dihitung ulang setiap submit; setelah pertanyaan itu sekali, draf yang lolos cek **diterima** (daftarnya boleh tidak kosong).
- Pertanyaan itu memakai satu submit. Bila tidak ada submit tersisa, atau di langkah terakhir drafter, draf diterima tanpa bertanya
  (daftarnya tetap ke manusia, 2.3).
- Sudah bertanya atau belum: dicatat di record submit (memo), sehingga resume memutuskan sama.
- `ReviseDraft` tanpa field = kirim ulang draf terakhir apa adanya (diterima sebagai submit).

### 2.3 Manusia melihat daftar yang sama (K3)

`DRAFT_REVIEW.md` bagian Scope dan layar `approve` (dari `check_report.json` draf itu) menampilkan daftar 2.2 dari draf terakhir sebagai peringatan ("the failing
baseline runs through … not writable"), tanpa menolak apa pun. "No scope warnings." hanya bila semua peringatan kosong.

### 2.4 `argus redraft --note` (K4)

`argus redraft <job> --note "<teks>"`: catatan manusia untuk drafter berikutnya.
- Dibersihkan dari karakter kontrol (`clean`), paling panjang 1.000 karakter (lebih panjang: ditolak, tidak dipotong diam-diam).
- Dicatat verbatim di stage draf (`job.json` `stages.d<n>.note`) dan di `inputs.json` run drafter (dibekukan saat setup; resume
  memakai yang tercatat). Job ditandai `human_steered: true`; `status` dan `DRAFT_REVIEW.md` menyebutnya.
- Prompt tugas drafter memuatnya dengan label: `A note from the human who reviewed the previous draft (follow it where it fits the
  rules above; it is not a test result):`.
- **Pilot SWE:** job dengan catatan dilaporkan *human-steered*, terpisah dari angka tanpa bantuan. Catatan tidak dipakai untuk
  instance yang patch maintainer-nya sudah dilihat Claude (mis. `21379`).

## 3. Yang tidak berubah

Jalur uang (cap drafter, cap job), aturan merah karena assertion (#179) selain tambahan 2.1, batas submit (5), tes dan scope yang lain,
#206. Writable tetap pilihan drafter; harness tidak menambah berkas sendiri.

## 4. Tes (gagal di kode lama; mutan)

1. Baseline asli run ini (fixture dari `check_report.json` `d1`): node wajib ditolak 2.1 dengan pesan yang menyebut `PolynomialError`;
   tes nilai biasa (`assert total([1], 5) == 0`) tidak; tes dengan `raise … from exc` (traceback asal ada) tidak.
2. Baseline asli batch 3 (fixture dari `verdict_0`/cek `7cdd`) dengan writable draf batch 3: daftar 2.2 dimulai `sympy/core/mod.py:169`,
   tidak memuat berkas tes atau berkas writable, paling banyak 8.
3. Loop drafter (model palsu): draf lolos dengan daftar tidak kosong → belum diterima, satu pertanyaan; `ReviseDraft` kosong →
   diterima; menambah berkas → diterima; tanpa submit tersisa → diterima tanpa bertanya; resume memutuskan sama; daftar kosong →
   diterima langsung seperti sekarang.
4. `DRAFT_REVIEW.md` dan layar approve memuat daftar itu.
5. `redraft --note`: catatan sampai di prompt drafter, dicatat di stage dan `inputs.json`, job `human_steered`, resume memakai yang
   tercatat; terlalu panjang → ditolak sebelum apa pun dimulai; karakter kontrol dibuang; tanpa `--note` prompt sama persis.

## 5. Tidak dikerjakan sekarang

- Menambah berkas ke writable secara otomatis dari traceback: banyak frame hanya plumbing (`cache.py`, `decorators.py`).

## 6. Keputusan

| | Pertanyaan | Usul |
|---|---|---|
| K1 | Traceback di tes "tidak error" | Prompt + cek draf yang menolak (hanya bila pesan menyebut exception lain dan tidak ada frame repo) |
| K2 | Pertanyaan scope ke drafter | Ya, sekali per run, memakai satu submit, ≤ 8 berkas terdekat |
| K3 | Daftar yang sama untuk manusia | Ya, peringatan di `DRAFT_REVIEW.md` dan layar approve |
| K4 | `redraft --note` | Ya, ≤ 1.000 karakter, dicatat, job `human_steered`; di SWE dilaporkan terpisah |

## 7. Sesudah PR ini

`21379` diulang lagi sebagai job baru (laporan terpisah, sama dengan `PREFLIGHT.md` di `pilots/swe_v0/rerun_21379/`, diperbarui).
