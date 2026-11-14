# Spec SANDBOX-SPLIT: grup sandbox serial dipecah jadi dua grup serial

Status: **draf spec untuk dibaca Atha; belum ada kode.** Strict lane. Ditulis Claude, 2026-11-14.
Dasar: laporan Fable (item 5), review desain Opus (2026-11-13), dan pengukuran dasar `verification/verify-20261113T201900Z-aarch64.log` (commit 7175b91) dengan pencatat `docker events` dan tekanan CPU/memori.

## 0. Masalah (terukur)

Waktu dinding satu `verify_at` (sekitar 19 menit pytest) sama dengan waktu grup sandbox serial: **1.146,8 detik (744 tes)** lawan non-sandbox **1.045,2 detik (3.396 tes)** yang jalan paralel di tiga worker lain. Menambah worker tidak menolong selama grup itu serial.
Per modul (log #508, tes >= 1 detik): `test_draft` 538 detik, `test_eval_sandbox` 131, `test_codetask_crash` 76, `test_stage` 55, `test_env_node` 44, sisanya masing-masing < 33.

## 1. Usulan

Dua grup serial `sandbox_a` dan `sandbox_b` (bukan lebih dari dua), masing-masing serial di dalamnya, saling paralel. Pembagian: **`test_draft.py` sendirian (sekitar 545 detik) lawan semua modul sandbox lain (sekitar 580 detik)**. Perkiraan waktu dinding sekitar 10 sampai 11 menit, sebelum biaya rebutan sumber daya. Pembagian "draft + eval lawan sisanya" tidak dipakai: 670 lawan 450 detik, tidak seimbang.

Aturan yang menjaga keselamatan (dikunci tes di `tests/test_xdist_groups.py`):
1. Tiap modul sandbox ada di tepat satu grup, utuh (modul tidak dipecah).
2. Pasangan ini selalu satu grup, karena berbagi keadaan global yang ditemukan Opus:
   - `test_codetask_crash.py` dan `test_auto_validation.py` (run id `rc`, `sb.remove_labeled({"argus.run": "rc"})` memeriksa seluruh mesin dengan `count == 1`);
   - `test_stage.py` dan `test_stage_viewer.py` (awalan dan label tetap);
   - `test_env_node.py` dan `test_env_from_base.py` (cache `~/.cache/argus-npm` dan `argus-pip`, `docker rmi` pada image yang dibangunnya).
3. Tes dengan batas waktu ketat (`test_sandbox`: `elapsed < 9`/`< 10`; `test_acceptance_sandbox`: `timeout_s: 3`; `test_stage`: `wait_s` 0,2 dan 0,5) tinggal di grup yang lebih ringan, dan margin waktunya dicatat.
4. Sakelar mundur `VERIFY_SANDBOX_GROUPS=1` (bawaan: 2 setelah spec ini lolos) mengembalikan satu grup; nilainya dicetak di log. Aturan rollback tertulis: satu kegagalan karena batas waktu atau exit 137 yang tak terjelaskan setelah merge berarti kembali ke 1.
5. Batas kontainer tidak diubah (1 CPU, 512 MB, `XDIST_WORKERS=4`), tidak ada plugin rerun.

Aturan tertulis "tes sandbox tidak jalan bersamaan" di `conftest.py`, `docs/Reconciliation.md` dan `PENDING.md` diganti: tes sandbox tidak jalan bersamaan **dalam satu grup**, dan dua grup tidak berbagi keadaan global (butir 2).

## 2. Apa yang dikoreksi dari catatan lama

`docs/Reconciliation.md` menulis "CPU berebut membuat exit 137". Penyebab itu **tidak pernah dibuktikan** (tidak ada bukti tersimpan). Pengukuran dasar menunjukkan 137 juga muncul di run hijau: 28 kematian berstatus 137 dan satu event `oom` (sekitar 20:36 UTC), yang sebagian pasti disengaja (`tests/test_sandbox.py:148` menegakkan `exit_code == 137` dan `killed` untuk batas memori; tes batas waktu juga membunuh kontainer). Maka kriteria "nol exit 137" tidak dipakai.

## 3. Bukti yang diminta sebelum merge

Urutan, murah dulu:
1. **Audit statis** (hanya membaca) atas semua modul sandbox untuk nama tetap, run id, `docker` global, cache bersama, port, dan penulisan `.sandbox_image*`. `test_stage_viewer.py` dan `test_env_from_base.py` belum diperiksa sama sekali; hasilnya dicatat di spec ini.
2. **Pemetaan 137 dan `oom` ke tes pemiliknya** pada run dasar: tiap kematian 137 harus dikaitkan ke tes yang sengaja menciptakannya (hitungan per image dibandingkan dengan dasar). Yang tak terkait ke tes mana pun menghentikan pekerjaan.
3. **Pengukuran waktu dinding per grup** (mulai paling awal sampai berhenti paling akhir dari laporan tes) ditambahkan ke ringkasan `conftest.py`.
4. **Tiga `verify_at` penuh berturut-turut, semuanya bersih**, tanpa job live dan tanpa `verify_at` kedua di mesin, dengan pencatat `docker events` dan tekanan CPU/memori. Syarat: semuanya `RESULT: PASS` dengan 0 tes sandbox dilewati; tidak ada event `oom` di luar yang berasal dari tes batas memori; hitungan 137 per image tidak melebihi dasar; tes berbatas waktu ketat memakai kurang dari separuh batasnya; satu kontainer terlama kurang dari separuh `timeout_s`. **Satu kegagalan menghentikan, bukan diulang sampai hijau.**
5. Mutan: pasangan yang berpisah grup harus membuat tes pengunci gagal (tiga pasangan, satu mutan masing-masing), modul tak dikenal harus gagal, dan sakelar `VERIFY_SANDBOX_GROUPS=1` harus mengembalikan satu grup.

### 3.1 Hasil audit statis sejauh ini (2026-11-14, grep, bukan pembacaan penuh)

- `test_stage_viewer.py`: docker sungguhan hanya di bagian "the real build in pwa_node22" (baris 856 dan seterusnya, lewat `approve_draft.sandbox_cfg`); sisanya memakai `Staging(run=...)` palsu atau `monkeypatch` pada `subprocess.run`. Tidak ada nama kontainer, port, atau cache tetap yang terlihat oleh grep. **Belum ditelusuri**: apakah bagian docker itu memakai `PREFIX`/`LABEL` milik `test_stage.py`.
- `test_env_from_base.py`: kebanyakan memakai `docker` palsu di `tmp_path`; baris 170 dan 194 sampai 200 memakai `sb.status` dan `sb.run_command` sungguhan atas image yang dibangun ke direktori sementara. Tidak ada `docker rmi` di berkas ini (yang ada di `test_env_node.py:226`). **Belum ditelusuri**: apakah build-nya memakai `~/.cache/argus-pip`.
- Keduanya tetap dipasangkan menurut aturan butir 2 sampai penelusuran itu selesai.

## 4. Sengaja tidak dikerjakan

- Memecah satu modul lintas grup, lebih dari dua grup, menambah worker, melonggarkan batas atau timeout.
- #7 (mengurangi run kontainer di `test_draft.py`): hematnya kecil (sekitar 1 menit CPU) dan menyentuh tes jaminan. Dikerjakan hanya kalau setelah ini `test_draft` ternyata grup terpanjang, dengan mutan per jaminan, dalam PR terpisah.
- Menjadikan `precheck.sh` bukti. Catatan: pra-cek yang memilih `test_draft.py` memakan 8 menit 51 detik, bukan 40 detik.

## 5. Batas yang diketahui

Penyebab exit 137 lama belum diketahui. Perilaku dua grup di bawah beban tidak diketahui sebelum langkah 4. Waktu dinding sebenarnya bisa kurang dari 10 menit bila sumber daya berebut.
