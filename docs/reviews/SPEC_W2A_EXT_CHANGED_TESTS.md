# Spec W2a-ext: `changed_tests`, draf yang boleh mengubah tes lama

Status: **spec, belum dikoding.** 2026-10-23. Ditulis Claude untuk review Atha/GPT. **Keputusan yang diminta: bagian 9.**
Dasar: `acceptance/draft.py` (W2a), `codetask/drafter.py` (W2b), `codetask/review.py` (W3), `router/job.py`.

## 0. Masalah

Draf W2a hanya boleh **menambah** file tes (`new_tests`). Tes yang sudah ada tidak boleh diubah, baik oleh draf maupun
agen, dan itu disengaja: tes lama adalah pagar.

Akibatnya, task yang **mengubah perilaku yang sudah dites** tidak bisa diselesaikan dengan jujur. Contoh nyata:
`success_rate` di `scripts/pilot_report.py`. `tests/test_pilot_report.py` membandingkan seluruh output JSON secara
persis, jadi menambah satu field pasti membuat tes itu gagal. Agen tidak boleh mengubahnya, dan draf juga tidak.
Sebagian besar task nyata berbentuk seperti ini.

**Tujuannya:** draf boleh menyertakan **isi baru untuk file tes yang sudah ada**. Manusia menyetujuinya dengan melihat
diff-nya, dan harness menjaga hal-hal yang bisa dijaga secara deterministik.

**Yang tidak berubah:**
- agen tetap tidak bisa menyentuh tes (file yang diubah tetap protected);
- acceptance tetap sama;
- baseline merah tetap wajib;
- persetujuan tetap terikat ke sha draf dan sha kontrak.

## 1. Bentuk draf

Field baru `changed_tests`, opsional, dengan bawaan kosong:

```json
"changed_tests": [
  {"path": "tests/test_pilot_report.py",
   "content": "<isi file yang baru>",
   "removed": [{"node": "test_old_shape", "reason": "the report has one more key; replaced by test_new_shape"}]}
]
```

**Cek statis (tanpa sandbox):**
- `path` adalah file `test_*.py` yang **sudah ada** di intake, berbentuk path yang plain, tidak sama dengan path tes baru,
  dan tidak duplikat;
- `content` berbeda dari isi lama dan ukurannya ≤ 50 KB (batas yang sama dengan `new_tests`);
- file itu **protected dan tidak writable** di scope kontrak;
- maksimal 5 file per draf (K5);
- `removed` berisi nama node tanpa `::` dan alasan yang tidak kosong.

## 2. Cek di sandbox

Semua cek berjalan pada **task baseline**, yaitu intake ditambah `new_tests` ditambah `changed_tests`.

1. **Tidak ada tes yang hilang diam-diam (K1).** `pytest --collect-only -q` dijalankan di sandbox untuk setiap file yang
   diubah, sekali pada isi lama (intake) dan sekali pada isi baru. Setiap node id lama, termasuk varian parametrize, harus
   tetap ada di isi baru, kecuali tercantum di `removed`. Node lama yang hilang tanpa alasan membuat draf ditolak, dan
   namanya disebut di pesan penolakan.
2. **Baseline merah, diperluas (K4).** Node wajib dari file tes baru **dan** node wajib dari file yang diubah, yaitu yang
   menurut draf ekspektasinya berubah, harus **gagal karena assertion** di kode sekarang. Semua node lain di validasi itu
   lulus, tidak ada yang error, dan jumlah failures sama persis dengan jumlah node wajib tadi. Aturannya sama seperti tes
   baru, hanya cakupannya bertambah.
3. **Patch referensi (bila ada):** diterapkan ke task baseline, lalu semua validasi harus lulus. Ini tidak berubah.

## 3. Tes yang melemah: tidak bisa dicek otomatis, jadi diperlihatkan

Harness tidak bisa memastikan isi baru **tidak lebih longgar** dari yang lama, misalnya assertion yang dihapus atau
diganti `assert True`. Pertahanannya ada di mata manusia, dibantu dua hal:
- **`DRAFT_REVIEW.md`** menampilkan **diff unified** lama→baru untuk setiap file yang diubah, daftar `removed` beserta
  alasannya, dan **peringatan otomatis (K3)**: fungsi tes yang jumlah `assert`-nya turun, tes yang dihapus, serta
  `pytest.skip`, `xfail`, atau `assert True` yang baru muncul. Peringatan ini tidak menolak draf, karena perubahan seperti
  itu bisa saja sah, tapi ia menunjuk tempat yang harus dibaca.
- **Layar `argus approve`** menulis: "mengubah N file tes lama (baca diff di `DRAFT_REVIEW.md`)", beserta jumlah
  peringatan.

## 4. Persetujuan dan record

- Record task memuat `changed: {path: {"before": sha_lama, "after": sha_baru}}` di samping `added`, plus `removed`.
  Snapshot task sudah mencakup isi baru, jadi cek setup tetap utuh (file yang berbeda dari record membuat run diblok).
- `approve()` memastikan isi file lama di intake masih sama dengan `before` saat approve. Kalau intake berubah di
  antara cek dan approve, approve ditolak, sama seperti cek intake yang sudah ada.

## 5. Paket review dan PR

- `codetask/review.py`: basis yang dibangun ulang adalah commit dasar ditambah tes baru **ditambah isi baru tes yang
  diubah**, dan input harus sama persis dengan itu. Di `changes.patch`, file yang diubah muncul sebagai `M` dengan tanda
  "**changed test, approved with the task**". Agen tetap tidak bisa mengubahnya, karena protected dan karena dicek di
  `changes_match_verdict`.
- `PR.md` mendapat bagian "**Existing tests changed by the task**": daftar file, node yang dihapus beserta alasannya, dan
  ringkasan diff. Reviewer PR wajib membacanya.

## 6. Drafter (W2b)

- `SubmitDraft` dan `ReviseDraft` mendapat `changed_tests` dengan bentuk yang sama.
- Prompt menjelaskan bahwa kalau issue mengubah perilaku yang sudah dikunci tes lama, tes lama itu diubah lewat
  `changed_tests`, **bukan** dibuang dari validasi. Node yang ekspektasinya berubah diwajibkan dan harus gagal sekarang,
  sedangkan node lain tetap ada dan tetap lulus.
- Penolakan yang menyebut node lama hilang memberi petunjuk: kembalikan node itu, atau cantumkan di `removed` beserta
  alasannya.

## 7. Tes (setiap tes harus gagal di kode lama; mutan)

**W2a (`tests/test_draft.py`, sandbox):**
1. Draf yang mengubah `test_old.py` dengan ekspektasi baru: node yang berubah merah karena assertion, node lain hijau,
   lalu `ok`. Approve mencatat `changed` dengan before/after, dan snapshot task memuat isi baru.
2. Node lama hilang tanpa `removed`: ditolak, dan namanya disebut. Dengan `removed` dan alasan: diterima.
3. Varian parametrize yang hilang tertangkap (karena pengumpulan node lewat sandbox).
4. File yang belum ada di intake, path yang writable, isi yang sama, atau lebih dari 5 file: ditolak (cek statis).
5. Node di file yang diubah gagal tanpa diwajibkan: ditolak, dan namanya disebut.
6. Intake berubah antara cek dan approve: ditolak.

**Paket review (`tests/test_review.py`):**
7. File yang diubah ditandai di `changes.patch` dan `PR.md`.
8. Agen yang mencoba mengubah tes yang diubah: ditolak, dan tidak ada paket.

**Drafter (`tests/test_drafter.py`, fake):**
9. `changed_tests` lewat `SubmitDraft` dan `ReviseDraft`.
10. Peringatan K3 muncul di `DRAFT_REVIEW.md` (jumlah assert turun, `skip` baru), dan diff ikut tampil.

**Router (`tests/test_router.py`):**
11. Layar approve menyebut jumlah file tes yang diubah dan jumlah peringatan.

## 8. Pilot W2b-3

Task `success_rate` di `scripts/pilot_report.py`: laporkan juga rate atas semua run (`done / runs_total`). Butir ini
sudah ada di PENDING sejak review 3b. Jalankan lewat router dengan drafter thinking dan approve `--no-reference`. Kriteria
ditulis sebelum run. Yang diukur:
- apakah drafter memakai `changed_tests` dengan benar, yaitu tes lama diperbarui tanpa tes yang hilang;
- apakah peringatan K3 membantu atau malah mengganggu;
- jumlah keputusanmu dan biaya job.

## 9. Keputusan yang diminta

| | Pertanyaan | Usul |
|---|---|---|
| K1 | Cara memastikan tidak ada tes yang hilang | **`pytest --collect-only` di sandbox**, lama dibanding baru (tepat, termasuk parametrize). Alternatif: nama fungsi lewat AST (tanpa sandbox, tapi parametrize tidak terlihat) |
| K2 | Boleh menghapus tes lama? | **Boleh, dengan alasan** di `removed`, dan ditampilkan ke manusia di `DRAFT_REVIEW.md` dan `PR.md` |
| K3 | Heuristik tes yang melemah | **Peringatan saja**, tidak menolak: jumlah assert turun, tes dihapus, `skip`/`xfail`/`assert True` baru |
| K4 | Node mana di file yang diubah boleh gagal di baseline | **Hanya node wajib**, aturan yang sama dengan tes baru |
| K5 | Batas | Hanya file `test_*.py` yang sudah ada di intake, maksimal 5 file per draf, masing-masing ≤ 50 KB |
| K6 | Router | Layar approve menyebut jumlah file tes yang diubah dan jumlah peringatan |
| K7 | Pilot pertama | **W2b-3 `success_rate`** dengan drafter thinking |

Perkiraan: satu PR kode untuk W2a, drafter, review, router, tes, dan mutan, lalu preflight W2b-3.
