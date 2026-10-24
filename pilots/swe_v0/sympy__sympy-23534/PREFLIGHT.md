# Pilot SWE v0: `sympy__sympy-23534` (preflight, ditulis sebelum run)

Status 2026-10-24: **persiapan; belum ada run.** Spek: `docs/reviews/SPEC_SWE_PILOT.md` (#192, kode #193). Penilai:
`scripts/swe_grade.py` dengan perbaikan dari review #193 (hasil yang tidak sah ditolak, `FAIL_TO_PASS` kosong ditolak,
hanya fungsi tes di tingkat modul). Perbaikan itu harus masuk `main` **sebelum grading**; run boleh lebih dulu.

## 1. Tujuan dan batas klaim

Pilot pertama di repositori selain Argus dengan target sukses dari luar. Klaim yang boleh ditulis dari hasilnya:
- "**harness Argus menyelesaikan task SWE-bench dari ujung ke ujung**", **bukan** "model X memperbaiki bug yang belum
  pernah ia lihat". Instance ini publik (SWE-bench Verified, issue sympy Mei 2022, patchnya di GitHub), jadi
  kemungkinan besar ada di data latih DeepSeek (kontaminasi);
- "**penilaian ala SWE-bench, Python 3.12**". Environment resmi sympy 1.11 memakai Python 3.9, dan penilainya milik
  Argus, bukan harness resmi. Tidak dibandingkan dengan angka leaderboard.

Yang diukur: apakah alur Argus berjalan di repo asing (intake 1.968 berkas, environment `sympy`, drafter, approve,
agen, paket review), apakah tes drafter menangkap perilaku yang sama dengan tes resmi, biaya, dan keputusan Atha.

## 2. Task

- **Issue:** `issue.txt` = `problem_statement` instance **apa adanya** (sha256 sama dengan dataset). Isinya:
  `symbols(('q:2', 'u:2'), cls=Function)` menghasilkan `Symbol`, bukan `UndefinedFunction`, bila ada lapisan kurung
  ekstra.
- **Repo:** clone `~/swe/sympy` (`https://github.com/sympy/sympy.git`) di `base_commit`
  `832c24fec1046eaa544a4cab4c69e3af3e651759`. Clone ini punya history lengkap, termasuk commit perbaikan. Intake hanya
  mengambil tree `base_commit` tanpa `.git` (dites di #193), jadi tidak ada yang bisa membaca commit sesudahnya.
- **Tes resmi** (`test_patch`, `FAIL_TO_PASS` = `test_symbols`, `PASS_TO_PASS` = 11 tes `sympy/core/tests/test_symbol.py`)
  ada di `~/swe/inst/`, di luar repo, job root, dan path jail tool. Drafter dan agen tidak melihatnya; penilai
  menerapkannya **sesudah** paket review jadi.
- **Kelayakan** (fase 2, tanpa biaya): di sandbox `sympy`, `base_commit` + `test_patch` → `test_symbols` FAIL karena
  AssertionError; + patch resmi → 13/13. Penilai di data asli: patch resmi `resolved: true`, patch kosong `false`.

## 3. Cara jalan (sesi Claude di VM; Atha hanya menulis "go live" / "y" per perintah)

Image `sympy` dari `scripts/build_env_sandbox_image.sh sympy ~/swe/venv-sympy` (`mpmath==1.3.0`, `pytest==9.1.1`, rootfs
`5b2123cd…`). Id image-nya dipin di `job.json` saat `code`; selama job, image tidak dibangun ulang. Checkout live
`~/pilot3a_live` di `main` yang sudah berisi preflight ini (issue dibaca dari sana). DeepSeek thinking (bawaan), cap job $1,00, cap drafter $0,75.

```bash
cd ~/pilot3a_live && git pull -q --ff-only
~/Argus-agent/.venv-verify/bin/python scripts/argus.py code --repo ~/swe/sympy \
    --commit 832c24fec1046eaa544a4cab4c69e3af3e651759 --issue-file pilots/swe_v0/sympy__sympy-23534/issue.txt \
    --environment sympy --key-file ~/.config/argus/deepseek_key --yes
```

Lalu ringkasan draf dari Claude (baris "Why they fail now" dikutip apa adanya), `approve` setelah "y", dan `retry`
bila perlu setelah "y". Sesudah `REVIEW_READY`, dan setelah perbaikan penilai ada di `main`:

```bash
~/Argus-agent/.venv-verify/bin/python ~/Argus-agent/scripts/swe_grade.py --instance ~/swe/inst/sympy__sympy-23534 \
    --repo ~/swe/sympy --review <dir paket review> --sha <sha256 yang dicetak status> --environment sympy \
    --out ~/Argus-agent/pilots/swe_v0/sympy__sympy-23534/grade.json
```

Selama tahap berjalan, `verify.sh` tidak dijalankan (venv yang sama).

## 4. Ekspektasi (sebelum run)

- **Drafter:** ±$0,02–0,20, 1–4 submit. Repo jauh lebih besar dari Argus, jadi ia mungkin membaca lebih banyak. Yang
  diharapkan: writable `sympy/core/symbol.py`, tes baru (mis. `sympy/core/tests/test_symbols_cls.py`) yang merah karena
  assertion (`type(q[0])` bukan `UndefinedFunction`).
- **Agen:** satu baris (`cls=cls` diteruskan pada panggilan rekursif `symbols`). ±$0,01–0,10, 1 attempt.
- **Job:** ±$0,05–0,30 dari cap $1,00.

## 5. Kriteria (ditetapkan sebelum run, tidak diubah sesudahnya)

1. **Drafter:** `DRAFTED` dalam ≤ 5 submit, validasi di environment `sympy`, minimal satu node wajib merah karena
   assertion pada perilaku dari issue, dan writable tidak lebih luas dari `sympy/core/**`. Draf yang lolos dengan cara
   lain (mis. writable `sympy/**` atau tes yang tidak menyentuh `cls=`) tidak di-approve.
2. **Approve** adalah keputusan Atha setelah membaca ringkasan (boleh menolak; itu hasil yang sah).
3. **Berhasil** bila: agen `DONE`, paket review valid, dan **`swe_grade.py` memberi `resolved: true`** (`FAIL_TO_PASS`
   1/1, `PASS_TO_PASS` 11/11) untuk patch dengan sha yang dicetak `status`, dengan biaya job ≤ $1,00. `DONE` dari Argus
   saja **tidak** cukup. Penilai yang menolak (hasil tidak sah) bukan "gagal", tetapi "belum dinilai": diperbaiki lalu
   dinilai ulang. Selain itu: gagal, dicatat, berhenti.
4. **Dicatat:** apakah tes drafter hijau di atas patch resmi (info dari penilai), biaya dan waktu per tahap, submit dan
   penolakannya, isi `job.json` (keputusan, id image), apakah patch agen sama dengan patch resmi, menit Atha (opsional),
   dan kalimat klaim dari bagian 1.
5. **Tidak diterapkan ke sympy.** Patch tidak di-push ke mana pun; ini latihan.
