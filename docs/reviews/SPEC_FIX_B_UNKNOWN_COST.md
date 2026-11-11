# Spek: FIX-B, biaya yang tidak diketahui tidak pernah gratis bagi cap (E1); harga harus angka yang bisa dipakai (E2)

Status: **keputusan Atha 2026-11-11** (rencana Fable, FIX-B; jalur ketat didelegasikan, "skip kalo ragu"). Temuan: `AUDIT2_2026-11-11` E1 dan E2, dibuktikan dengan membaca
kode (`models/pricing.py:66-68`, `harness/llm.py` `Reservation.charge` dan `check_priced`). Tanpa model, tanpa uang.

## 1. Masalah

**E1.** `cost_usd` mengembalikan `None` bila balasan melaporkan pemakaian yang harganya tidak ada (token cache-write tanpa tarif tulis). Ledger menulis `usd_nano: null`, tetapi
`Reservation.charge` menjumlahkan `nano or 0`, dan `reconcile_ledger` melewati baris null: panggilan itu **gratis bagi cap**, juga sesudah resume. Aturan `AGENTS.md`: "Unknown cost is `null`, never `0`",
dan cap tidak boleh bisa dilewati oleh biaya yang tak terhitung.

**E2.** `check_priced` hanya memeriksa harga ada. Harga negatif menurunkan biaya tercatat; `{input: 0, output: 0}` pada penyedia langsung membuat cap yang terbatas tak berarti. Hanya gateway
yang menjaga ini (`gateway.entry`).

## 2. Perubahan (`harness/llm.py`)

1. **E1.** Pada jalur balasan sukses, sesudah blok gateway: bila `nano is None` dan model punya harga (`self.price is not None`), tagih **kasus terburuk** panggilan itu (`worst_nano`, yang
   sudah ditulis di `llm_call_started`), catat `usd_nano = worst_nano` dan `charged = "worst_case_unknown_cost"` (preseden: `worst_case_no_usage`). Ledger dan reservasi sama, jadi resume menghitung hal
   yang sama. Model tanpa harga tetap `null` dan dengan anggaran terbatas sudah ditolak sejak konstruksi (`check_priced`).
2. **E2.** `check_priced` memanggil `check_price_values` untuk harga yang ada: tarif (`input`, `output`, `cache_read`, `cache_write_5m`, `cache_write_1h`) yang bukan angka, bukan bilangan hingga,
   bool, atau negatif **selalu ditolak** (tarif cache yang `null` berarti "tidak diketahui" dan boleh); `input` atau `output` bernilai 0 pada penyedia langsung dengan `budget.max_usd`
   terbatas **ditolak** ("model itu tak membebani cap"); model gateway tetap diperiksa `gateway.entry` (`free: true`); `max_usd: null` mengizinkan nol.

**Perubahan sesudah review (Sonnet):**
3. E1 menagih **yang lebih besar** dari kasus terburuk pra-kirim dan pemakaian nyata yang dihargai dengan setiap token tulis pada tarif tertinggi yang dimiliki harga itu (`input`, `cache_write_5m`,
   `cache_write_1h`), dengan pengali terburuk. Alasan: `worst_nano` berasal dari estimasi, yang bisa meleset (hitungan heuristik, atau penyedia yang mengabaikan `max_tokens`).
4. `check_price_values` juga menolak harga tanpa kunci `input` atau `output`, `peak_multiplier` yang bukan bilangan hingga bernilai paling sedikit 1 (pengali di bawah 1, nol, negatif, NaN atau string menekan
   biaya tercatat), dan `long_context_above` yang bukan bilangan positif.

## 3. Tes (gagal di kode lama)

1. Panggilan dengan cache-write tanpa tarif tulis: ledger `charged = worst_case_unknown_cost`, `usd_nano = worst_usd_nano`, reservasi sama, dan `reconcile_ledger` sama dengan reservasi.
2. Biaya yang diketahui tetap `actual`; model tanpa harga dengan anggaran tak terbatas tetap `null` dan tidak menagih.
3. Tiap tarif non-angka, NaN, tak hingga, bool, string, negatif: ditolak untuk `input`, `output`, `cache_read`, dengan anggaran terbatas dan tidak terbatas.
4. `input` atau `output` 0 pada `deepseek:` dengan anggaran terbatas ditolak; dengan `max_usd: null` lolos; `cache_read: 0` lolos.
5. Semua 14 harga di `config.yaml` tetap lolos (model gratis lewat gateway), dan tarif `input`/`output` yang `null` ditolak sedangkan cache `null` lolos.
Mutan: kondisi `nano is None`, `self.price is not None`, label `charged`, tiap cabang `check_price_values` (bukan angka, hingga, bool, negatif, nol), pengecualian gateway, batas terbatas/tak terbatas, pengecualian `None` cache.

## 4. Di luar cakupan

Pemeriksaan harga jalur gateway (sudah ada), `paid.py` (kasus E4), fsync ledger dan redaksi key (FIX-C).
