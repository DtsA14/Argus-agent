# Pilot W2b-2, drafter run `w2b2d1` dan approval `pr_title`: hasil

2026-10-23. Drafter pada intake `argus_p7`, issue `w2b2/issue.txt` (judul `PR.md`), config `w2b2/config_w2b2_draft.yaml`,
Argus `d73e675`. Kriteria: `w2b2/PREFLIGHT.md` bagian 5.

## Drafter: berhasil (kriteria 1)

| | |
|---|---|
| Status | **`DRAFTED`** dalam 2 submit (SubmitDraft ditolak, ReviseDraft `validation` diterima) |
| Panggilan model | 4; langkah 3 dari 16 |
| Biaya | **$0,0933** (`usd_complete` true); cache read 23.661, write 20.040 |
| Salinan intake | tidak berubah |
| Waktu terminal | gerbang lolos 17:39:21Z, kunci 17:39:26Z, selesai 17:40:16Z (**55 detik**) |

Jalur: SearchFiles `def render_pr`, SearchFiles `tests`, baca `codetask/review.py`, SubmitDraft, lalu ReviseDraft.

Submit 1 ditolak karena (a) tiga tes yang memang lulus di kode sekarang (judul pendek, tepat 80 karakter, heading 120)
dimasukkan ke `must_pass`, dan (b) validasi regresi `tests/test_review.py` gagal di sandbox karena butuh `git`, yang
tidak ada di sandbox. Revisi mengeluarkan ketiga tes dari `must_pass` (tetap ada di berkas dan tetap harus lulus,
karena validasi `target` menjalankan seluruh berkas) dan membuang validasi regresi.

Draf: writable `codetask/review.py`; protected `tests/**`, `acceptance/**`, `harness/**`, `scripts/**`; tes baru
`tests/test_pr_title.py` (8 tes, 5 wajib); profil **`default`**; **tanpa `tools`**; `unverifiable` kosong. Claude
memeriksa nilai harapan kedelapan tes terhadap aturan di issue: semuanya cocok.

## Approval: dilakukan, lalu ditemukan tidak bisa dikerjakan

Atha menyetujui ("approve"): `approve_draft.py ... --task pr_title --max-usd 0.5 --max-iterations 3 --no-reference
--approve` (`approve_output.txt`): record `kind: task`, `feasibility: unproven`, sha kontrak **`c9535a0c7b3e`**.

Saat menyiapkan gerbang agen, Claude menemukan bahwa **kontrak ini praktis tidak bisa dipenuhi**:
- tanpa `tools`, agen hanya punya `WriteFile`, yang menulis ulang berkas utuh;
- `codetask/review.py` berukuran 30.413 byte (±7.600 token);
- profil `default` membatasi output 4.096 token per panggilan.

Setiap attempt agen akan terpotong sebelum berkasnya tertulis. Drafter tidak mungkin tahu ini: argumen `SubmitDraft`
tidak punya `tools`, dan prompt-nya tidak menjelaskan bahwa WriteFile menulis berkas utuh.

**Keputusan:** agen **tidak dijalankan** pada `pr_title`. Task itu tetap tercatat (record, kontrak, laporan) sebagai
temuan.

## Perbaikan (PR berikutnya)

- `SubmitDraft`/`ReviseDraft` mendapat `tools` (hanya `edit_file` dan `search_files`, yang diizinkan untuk kontrak mana
  pun). Prompt menyebut tool agen dan bahwa `WriteFile` menulis berkas utuh.
- **Cek kelayakan deterministik sebelum sandbox:** berkas writable yang terlalu besar untuk ditulis ulang dalam satu
  output (perkiraan byte/4 > `max_output_tokens` profil), sementara `edit_file` tidak diberikan, membuat draf **ditolak**
  dengan alasan dan saran (tambah `edit_file` atau profil lebih besar). Kontrak seperti `pr_title` tidak bisa lolos lagi.
- `DRAFT_REVIEW.md` menampilkan tool tambahan.

Langkah berikutnya W2b-2: drafter dijalankan ulang (`w2b2d2`, issue dan config sama), approve dengan nama `pr_title2`,
lalu agen.
