# M6 W2a: cek draf deterministik dan persetujuan manusia

Status: **implementasi untuk review.** 2026-10-17. Rencana: `docs/reviews/M6_PLAN.md` W2 dan keputusan desain W2
(dipecah W2a/W2b; repo task terpisah; patch referensi wajib). Tanpa LLM, tanpa run live.

## 1. Alurnya

1. **Draf** (`acceptance/draft.py` `validate_draft`) adalah JSON bertipe:
   - `base`: nama intake;
   - `plan`: file, langkah, risiko;
   - `contract`: hanya `scope`, `validation`, dan opsional `tools` dan `budget_profile`;
   - `new_tests`: path dan isi, minimal satu file baru `test_*.py`;
   - `unverifiable`: catatan untuk reviewer.

   **Draf tidak bisa mengisi** input, issue, cap biaya, atau batas attempt. Draf yang memuat `limits` atau `inputs`
   ditolak.
2. **Kontrak** dibangun harness dari draf ditambah isian manusia: nama task, issue, `max_usd`, `max_iterations`.
3. **Cek statis:**
   - kontrak valid;
   - setiap tes baru adalah file baru (tidak mengganti file intake), masuk scope protected dan tidak writable, dan
     punya minimal satu node wajib sendiri;
   - node wajib tes baru memakai validasi pytest.
4. **Baseline merah** (sandbox, intake ditambah tes baru):
   - setiap node wajib tes baru terkoleksi dan berstatus FAIL karena assertion. ERROR, tidak terkoleksi, atau
     kegagalan koleksi membuat draf ditolak;
   - di validasi itu hanya node baru yang boleh gagal: jumlah failures sama dengan jumlah node baru, errors 0, dan
     output pytest konsisten;
   - node wajib tes lama lulus, dan setiap validasi tanpa tes baru lulus.
5. **Patch referensi hijau:** patch manusia, berupa git diff terhadap baseline, diterapkan ke salinan bersih.
   - Patch hanya boleh mengubah file writable. Tes draf, file protected, dan file di luar writable ditolak, jadi solusi
     tidak bisa memanipulasi tes.
   - Patch kosong atau yang tidak bisa diterapkan ditolak.
   - Setelah patch, semua validasi harus lulus.

   Patch referensi tidak dicoba kalau baseline-nya sudah salah.
6. **Persetujuan** (`scripts/approve_draft.py ... --approve`) hanya dari laporan yang `ok`. Urutan publikasinya:
   1. **record** `fixtures/intake/<task>.json`;
   2. **kontrak** `fixtures/contracts/<task>.json`;
   3. **repo task** `fixtures/repos/<task>`, yaitu snapshot intake ditambah tes yang disetujui. Snapshot intake asli
      tidak pernah diubah.

   Setiap langkah memakai rename atomik dan tidak pernah menimpa. Tes yang berbeda dari yang dicek ditolak.

## 2. Empat invariant dan buktinya

| Invariant | Bagaimana dikunci |
|---|---|
| 1. Persetujuan mengikat sumber kebenaran | Record memuat: dasar intake (commit, tree, snapshot), hash setiap file tambahan, snapshot repo task, bit executable, sha256 kontrak final, sha draf, rencana, dan catatan non-otomatis. Saat setup: (a) snapshot repo task harus persis sama dengan record (cek W4: isi, jumlah file, mode), jadi file tambahan, file hilang, atau file berubah diblok; (b) sha kontrak beku harus sama dengan sha yang disetujui. Kalau tidak: `BLOCKED invalid_contract` sebelum panggilan model. Kalau berhenti di tengah publikasi, yang tersisa record tanpa repo task, dan itu diblok. |
| 2. Baseline merah karena assertion | Langkah 4 di atas. Tes untuk: tes yang hijau di base, gagal import, error fixture, node yang tidak ada, dan kegagalan tambahan. |
| 3. Patch referensi lewat validasi yang sama | Langkah 5: validasi kontrak yang sama, di salinan baseline yang bersih. Tes untuk: patch yang mengubah tes draf, tes lama, file di luar writable, patch kosong, patch yang tidak memperbaiki, dan patch yang tidak bisa diterapkan. |
| 4. Kriteria non-otomatis bukan kelulusan | `unverifiable` hanya disimpan di laporan dan record sebagai catatan reviewer. Field itu tidak pernah menjadi kriteria kontrak dan tidak dibaca acceptance. |

**Tes tambahan hanya lewat jalur persetujuan:** tes baru wajib protected dan tidak writable, jadi agen tidak bisa
menulisnya selama task (scope acceptance yang sudah ada). Setelah disetujui, tes itu bagian dari snapshot terkunci
repo task, jadi perubahan sebelum run diblok di setup.

## 3. Bukti

- **Tes sandbox asli** (environment `argus`, `tests/test_draft.py`, 36 tes): repo kecil yang di-intake dari git, satu
  bug, satu tes lama, satu tes baru. Kasus bahagia sampai persetujuan, semua kasus penolakan di atas, persetujuan dari
  laporan gagal, persetujuan ulang, tes yang berubah antara cek dan persetujuan, berhenti sebelum repo task, dan repo
  task yang diubah setelah persetujuan.
- **Code task** (`tests/test_codetask.py`): task dengan kontrak selain yang disetujui diblok tanpa panggilan model.
  Dengan kontrak yang disetujui, task berjalan dan `result.json` mencatat `kind: task`, file tambahan, dan sha kontrak.
- **Mutan** (`verification/mutants-w2a-20261020-744c8b8.log`): 20 dari 21 tertangkap. Yang 21 itu 16 asli
  ditambah 5 untuk perbaikan review #79: approval tidak membandingkan sha draf, tidak membandingkan sha kontrak, tidak
  membangun ulang kontrak dari draf, tidak mengecek ulang intake, dan kontrak berbagi `scope` dengan draf. **Satu yang lolos**, "tes yang berubah setelah cek bisa disetujui", **tidak ekuivalen secara perilaku**. Itu
  ekuivalen hanya terhadap apa yang diterbitkan. `added` dihitung `materialize()` dari `draft["new_tests"]`, dan sha
  draf dicek lebih dulu, jadi `added` hasil hitung ulang selalu sama dengan saat `check()`. Bedanya hanya kalau
  pemanggil mengubah `report["added"]` saja: kode asli menolak, sedangkan mutan tetap menerbitkan isi yang benar,
  karena record memakai `added` hasil hitung ulang, bukan dari laporan. Cek itu dipertahankan sebagai lapis kedua.

## 3a. Perbaikan setelah review #79

`approve()` menerbitkan persis yang diperiksa `check()`, siapa pun pemanggilnya. Semua dicek sebelum ada yang ditulis:
- `check()` menyimpan `contract_sha256`;
- `approve()` membandingkan sha draf dan sha kontrak;
- kontrak di laporan harus sama persis dengan draf yang dibangun ulang ditambah isian manusia, jadi scope atau validasi
  tidak bisa diganti walaupun hash-nya ikut dipalsukan;
- intake dicek ulang.

Temuan tambahan saat itu: `build_contract` memakai objek `scope` dan `validation` yang sama dengan draf, sehingga
mengubah kontrak di laporan ikut mengubah draf. Kini dipakai salinan, dan ada tes yang mengunci itu.

## 4. Batas

- Node wajib tes baru harus pytest. Tes baru berbasis unittest belum didukung.
- `unverifiable` tidak diperiksa isinya. Tugasnya hanya memastikan catatan itu sampai ke reviewer (W3 `PR.md`).
- Draf belum dibuat model. Itu W2b, yang menghasilkan file draf yang sama dan tetap harus lewat W2a.
