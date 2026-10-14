# Permintaan review: fase 2d (path jail + sandbox Docker)

PR #3, branch `m2-2d` dari `main` `c9a138d`. Rencana: `docs/MILESTONE2_PLAN.md` bagian 3.4 (dengan hardening GPT).
Bukti: `verification/verify-20261014T103740Z-x86_64.log`: 388 lulus, **0 tes sandbox di-skip**, Docker 29.8.2 linux/amd64.

## File utama
- `tools/fs.py`: `PathJail`
- `tools/sandbox.py`: `run_python`, `status`, `tool_version`
- `nodes/llm_worker.py`: tool `RunPython` (hanya bila `sandbox.kind: docker`)
- `graph.py`: gagal saat start bila sandbox diminta tapi tidak bisa dipakai
- `scripts/pin_sandbox_image.sh` (VM), `scripts/build_local_sandbox_image.sh` (tanpa registry), `scripts/verify.sh`
- `tests/test_fs.py` (21), `tests/test_sandbox.py` (15)

## Klaim
1. Path jail menolak `..`, path absolut, NUL, kosong, root itu sendiri, symlink (file atau direktori) yang mengarah keluar, dan file yang ditukar jadi symlink setelah dicek (`O_NOFOLLOW`). Tulis atomik dan aman diulang.
2. Setiap flag sandbox dicek **efeknya dari dalam container nyata**: uid/gid 65534, `CapEff` dan `CapBnd` 0, `NoNewPrivs` 1, hanya `lo`, mount `/` dan `/data` `ro`, `/workspace` dan `/tmp` `rw`, nilai cgroup memori/pids/CPU sesuai config, OOM → exit 137, fork bomb ditolak, timeout membunuh dan menghapus container, output dibatasi.
3. Tidak ada fallback: image tidak pinned, Docker tidak ada, atau daemon mati → `SandboxUnavailable`, kode tidak pernah jalan di host (ada tes dengan file penanda).
4. Langkah `RunPython` yang ter-commit tidak dijalankan ulang saat resume; ganti image = versi tool baru = memo lama tidak dipakai.
5. `verify.sh` → FAIL bila tes sandbox di-skip (didemonstrasikan: 11 di-skip → FAIL), kecuali `ARGUS_SANDBOX_OPTIONAL=1`.

## Temuan selama 2d
- `docker run` tanpa `-i` membuang stdin: container "berhasil" tanpa menjalankan kode. Ada tes yang gagal kalau `-i` hilang (11 tes gagal pada mutasi itu).
- Mutasi menemukan **3 tes yang lulus karena alasan yang salah**: menghapus `--read-only`, `--cap-drop ALL`, atau `:ro` pada `/data` tidak menggagalkan apa pun, karena izin file (nobody) sudah menolak penulisan dan user non-root otomatis punya `CapEff` 0. Tes sekarang memeriksa flag mount dan `CapBnd` langsung; ketiga mutasi tertangkap. Total 13 mutasi, 13 tertangkap.

## Batasan yang disadari
- Bukti di sini memakai image lokal hasil `docker import` dari Python mesin ini (Docker Hub diblokir), di cgroup v1, x86_64. **Belum diuji di VM OCI** (ARM, kemungkinan cgroup v2, image resmi `python:3.13-slim`). Tes cgroup sudah menangani v1 dan v2, tapi syarat GPT tetap: jalankan `verify.sh` di VM.
- Sandbox berbagi kernel dengan host (sifat Docker). Socket Docker tidak boleh diekspos; harness memanggil Docker CLI lokal.
- Workspace per task dibuat `0777` supaya nobody di container bisa menulis; letaknya di dalam folder run.

## Pertanyaan untuk reviewer
- Apakah perlu seccomp profile khusus (sekarang default Docker), atau cukup untuk M2?
- `RunPython` mengembalikan stdout/stderr apa adanya ke model (dipotong 64 KB). Perlu filter tambahan?

## Tanggapan atas audit 2d (GPT, 2026-10-14)

Bukti setelah patch: `verification/verify-20261014T110744Z-x86_64.log`: 402 lulus, **0 tes sandbox di-skip**.

| Temuan | Status |
|---|---|
| P1: `max_output_bytes` hanya membatasi output yang dikembalikan, bukan memori harness | **Terbukti.** Peak RSS proses harness saat kode mencetak 0 / 200 / 400 MB: 12 / 613 / 1213 MB (≈3× ukuran output). **Diperbaiki:** `Popen` + dua thread pembaca yang menguras pipe sampai EOF per 64 KB, menyimpan maks `max_output_bytes` per stream dan membuang sisanya (tidak pernah berhenti membaca, jadi kode tidak macet di pipe penuh). Stdin dikirim dari thread sendiri. Setelah patch: 13 / 13 / 13 MB. Tambahan: lewat `kill_after_output_bytes` (16 MB) container dibunuh lebih awal, tidak menunggu timeout; hasil memuat `stdout_bytes`/`stderr_bytes` (jumlah yang benar-benar dicetak) dan `output_limit_exceeded`. 7 tes baru: 256 MB stdout terkuras habis (exit 0) dengan pertumbuhan RSS < 32 MB, kode tetap jalan setelah 8 MB output (file penanda + stderr), stderr juga dibatasi, output tanpa akhir dibunuh < 10 dtk dan container terhapus, timeout tetap membunuh + menghapus setelah output besar, UTF-8 rusak tidak bikin crash |
| P2: race direktori induk pada path jail | **Terbukti** dengan tes race sungguhan (proses lain menukar `sub/` ↔ symlink keluar): jail lama menulis file temp **di luar root** di 3/3 run. **Diperbaiki** dengan `openat`: root dibuka, setiap komponen direktori dibuka `O_DIRECTORY\|O_NOFOLLOW` relatif ke descriptor induknya (mkdir juga via `dir_fd`), file temp dan `renameat` relatif ke descriptor direktori, lalu fsync direktori. `..` diselesaikan secara leksikal dan tidak boleh naik di atas root. Tes: hook race di 3 titik (sebelum walk → ditolak; setelah walk / sebelum rename → mendarat di direktori yang sudah dibuka, tidak di luar), versi baca, dan race nyata lintas proses (≥3000 tulis, kedua hasil terjadi, nol file di luar; 15/15 run bersih). Threat model ditulis di `tools/fs.py` dan README |

**Perubahan perilaku (lebih ketat):** symlink di dalam root sekarang juga ditolak (sebelumnya diizinkan bila tetap di dalam root), karena target symlink tidak bisa dicek tanpa race. Tes lama diganti `test_symlinks_are_refused_even_when_they_stay_inside_the_root`. Baca juga menolak FIFO/device/direktori (FIFO sebelumnya bisa membuat baca macet).

**Temuan tambahan saat menguji P1:** driver log default Docker (`json-file`) menyalin **seluruh** output container ke disk host (`/var/lib/docker/containers/...`), terlepas dari cara harness membaca pipe. Satu run mutasi (kill dimatikan) meninggalkan container yang terus mencetak dan **menghabiskan disk sandbox Claude** (~30 GB). Diperbaiki dengan `--log-driver none` (output tetap sampai lewat attach) + label `argus.sandbox=1`; tes memeriksa `HostConfig.LogConfig.Type` container yang sedang jalan. Pembersihan setelah kill juga diulang sekali, untuk kasus container baru dibuat setelah percobaan kill pertama.

**Mutasi:** 12 dijalankan, 12 tertangkap. Sandbox: buffer tak terbatas (tersembunyi, field hasil tetap benar → tertangkap tes RSS), berhenti membaca di batas, tanpa kill awal, tanpa kill/hapus saat timeout, decode strict, `--log-driver json-file`. Jail: walk mengikuti symlink, tulis via path string setelah walk (gaya lama), baca via path string, `..` di atas root diabaikan, tanpa cek file reguler, tanpa cek symlink saat replace.

**Seccomp:** mengikuti saran, tidak ada profile custom di M2; README tidak mengklaim isolasi kernel penuh.

**Masih terbuka sebelum 2d dinyatakan selesai:** `verify.sh` di VM OCI ARM dengan image `python:3.13-slim` yang dipin ke digest (butuh Atha).
