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
