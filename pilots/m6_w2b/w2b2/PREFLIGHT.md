# Pilot W2b-2: preflight (ditulis sebelum run)

Status 2026-10-23: **persiapan; belum ada run.** Spec: `docs/reviews/SPEC_W2B_DRAFTER.md` bagian 7. W2b-1 selesai
(`w2b1/live/w2b1d3/RESULT.md`). Keputusan Atha (2026-10-23): task "judul `PR.md` dipotong di batas kata", issue ditulis
Claude ("lu yang tulis"), dan **tanpa patch referensi**.

## 1. Tujuan

Alur **end-to-end** yang belum pernah jalan utuh: issue, drafter, approve (`--no-reference`), agen, paket review, lalu
patch diterapkan ke `main`. Yang diukur: apakah hasilnya `agent-completed` tanpa patch referensi manusia, berapa
total biayanya, dan berapa titik keputusan dan menit Atha.

Catatan pemilihan task: kandidat pertama (`success_rate` di `pilot_report.py`) **tidak bisa** diselesaikan dengan
jujur di bawah W2a. Tes lama membandingkan output JSON persis, sedangkan draf hanya boleh menambah tes, tidak mengubah
tes lama. Itu ditunda ke "W2a-ext: changed_tests" (W2b-3).

## 2. Artefak dan cek (tanpa biaya)

| | |
|---|---|
| Basis | intake **`argus_p7`** = `main` `3b5d26e` (436 berkas, snapshot `3fe0c22f85b0…`; exclude `verification`, `pilots`), `fixtures/intake/argus_p7.json` |
| Issue | `w2b2/issue.txt`, ditulis Claude, 1.121 karakter (batas 2.000). Definisi pemotongan dibuat persis supaya bisa dites: ≤ 80 karakter apa adanya; selain itu 81 karakter pertama dipotong sebelum spasi terakhir, lalu `...`; tanpa spasi (atau hasil kosong), 80 karakter lalu `...` |
| Kesesuaian dengan W2a | tidak ada tes lama yang mengunci judul `PR.md` (dicek: `tests/test_review.py` hanya memeriksa isi lain), jadi tes baru saja cukup |
| Config drafter | `w2b2/config_w2b2_draft.yaml`: isi sama dengan config terakhir W2b-1 (`w2b1d3`), empat selisih dari `config.yaml`; attempt $0,70, cap $0,75, input 64.000, output 16.384, 3 submit, caching menyala; **drafter wajib memilih profil** (PR #155) |
| Gerbang drafter | `w2b2/go_live_draft.sh`: sama dengan W2b-1, dengan intake `argus_p7`, issue dan config baru, run id `w2b2d[1-9]`; cek bocoran diganti cek bahwa `pilots/` dan `verification/` tidak ada di intake (tidak ada jawaban yang bisa bocor) |
| Tes gerbang | `w2b2/gl_test_draft_output.txt` |

## 3. Langkah dan persetujuan

| # | Langkah | Persetujuan |
|---|---|---|
| 1 | Merge PR ini; checkout live ke `main`; salin `fixtures/repos/argus_p7` ke checkout live; `go_live_draft.sh --check-only` | Atha ("merge") |
| 2 | **Drafter** satu kali: `go_live_draft.sh w2b2d1` | **Atha, "go live"** |
| 3 | Claude melaporkan draf. Atha membaca `DRAFT_REVIEW.md` (ringkasan dari Claude), lalu memutuskan approve atau tidak. Bila approve: `approve_draft.py --draft runs/w2b2d1/draft.json --task pr_title --issue-file runs/w2b2d1/issue.txt --max-usd <cap> --max-iterations 3 --no-reference --approve`. Cap mengikuti profil pilihan drafter (`large_usd` → $0,75 seperti 3b; `default` atau `large` → $0,50) | **Atha, "approve"** |
| 4 | PR berisi record dan kontrak task, gerbang agen (sha kontrak, config agen) dan tesnya, plus preflight agen (kriteria sebelum run) | Atha ("merge") |
| 5 | **Agen** satu kali: `go_live_agent.sh w2b2a1` | **Atha, "go live"** |
| 6 | `build_review.py`; bila `DONE` dan paket valid, patch diterapkan ke `main` tanpa perubahan, lalu `verify.sh` | Atha ("merge") |

## 4. Ekspektasi (sebelum run)

- **Drafter:** task kecil (satu fungsi di `codetask/review.py`). Yang perlu dibaca: `codetask/review.py` (±540 baris)
  dan cara tes lama membangun paket review (`tests/test_review.py`, besar). Ada risiko konteks besar bila drafter
  membaca `tests/test_review.py` seluruhnya. Perkiraan **$0,15–0,35**, 1–2 submit. Tes yang paling mungkin: memanggil
  `render_pr` atau `build` dengan kontrak berissue panjang dan memeriksa baris pertama `PR.md`.
- **Agen:** satu perubahan kecil di `render_pr`. Perkiraan **$0,05–0,20**, satu attempt.
- **Total W2b-2:** ±$0,20–0,55.

## 5. Kriteria (ditetapkan sebelum run, tidak diubah sesudahnya)

1. **Drafter berhasil:** `DRAFTED` dalam ≤ 3 submit, `source_unchanged` true, biaya ≤ $0,70 dengan `usd_complete` true.
   Selain itu: dicatat, berhenti, tidak ada run ulang tanpa persetujuan baru.
2. **Approve** adalah keputusan Atha. Bila Atha menolak draf, W2b-2 berakhir di situ dan alasannya dicatat (hasil yang
   sah, bukan kegagalan harness).
3. **W2b-2 berhasil** bila: agen `DONE`, paket review valid, patch agen diterapkan ke `main` **tanpa perubahan**, dan
   `verify.sh` lulus, sehingga task `agent-completed` **tanpa patch referensi manusia**. Selain itu: gagal, dicatat, berhenti.
4. **Dicatat:** biaya drafter dan agen; submit dan alasan penolakan; profil pilihan drafter dan apakah cukup bagi agen;
   cakupan dan bobot tes drafter (dinilai Claude dari isinya); titik keputusan Atha, waktu terminal kedua run
   (`~/argus-supervision.log`), dan menit Atha (satu angka, opsional).
