# M6 pilot 2 (kandidat): validasi `--impl` di `main.py`: reproduksi dan spesifikasi acceptance

Status 2026-10-21: **spesifikasi disetujui (GPT); tes, patch referensi, mutan, dan cek draf di sandbox sudah ada; belum
di-approve, belum ada panggilan coder.** Pilihan: kandidat 1 dari opsi B (hanya `--impl`; skrip audit sengaja tidak digabung). Pertanyaan eksperimen: seberapa baik coder menyelesaikan
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

## 3. Tes acceptance (inventaris final: **7 wajib + 6 penjaga = 13 tes** di `tests/test_impl_flag.py`; subprocess `main.py` dengan `--runs-dir` di tmp)

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

**Enam penjaga** (lulus di baseline dan harus tetap lulus; tidak masuk `must_pass` karena aturan baseline merah W2a, tetapi
dijalankan bersama file target): (1) `--impl worker=fake` `DONE`; (2) keempat node `fake` `DONE`; (3) tanpa flag `DONE`;
(4) `--impl worker=llm --impl worker=fake` `DONE` (yang terakhir menang); (5) `--model janitor=anthropic:x` tetap
`config error: unknown role`; (6) `--model worker` tetap `config error: override must look like`.
Ringkasan sebelumnya yang menyebut empat penjaga salah; inventaris di atas yang berlaku.

Regresi dari tes yang ada (validasi `regression`, 18 tes): seluruh `tests/test_models.py` (15 tes) dan tiga alur `main.py` di
`tests/test_milestone1.py` (`test_pass_first_try`, `test_fail_then_pass_uses_feedback`, `test_iteration_budget`), tanpa diubah.
Satu tes di file lain yang membaca `verification/` tidak ikut (tidak ada di snapshot).

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

## 6. Keputusan (GPT, 2026-10-21)

1. `LLM` huruf besar **ditolak**; kind harus tepat `fake` atau `llm`; tidak ada normalisasi diam-diam.
2. `--impl` berulang untuk node yang sama: **yang terakhir menang** (perilaku yang ada dipertahankan).
3. Salah ketik node di `impl:` pada file config: **di luar scope**.
4. Penjaga tidak masuk `must_pass` (aturan baseline merah W2a) tetapi dijalankan di file target.

## 7. Hasil artefak (VM, sandbox `argus`; tidak ada panggilan model)

| Artefak | Hasil |
|---|---|
| `new_test.txt` / `draft.json` | 13 tes: 7 wajib, 6 penjaga |
| Baseline (host, tes ditambah tanpa perbaikan) | 7 gagal (persis tujuh tes wajib), 6 lulus |
| `reference.patch` | dua berkas, +22/-4 baris (`main.py`, `models/registry.py`); dengan patch: 13/13 lulus, regresi 18/18 lulus |
| Mutan (`mutants.log`) | **11/11 tertangkap**; 11 mutan memetakan sembilan baris tabel bagian 4 (baris "hanya kind atau hanya node" dan "tolak semua atau telan error" masing-masing dua mutan) |
| `check_report.json` (`approve_draft.py`, tanpa `--approve`, sandbox `argus`) | `ok: true`; baseline `target`: 7 gagal, 0 error; baseline `regression`: lulus; patch referensi: `target` dan `regression` lulus, hanya `main.py` dan `models/registry.py` berubah |
| Hash | intake `argus_p2`: commit `cc8a2fda…`, tree `99feeb0c…`, 379 file, snapshot `363964f8…`; sha256 kontrak `295e9514…` (hanya perkiraan sampai approval resmi) |

Belum dilakukan (menunggu review): `--approve`, latihan model palsu, preflight, dan run coder.
