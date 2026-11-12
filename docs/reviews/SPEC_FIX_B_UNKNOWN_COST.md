# Spek: FIX-B, harga harus angka yang bisa dipakai (E2); E1 ditunda

Status: **keputusan Atha 2026-11-11** (rencana Fable, FIX-B; jalur ketat didelegasikan, "skip kalo ragu"). Temuan: `AUDIT2_2026-11-11` E1 dan E2. Tanpa model, tanpa uang.

## 1. Cakupan

**E2 (dikerjakan).** `check_priced` hanya memeriksa harga ada. Harga negatif menurunkan biaya tercatat; `{input: 0, output: 0}` pada penyedia langsung membuat cap yang terbatas tak berarti.
Hanya gateway yang menjaga ini (`gateway.entry`). `check_priced` sekarang memanggil `check_price_values` (`harness/llm.py`):
1. tarif (`input`, `output`, `cache_read`, `cache_write_5m`, `cache_write_1h`) yang bukan angka, bukan bilangan hingga, bool, atau negatif **selalu ditolak**; tarif cache yang `null` berarti "tidak diketahui" dan boleh;
2. harga tanpa kunci `input` atau `output`, atau dengan `input`/`output` `null`, ditolak;
3. `peak_multiplier` harus bilangan hingga paling sedikit 1, dan `long_context_above` bilangan positif (pengali di bawah 1, nol, negatif, NaN atau string menekan biaya tercatat);
4. `input` atau `output` bernilai 0 pada penyedia langsung dengan `budget.max_usd` terbatas ditolak ("model itu tak membebani cap"); model gateway tetap diperiksa `gateway.entry` (`free: true`);
   `max_usd: null` mengizinkan nol.
Semua 14 harga di `config.yaml` tetap lolos.

**E1 (diputuskan Atha 2026-11-11: opsi C, terima celahnya).** Biaya yang tak bisa dihitung (cache-write tanpa tarif tulis pada model non-Anthropic) ditulis `usd_nano: null` di ledger, tetapi `Reservation.charge` menjumlahkan `nano or 0`
dan `reconcile_ledger` melewati baris null: panggilan itu gratis bagi cap, juga sesudah resume. Percobaan perbaikan (branch `fix-b-e1-draft`: menagih yang lebih besar dari kasus terburuk dan pemakaian nyata pada tarif tulis
tertinggi, `charged = worst_case_unknown_cost`, 22 mutan mati) **membenturkan dua hal yang sudah tertulis**: aturan `AGENTS.md` "Unknown cost is `null`, never `0`" (ledger akan memuat angka, bukan null) dan tes
`tests/test_peak_edges.py::test_an_unknown_cost_after_sending_is_null_and_charged` (keputusan SPEC_PEAK_EDGES: biaya tak diketahui dicatat null). Pilihan yang ditawarkan (Atha memilih **C**):
- **A.** Catat angka kasus terburuk di `usd_nano` (preseden: `worst_case_no_usage`); konsisten dengan reservasi dan resume; mengubah aturan "unknown is null" untuk kasus ini dan tes itu.
- **B.** Tetap `usd_nano: null`, tambah kolom `charged_nano` di event dan buat `reconcile_ledger` serta `reservation_from_ledger` menghitungnya bila `usd_nano` null; aturan "null" utuh, perubahan lebih besar
  (konsumen ledger lain, termasuk `argus-ledger`, memperlakukan null sebagai 0).
- **C.** Terima celah: model non-Anthropic tanpa tarif tulis yang melaporkan cache-write jarang; catat sebagai batasan.

## 2. Tes (gagal di kode lama)

Tiap tarif non-angka, NaN, tak hingga, bool, string, negatif (`input`, `output`, `cache_read`; anggaran terbatas dan tidak); nol `input` atau `output` pada `deepseek:` ditolak dengan anggaran terbatas dan lolos dengan `max_usd: null`;
`cache_read: 0` lolos; `input`/`output` `null` ditolak dan cache `null` lolos; pengali puncak di bawah 1 atau bukan angka ditolak; `long_context_above` non-positif ditolak; kunci `input`/`output` hilang ditolak;
semua harga di `config.yaml` tetap lolos.
Mutan: tiap cabang `check_price_values` (bukan angka, hingga, bool, negatif, nol), pengecualian gateway, batas terbatas/tak terbatas, pengecualian `None` cache, pengali, ambang, kunci hilang, pemanggilan.

## 3. Keputusan E1: C (terima)

Alasan (Claude, disetujui Atha): kasusnya tidak bisa dicapai oleh model yang dikonfigurasi hari ini (Anthropic wajib punya tarif tulis; model gateway memakai biaya yang dilaporkan gateway; DeepSeek langsung hanya melaporkan
cache-hit), mengubah inti uang (A) atau ledger dan semua konsumennya (B) lebih berisiko daripada celahnya, dan run yang menyentuhnya ditandai `usd_complete = false`. Batas dicatat di `AGENTS.md` ("Known limit").
**Dibuka lagi bila:** penyedia langsung yang melaporkan token cache-write ditambahkan, atau `usd_complete = false` muncul di job nyata. Perbaikannya sudah siap di branch `fix-b-e1-draft` (opsi A, 22 mutan mati) dan hanya
perlu keputusan A atau B dan pembaruan `tests/test_peak_edges.py`.
