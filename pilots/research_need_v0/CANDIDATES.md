# Kandidat issue untuk bukti "riset dibutuhkan" (2026-11-04, tanpa model, tanpa biaya)

Tujuan (PENDING, planner berhirarki): satu issue argus-ledger yang lengan tanpa riset (`argus code`) kerjakan salah.
Pilot 015 gagal membuktikannya: `exclude_content_types` ternyata sudah dikenal DeepSeek. Cara kerja sekarang: baca
release notes, uji perilaku di dua venv scratch (up1 = starlette 1.8.0 + fastapi 0.143.2, up2 = starlette 1.10.0 +
fastapi 0.162.0, pydantic 2.14.2), baru tulis kandidat. Skrip: `probe_params.py`, `probe_deprecations.py`.
Sumber: `docs/release-notes.md` di fastapi/fastapi dan encode/starlette (master, 2026-11-04).

## Perilaku yang terbukti berbeda (up1 → up2)

| Perubahan (rilis) | up1 | up2 |
|---|---|---|
| Dua model query digabung, `f: Annotated[A, Query()], p: Annotated[B, Query()]` (fastapi 0.157) | 422, `f` dan `p` "missing" | 200 |
| Model query opsional, `Annotated[A \| None, Query()] = None` (0.159) | `AssertionError` saat app dibuat | 200; `null` bila tanpa query |
| `extra="forbid"` pada model query menolak parameter saudaranya (0.160) | 422 "missing" (model tidak jalan) | 422 `extra_forbidden` pada `limit` |
| `null` JSON eksplisit vs tidak dikirim, `Body()` (0.151) | `null` diganti default (200) | `null` → `None` (200); `n: int = 1` dengan `null` → 422 |
| Default `Query(ge=1) = 0` tidak divalidasi (0.148) | 422 | 200 |
| `FastAPI(root_path=...)` deprecated (0.146) | tanpa peringatan | `FastAPIDeprecationWarning` (turunan `UserWarning`, **bukan** `DeprecationWarning`: `-W error::DeprecationWarning` tidak menangkapnya) |
| `Query(custom=...)` dihapus (0.155) | jalan | `TypeError`; `regex=`/`example=` hanya memperingatkan |
| `TestClient.stream()` kembali sebelum app selesai (starlette 1.9) | menunggu app | segera; menutup respons membatalkan app |

Tidak relevan untuk argus-ledger (tidak dipakainya): form/boolean/file (0.147-0.153, 0.158, 0.161-0.162), WebSocket security
(0.144), `FileResponse` Range (1.10.0), `Match`, `FloatConvertor`, `Config`. Host case-insensitive (1.9) dan `Vary` yang
dipertahankan (1.9) hanya memperbaiki sisi up1: di up2 semua lengan lulus.

## Kandidat, berurutan

Syarat: issue ditulis seperti pengguna (apa yang harus terjadi, tanpa menyebut API), grader tersembunyi dijalankan di
`ledger_py312_up2`, dan jawaban natural dari ingatan lama harus bisa salah di up2.

| # | Issue (perilaku yang diminta) | Kenapa ingatan lama bisa salah | Risiko kandidat |
|---|---|---|---|
| K1 | `POST /jobs/{id}/note` (JSON `{"note": ...}`): `null` menghapus catatan, tidak dikirim = tidak berubah | `null` dulu jatuh ke default; kini dibedakan. Implementasi `Body()` dengan default melewatkan perbedaan itu di up1, kini benar | Endpoint tulis baru: scope besar (sesi, CSRF, ledger yang tadinya baca-saja) |
| K2 | `GET /jobs` bisa difilter (`state`, `limit`, `offset`) lewat satu atau dua model Pydantic yang dipakai ulang di `/jobs.csv` | Dua model query digabung gagal di up1 (422), jalan di up2; model opsional `AssertionError` di up1 | Issue yang menyebut "model" menentukan implementasi; tanpa itu parameter biasa cukup dan riset tidak dibutuhkan |
| K3 | Layanan di belakang prefix `/ledger`: semua redirect dan tautan UI membawa prefix | `FastAPI(root_path=)` deprecated; cara baru lewat server (`uvicorn --root-path`) | Lolos tanpa riset (cuma peringatan `UserWarning`); grader harus mengecek peringatan, jadi menilai gaya, bukan kebenaran |
| K4 | `GET /jobs/stream` (SSE, satu event per job) dengan tes yang menutup tengah jalan | `TestClient.stream()` berubah di 1.9 (tidak lagi menunggu); tes lama bisa menggantung | Belum terbukti di venv; butuh probe dulu |

Penilaian jujur: K1 paling jelas butuh pengetahuan baru, tetapi mahal. K2 murah dan terbukti beda, tetapi hanya salah
bila issue-nya menentukan model. Kebanyakan perubahan up2 hanya memberi kemampuan baru, bukan membuat jalan lama salah:
lengan tanpa riset biasanya tetap benar lewat jalan lama. Peluang menemukan issue yang gagal tanpa riset di sini rendah;
n = 1 lagi mungkin hasilnya sama dengan 015.

## Penyaringan (menunggu "go live" kecil)

Satu panggilan DeepSeek per kandidat, tanpa tool, lewat `LLMCaller` (jalur ketat: cap, ledger), < $0,01 total. Pertanyaan
ke model: tulis endpoint/fungsi untuk issue itu **dan** jawab "perilaku apa di FastAPI 0.162 / Starlette 1.10 yang kamu
andalkan". Kandidat dilanjutkan ke pilot dua lengan hanya bila jawaban salah menurut probe di atas (K2: model menulis
dua model query digabung, atau menganggapnya tidak didukung; K1: menganggap `null` = default). Kalau semua jawaban
benar: hentikan, catat "ingatan DeepSeek cukup untuk kelas ini", dan tinggalkan alasan planner berhirarki dari jalur riset→kode.
