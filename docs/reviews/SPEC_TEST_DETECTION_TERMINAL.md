# Spek: hit gerbang deteksi tes menjadi terminal (GATE)

> **Amandemen 2026-11-14:** `SPEC_GATE_RC_CLARIFICATIONS.md` (TERMINAL Usul 1 menggantikan kalimat terakhir C3 di `SPEC_TEST_DETECTION_GATE.md`; perilaku hit bersama laporan konflik dan hit pada attempt diblokir dicatat di sana).

Status: **dikerjakan Claude 2026-11-12** (fase 3, GATE; `FABLE_SPEC_REPORT_CONFLICT_v1.md` §8 butir 2, `FABLE_PLAN_2026-11-11.md`). Bertumpu pada RC
(`ReportConflict`, #473): jalan keluar yang sah sudah ada, jadi umpan balik yang mengajari pola mana yang harus dihindari tidak lagi dibutuhkan. Jalur ketat:
mengubah keputusan di node acceptance. Berlaku AGENTS.md; **merge dari Atha**. Tanpa model, tanpa uang.

## Masalah

`scope:no_test_detection` (SPEC_TEST_DETECTION_GATE) menggagalkan verdict bila kode produksi mengenali tes (`PYTEST_CURRENT_TEST`, `"pytest" in sys.modules`, ...).
Hari ini hit itu masuk umpan balik attempt berikutnya (`unmet`: alasan dan baris yang cocok), sehingga agen diberi tahu pola mana yang tertangkap dan boleh mencoba
pola lain. Gerbang ini pagar, bukan bukti; mengajari agen menghindarinya melemahkannya.

## Usul

1. **Terminal.** Bila `scope:no_test_detection` gagal pada verdict sebuah attempt, run berakhir `FAILED_ACCEPTANCE` dengan `stop_reason` berawalan `test_detection`.
   Tidak ada attempt berikutnya, jadi tidak ada umpan balik ke agen. Urutan di node acceptance (sesudah urutan v3 C3 dari RC): pass, blocked, `llm_failed`, laporan
   konflik (terkonfirmasi atau sandbox tak ada), **hit deteksi**, lalu `max_iterations`/stagnasi/admission. Laporan konflik tak pernah terkonfirmasi bila kriteria ini gagal
   (RC mensyaratkan semua kriteria non-validasi lulus), jadi hit deteksi tidak bisa disembunyikan di balik laporan.
2. **Terlihat oleh manusia.** Ringkasan verdict (`result.json`, `verdict.detected`) memuat jumlah hit dan sampai lima hit (path, baris, nama pola; bukan teks barisnya),
   dan `status` pada job `AGENT_FAILED` menampilkan baris `test detection (shown to you, never to the agent): <path>:<baris> <pola> ...`.
3. Verdict lengkap (`verdict_<i>.json`) tidak berubah: kriteria dan buktinya tetap ada untuk manusia dan hakim.

## Di luar cakupan

Mengubah pola, ambang, atau cara pemindaian. Menolak `retry` biasa (retry tetap boleh: run baru, kontrak sama; manusia yang memutuskan).

## Tes (gagal di kode lama), `tests/test_detection_terminal.py`

hit saat validasi lulus semua → `FAILED_ACCEPTANCE/test_detection`, satu attempt, model tidak dipanggil lagi; hit bersama kegagalan lain → tetap terminal; hit bersama
laporan konflik → terminal (tak terkonfirmasi); umpan balik tidak pernah memuat alasan deteksi; ringkasan membawa `detected` tanpa teks baris; `status` menampilkannya;
verdict tanpa hit tidak berubah (stagnasi dan `max_iterations` seperti biasa). Mutants: `verification/detection_terminal_mutants.py`.
