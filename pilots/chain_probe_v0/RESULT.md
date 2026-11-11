# Probe rantai ledger → viewer (SPEC_CHAIN_PROBE), T1 `max_usd`, 2026-11-11

T1, S dan T2 selesai: ledger `f2852da` (issue 019), staging Stage 17 live, viewer `48d2d23` (issue 044, rilis `j20261111_131116_b7a9-48d2d2398d37`).

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

## S dan T2

- S: `pilots/staging_stage17/` (7 langkah, semua sesuai harapan, tanpa model). Terukur: 149 dari 149 job nyata punya `max_usd`; kasus tanpa `max_usd` hanya teruji di tes.
- T2 (`j20261111_131116_b7a9`): issue 044 ditulis Claude dari bentuk `max_usd` di patch T1 yang ter-apply (key sesudah `cost_usd`, angka, hilang bila tak ada). Draf pertama lolos ($0,0115; harness menjaga 46 tes lama lewat `old_tests_*`), agen 11 langkah ($0,0052), total $0,0167; patch bersih, tanpa penolakan, tanpa retry.
- Biaya rantai: T1 tiga job ($0,0757 + $0,0770 + $0,0293) + T2 $0,0167 = **$0,1987**, di bawah $0,30; dua job T1 pertama ($0,1527) tidak menghasilkan patch yang dipakai.

## Perekat tambahan (S dan T2)

| perekat | bisa diotomasi? |
|---|---|
| Menulis issue T2 dari bentuk field di patch T1 (nama key, tipe, posisi, bila hilang) | **sebagian**: bentuk field bisa diekstrak dari patch dan tes T1 (sebagian sudah ada di tes baru); kalimat tampilan (`of $Y`, dua desimal) tetap keputusan manusia |
| Menunggu staging S sebelum viewer dicek di HP | ya (urutan tetap T1 → apply → S → T2) |
| Satu "go live" per PLAN.md untuk S, satu per job `argus code` | gerbang manusia yang disengaja, bukan perekat |

Kesimpulan awal: T2 berjalan tanpa gesekan karena kontraknya ditulis dari patch yang ter-apply. Gesekan terbesar rantai ini ada di T1 (tes lama bocor), bukan di oper hasil antar repo. Itu mendukung operator rantai tetap (T1 → apply → S → T2) lebih dulu daripada planner; planner berhirarki tetap belum dibenarkan.
