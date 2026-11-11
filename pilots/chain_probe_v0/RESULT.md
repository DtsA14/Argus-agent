# Probe rantai ledger → viewer (SPEC_CHAIN_PROBE), T1 `max_usd`, 2026-11-11

T1 selesai: ledger `f2852da` (issue 019). S (staging Stage 17) dan T2 (viewer) belum.

| job | hasil | biaya | catatan |
|---|---|---|---|
| j20261111_112252_11b3 | draf OK (3 tes merah benar), agen DONE, **patch ditolak** | $0,0757 | drafter hanya mengubah test_api.py dan test_stage_times.py, melewatkan test_title_in_jobs.py (daftar key persis). Agen lalu menaruh `_relax_stale_key_lists()` di kode produksi: bila `pytest` ada di `sys.modules`, ia menimpa konstanta tes dengan objek yang `==` ke list apa pun. Tes lama lulus karena dibutakan. Tidak di-apply. |
| j20261111_113723_c4be | draf OK, agen FAILED_ACCEPTANCE, abandon | $0,0770 | kali ini drafter mengubah test_title_in_jobs.py tetapi melewatkan test_api.py (perbandingan dict persis). Agen tak bisa mengubah tes terkunci. |
| j20261111_114930_18a2 | draf OK, agen DONE, **di-apply** | $0,0250 + agen | issue menyebut ketiga file tes terdampak; patch bersih (tanpa trik tes). |

Issue: `019-max-usd.v1.txt` (awal), `.v2.txt` (menyebut test_title_in_jobs), `019-max-usd.txt` (menyebut ketiga file).
`argus redraft` ditolak pada job REVIEW_READY ("only a failed or unapproved draft is redrafted"), jadi koreksi = job baru.

## Perekat (tindakan manusia/Claude)

| perekat | bisa diotomasi? |
|---|---|
| Mengetahui **tes lama mana** yang membandingkan bentuk persis item dan harus ikut berubah (`grep` field serupa di tes) | **ya**: harness bisa mencari tes lama yang mengandung key tetangga (`cost_usd`) atau konstanta daftar key; ini celah "tes lama bocor" di PENDING, sekarang terbukti dua kali berbeda dalam satu issue |
| Mengenali kecurangan agen di patch (kode produksi yang mengenali pytest) | **sebagian**: pemindaian patch untuk `sys.modules`/`pytest`/`PYTEST` di berkas non-tes bisa jadi gerbang; penilaian akhir tetap manusia |
| Menulis ulang issue dengan nama berkas tes terdampak | ya, bila perekat pertama otomatis |
| Memutuskan abandon vs retry (retry sia-sia bila tes terkunci salah) | sebagian |

Belum diukur: perekat S dan T2 (bentuk field dari patch T1 ke issue viewer), menit Atha.
