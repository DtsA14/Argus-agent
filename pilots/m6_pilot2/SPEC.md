# M6 pilot 2 (kandidat): validasi `--impl` di `main.py`: reproduksi dan spesifikasi acceptance

Status 2026-10-21: **untuk review. Belum ada draf, tes final, patch referensi, atau panggilan coder.** Pilihan: kandidat 1
dari opsi B (hanya `--impl`; skrip audit sengaja tidak digabung). Pertanyaan eksperimen: seberapa baik coder menyelesaikan
perubahan lintas berkas yang kecil tapi punya keputusan desain, dengan acceptance deterministik.

## 1. Reproduksi (VM, `main.py` pada `1b0780f`, pipeline default dengan node palsu: tanpa biaya)

`python main.py --quiet --scenario pass --runs-dir <tmp> --run-id p <flag>`; `main.py`, `models/registry.py`, dan
`graph.py` sama dengan `main` terbaru (tanpa diff).

| # | Flag | Exit | Yang terjadi | Masalah |
|---|---|---|---|---|
| 1 | (tanpa flag) | 0 | `DONE` | pembanding |
| 2 | `--impl evalutor=llm` (salah ketik node) | **0** | `DONE`, node diabaikan diam-diam | **cacat utama**: pengguna mengira memakai evaluator sungguhan, padahal evaluator palsu |
| 3 | `--impl =llm` (node kosong) | **0** | `DONE`, diabaikan | sama |
| 4 | `--impl evaluator` (tanpa `=`) | 1 | **traceback** `ConfigError ... got ''` dari `graph.py` | bukan pesan `config error:` seperti `--model`; pesannya tidak menyebut flag salah format |
| 5 | `--impl evaluator=` (kind kosong) | 1 | traceback yang sama | sama |
| 6 | `--impl evaluator=llmm` (kind salah) | 1 | traceback | sama |
| 7 | `--impl evaluator=LLM` (huruf besar) | 1 | traceback | sama |
| 8 | `--impl worker=fake --impl worker=llm` | 1 | yang terakhir menang diam-diam (`MissingApiKey` karena `llm`) | sama dengan `--model` (dict ditimpa); dicatat, tidak diubah |
| 9 | `--model janitor=anthropic:x` | 1 | `config error: unknown role 'janitor'; roles are [...]` | **pola yang harus ditiru** |
| 10 | `--model worker` | 1 | `config error: override must look like 'role=provider:model', got 'worker'` | pola yang harus ditiru |

**Cacat kedua (temuan saat reproduksi):** kasus 4, 5, 6, 7 gagal *setelah* run dimulai: direktori `<runs>/p` sudah dibuat
berisi `checkpoints.sqlite` dan `memo.sqlite`. Akibatnya perintah yang sudah dibetulkan dengan `--run-id` yang sama ditolak
(`RunExists`: "run 'p' already exists; use --resume"). Validasi harus terjadi **sebelum** run apa pun dimulai.

Tes subprocess `main.py` bisa berjalan di sandbox `argus` (dicoba di VM: `1 passed`, valid run `DONE` dengan `--runs-dir`
di tmp), jadi acceptance tidak butuh Docker di dalam sandbox dan tidak butuh git.

## 2. Perilaku yang ditetapkan (kontrak yang bisa diamati, bukan resep)

Hanya perilaku `main.py` dari luar; lokasi kode dan nama fungsi dibiarkan pada coder.

1. **Format.** Setiap `--impl` harus `node=kind` dengan node dan kind tidak kosong. Kalau tidak: stderr berawalan
   `config error:`, memuat item yang salah, **exit 1**, tanpa traceback. Pola sama dengan `--model` (kasus 10).
2. **Node dikenal.** Node harus salah satu dari `orchestrator`, `worker`, `synthesize`, `evaluator` (node yang punya
   implementasi di `graph.py`). Node lain: `config error:` yang memuat `unknown node '<node>'` dan **keempat nama yang
   valid**, exit 1 (pola kasus 9).
3. **Kind dikenal.** Kind harus tepat `fake` atau `llm` (huruf kecil, seperti `graph.py` hari ini; `LLM` tetap ditolak,
   tetapi sebagai `config error:`). Kind lain: `config error:` yang memuat node, nilai yang salah, dan `'fake' or 'llm'`.
4. **Sebelum apa pun berjalan.** Setiap penolakan terjadi sebelum direktori run dibuat dan sebelum pemeriksaan kunci API:
   `<runs-dir>/<run-id>` tidak ada sesudahnya, dan perintah yang dibetulkan dengan run id yang sama berjalan.
5. **Tidak berubah:** `--impl` valid (`worker=fake`, keempat node `fake`) berjalan `DONE` dengan keluaran akhir yang sama;
   tanpa `--impl` identik; `--model` (kasus 9 dan 10) identik; `--impl` yang diulang untuk node yang sama: yang terakhir
   menang (kasus 8, sama dengan `--model`).

**Di luar scope (dicatat di `unverifiable`, tidak diperiksa):** salah ketik node di bagian `impl:` pada file config (juga
diabaikan diam-diam, tetapi itu perubahan terpisah); apakah `llm` butuh kunci; `--scenario`, `--max-iter`; pesan persis
selain kata kunci di atas; ketahanan `graph.py` terhadap config buatan tangan.

## 3. Tes acceptance yang diusulkan (belum ditulis; subprocess `main.py` dengan `--runs-dir` di tmp)

Wajib (**harus gagal di baseline** karena assertion, bukan error):

| Node tes | Mengunci | Gagal di baseline karena |
|---|---|---|
| `test_a_mistyped_node_is_refused` (`evalutor=llm`) | kontrak 2: exit 1, `unknown node 'evalutor'`, keempat nama valid | exit 0 dan `DONE` |
| `test_a_second_mistyped_node_is_refused` (`synthesise=fake`) | sama, node lain | exit 0 |
| `test_an_empty_node_is_refused` (`=llm`) | kontrak 1 | exit 0 |
| `test_an_item_without_equals_is_refused_cleanly` (`evaluator`) | kontrak 1: `config error:`, tanpa traceback | traceback, tanpa `config error:` |
| `test_an_empty_kind_is_refused_cleanly` (`evaluator=`) | kontrak 1 | traceback |
| `test_an_unknown_kind_is_refused_cleanly` (`evaluator=llmm`) dan `worker=LLM` | kontrak 3 | traceback |
| `test_a_refused_flag_starts_nothing_and_the_corrected_command_runs_with_the_same_run_id` | kontrak 4 | typo menghasilkan `DONE` (baris pertama gagal); untuk kind salah, direktori run tertinggal |

Penjaga (lulus di baseline dan harus tetap lulus; tidak masuk `must_pass` karena aturan baseline merah W2a, tetapi
dijalankan bersama file target): `--impl worker=fake` `DONE`; keempat node `fake` `DONE`; tanpa flag `DONE`;
`--impl worker=llm --impl worker=fake` `DONE` (yang terakhir menang); `--model janitor=anthropic:x` tetap
`config error: unknown role`; `--model worker` tetap `config error: override must look like`.

Regresi dari tes yang ada: `tests/test_models.py` (`parse_overrides`, `apply_overrides`, `ModelRef`) harus tetap lulus
tanpa diubah.

## 4. Bukti bahwa tes membedakan implementasi benar dari yang hanya membuat tes hijau

Implementasi "kosong" yang harus tertangkap:

| Implementasi salah | Ditangkap oleh |
|---|---|
| Menghardcode `evalutor` | tes dua node berbeda (`evalutor`, `synthesise`) |
| Memvalidasi di `graph.py` (terlambat) | kontrak 4: direktori run tertinggal, run id yang sama ditolak |
| Hanya memeriksa kind, bukan node (atau sebaliknya) | tes node dan tes kind terpisah |
| Menolak semua `--impl` atau menelan error | penjaga valid (`DONE`) |
| Menormalkan `LLM` menjadi `llm` | tes `worker=LLM` |
| Pesan tanpa daftar node valid | tes node memeriksa keempat nama |
| Menangkap `ConfigError` tapi tetap menjalankan run | tes mengecek exit 1 dan tidak ada direktori run |
| Mengubah `--model` | penjaga `--model` dan `tests/test_models.py` |
| Mengganti `parse_overrides` agar menolak duplikat | penjaga "yang terakhir menang" |

Sebelum dibekukan, gue akan menjalankan tiap baris tabel itu sebagai mutan terhadap patch referensi (seperti W2a/W3): tiap
implementasi salah harus membuat minimal satu tes gagal; yang lolos berarti celah tes, bukan implementasi.

## 5. Batas perubahan dan konfigurasi yang diusulkan

- **Writable:** `main.py`, `models/registry.py`. **Protected:** `tests/**`, `conftest.py`, `graph.py`, `runner.py`,
  `config.yaml`, `harness/**`, `acceptance/**`, `codetask/**`, `tools/**`, `models/` selain `registry.py`, `nodes/**`,
  `evals/**`.
- Kenapa `graph.py` protected: validasi harus terjadi sebelum run, dan `graph.py` tidak boleh menjadi tempat jalan pintas.
- Patch referensi (manusia): sekitar 20–30 baris di dua berkas.
- Tools `search_files`, `edit_file`; profil `default`; cap `max_usd` 0.50; `max_iterations` 3; aturan henti dan prosedur
  pemulihan sama dengan pilot 1 (`pilots/m6_pilot1/PREFLIGHT.md`).
- Cek `.gitattributes` (tidak ada di Argus) dan batas patch dari `REVIEW_M6_W3.md` tetap berlaku.

## 6. Keputusan yang diminta dari review

1. `LLM` (huruf besar) ditolak (usulan) atau dinormalkan?
2. `--impl` berulang untuk node yang sama: tetap "yang terakhir menang" (usulan) atau ditolak?
3. Salah ketik node di file config: di luar scope (usulan) atau ikut?
4. Penjaga di bagian 3 tetap tidak masuk `must_pass` (aturan W2a), tetapi dijalankan di file target: setuju?

Setelah ini disetujui: bekukan kriteria, tulis tes dan patch referensi, jalankan mutan atas tabel bagian 4, lalu
`approve_draft.py` (cek baseline merah dan hijau di sandbox), dan baru lanjut ke langkah approval dan preflight seperti pilot 1.
