# Spek: probe rantai lintas repo (ledger → viewer), tanpa planner

Status: **usulan Claude 2026-11-11** (Atha: "bikin spek #1"; redraft otomatis 3b ditunda sampai ada kasus lagi). Langkah
kecil menuju pipeline berhirarki (PENDING "Satu pipeline berhirarki"), tanpa kode harness baru. **Tidak ada perubahan di
Argus**: hanya dua issue di repo latihan dan satu berkas catatan. Jalur cepat (aplikasi latihan); tidak menyentuh uang,
sandbox, key, atau grader.

## 1. Pertanyaan

PENDING membenarkan planner berhirarki hanya bila ada kerja yang tidak cukup dengan urutan tetap. Pertanyaan probe ini:
**apa saja yang manusia lakukan sebagai perekat** saat satu perubahan harus melewati dua repo, dan mana dari itu yang
bisa dikerjakan harness?

Rantai ini sudah terjadi tiga kali dengan tangan: Stage 15 (waktu stage) → viewer 041; Stage 16 (judul) → viewer 042/043;
Stage 14 (review draf) → halaman draf viewer. Probe ini menjalankan satu rantai lagi **dengan pengukuran**, bukan
membangun sesuatu.

## 2. Rantai yang diuji

Field baru: **`max_usd`** (batas biaya job, sudah ada di `job.json`, belum ada di API ledger).

| Langkah | Repo | Isi | Lane |
|---|---|---|---|
| T1 | argus-ledger | `GET /jobs` dan `GET /jobs/{id}` meneruskan `max_usd` bila berupa angka (aturan seperti issue 018: tidak ada key bila tidak ada, null, atau bukan angka) | `argus code`, "go live" per job |
| S | staging | Stage baru (satu "go live" per PLAN.md yang ter-commit); viewer membaca snapshot | seperti Stage 15/16 |
| T2 | argus-viewer | halaman job menampilkan "biaya $X dari $Y" dari `cost_usd` dan `max_usd`; tanpa `max_usd` tampilan lama | `argus code`, "go live" per job |

T2 bergantung pada T1 dan S: bentuk field (nama, tipe, bila hilang) harus dioper, dan snapshot staging harus sudah
memuatnya sebelum viewer dicek di HP.

## 3. Yang dicatat (satu berkas, `pilots/chain_probe_v0/RESULT.md`)

Per langkah: job id, biaya dari ledger, jumlah percobaan draf, penolakan formulir, retry agen, dan hasil judge. Per
**perekat** (tindakan manusia atau Claude di antara langkah), satu baris:

- apa yang dilakukan (mis. "menyalin bentuk field dari patch T1 ke issue T2", "menunggu apply", "memutuskan urutan",
  "menjalankan staging");
- menit, bila Atha ikut; jumlah keputusan Claude;
- **bisa diotomasi?** `ya` (harness cukup membaca artefak job), `sebagian`, atau `tidak` (butuh penilaian).

Tolok ukur supervisi tetap seperti `argus-supervision-measure`: jumlah keputusan Claude, waktu terminal "go live", menit
Atha (opsional).

## 4. Tolok ukur keberhasilan probe

- Bentuk field yang dioper ke T2 **diambil dari patch T1 yang sudah di-apply**, bukan dari tebakan; bila T2 salah karena
  bentuk field, itu temuan (perekat gagal), bukan kegagalan probe.
- Setiap perekat tercatat dengan penilaian `bisa diotomasi?`.
- Biaya total rantai (T1 + T2) di bawah $0,30.

Hasil probe menentukan dua hal: (a) bila semua perekat `ya`/`sebagian` dan kecil, kandidat berikutnya adalah operator
rantai tetap (`argus chain`: T1 → apply → S → T2) sebelum planner; (b) bila ada perekat `tidak` yang sering, itu bahan
spek planner. Bila rantai berjalan tanpa perekat berarti, tahap 3 tetap tidak dibenarkan dan dicatat begitu.

## 5. Urutan kerja

1. Atha menyetujui spek ini ("go live" untuk T1, T2 menyusul karena bergantung pada T1).
2. Claude menulis issue T1 (`argus-ledger-issues/019-max-usd.txt`), `argus code`, review, apply.
3. Staging: PLAN.md dan Stage 17 (satu "go live" sendiri).
4. Claude menulis issue T2 dari **patch T1 yang ter-apply**, `argus code`, review, apply, deploy viewer.
5. `RESULT.md` dan satu baris di PENDING; PR membawa log pilot.

## 6. Di luar cakupan

- Planner, operator rantai, oper hasil otomatis (ADR-005), cap bertingkat, replan. Semuanya menunggu hasil probe.
- Auto-redraft (3b): ditunda sampai ketemu kasus `submits_exhausted` lagi.
- Perubahan pada `harness/`, `router/`, atau `codetask/`.
