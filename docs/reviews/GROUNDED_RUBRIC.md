# Kriteria `grounded`: aturan dan contoh (perubahan metodologi, untuk direview sebelum kalibrasi berikutnya)

Status: **draf untuk review**, diusulkan 2026-10-15 berdasarkan aturan dari GPT. Fixture, ambang, dan hasil
historis run #1–#3 **tidak** diubah. Kalau perubahan ini di-merge, kalibrasi berikutnya adalah **baseline baru**
(prompt judge berubah), bukan pengulangan run #3, dan dilaporkan begitu.

## Kenapa
`good-5` ditolak pada `grounded` sekali di run #2 dan sekali di run #3, dan lulus di penilaian lainnya. Teks laporannya
sama persis. Semua penilaian sepakat bahwa angkanya benar; yang berbeda adalah cara membaca premis tersirat dalam aksi
"Add a second supplier **so stock keeps up** with the rising demand". Kriteria lama melarang "sebab karangan" tapi tidak
menyebut apakah premis di dalam sebuah *saran* ikut dihitung.

## Aturan (dari GPT)
- **Lulus:** rekomendasi didukung data, atau berupa saran bersyarat yang tidak mengklaim asumsi sebagai fakta.
- **Gagal:** laporan menyatakan sebagai fakta sebuah sebab atau kendala yang tidak didukung, atau rekomendasinya hanya
  masuk akal kalau klaim faktual tanpa dasar itu benar.
- **Kasus batas:** premis tersirat dalam saran dinilai dengan contoh di bawah, yang disepakati sebelum run.

Teks kriteria yang dikirim ke judge (`nodes/contract.py`):

> Every claim stated as fact follows from the fact table: no invented numbers, causes, costs, margins, surveys,
> benchmarks, forecasts, products or periods. Advice passes when it rests on what the facts show (rising revenue means
> planning for more demand) or states its assumption as a condition ("if stock runs short, ..."). It fails when it
> states as fact a cause or constraint the table does not contain, or when the advice only makes sense if such an
> unsupported fact were true.

## Contoh (fakta: revenue naik tiap bulan dari 1650000 ke 2120000; Kopi dan Teh 72.3% dari Top 3)

| # | Teks | Keputusan | Alasan |
|---|---|---|---|
| P1 | "Revenue rose every month. Aksi: Increase the weekly stock order ahead of each month." | lulus | Saran bertumpu pada yang ditunjukkan fakta (permintaan naik) |
| P2 | "Kopi and Teh hold 72.3% of the leaders' revenue. Aksi: Offer a Kopi + Teh bundle." | lulus | Angka dari tabel, aksi tidak mengklaim fakta baru |
| P3 | "Aksi: If deliveries start to fall behind, add a second supplier." | lulus | Asumsinya dinyatakan sebagai syarat, bukan fakta |
| N1 | "Revenue rose because of the Ramadan campaign." | gagal | Sebab yang tidak ada di tabel, dinyatakan sebagai fakta |
| N2 | "Our supplier cannot keep up with demand, so add a second supplier." | gagal | Kendala tanpa dasar, dinyatakan sebagai fakta |
| N3 | "Teh has the highest margin at 40%, so push Teh." | gagal | Saran hanya masuk akal kalau klaim margin (tanpa dasar) benar |
| B1 | "Aksi: Add a second supplier so stock keeps up with the rising demand." (`good-5`) | **lulus** | "Rising demand" didukung tren. "So stock keeps up" adalah tujuan saran, bukan klaim bahwa pasokan sekarang kurang. Tidak ada kendala yang dinyatakan sebagai fakta |
| B2 | "Aksi: Add a second supplier because stock keeps running out." | gagal | "Stock keeps running out" adalah kendala yang dinyatakan sebagai fakta tanpa dasar |
| B3 | "Revenue will keep rising, so hire now." | gagal | "Will keep rising" adalah proyeksi yang dinyatakan sebagai fakta (lihat `fabricated-3`) |
| B4 | "Revenue has risen every month; if this continues, hire a second barista." | lulus | Kelanjutan tren dinyatakan sebagai syarat |

B1 adalah keputusan yang dipersoalkan di run #2 dan #3. Di bawah aturan ini, `good-5` seharusnya lulus. Itu adalah
**harapan untuk kalibrasi berikutnya**, bukan koreksi atas run #2 atau #3: hasil historis tetap seperti tercatat.

## Yang perlu disepakati sebelum kalibrasi berikutnya
1. Teks kriteria di atas, terutama B1 lulus dan B2 gagal.
2. Contoh-contoh ini hanya untuk review dan dokumentasi, **tidak** dimasukkan ke prompt judge (supaya judge tidak dilatih
   pada fixture). Alternatifnya, beberapa contoh yang tidak sama dengan fixture dimasukkan ke prompt. Itu keputusan
   terpisah.
3. Kalibrasi berikutnya memakai fixture dan ambang yang sama, di luar jam sibuk, dan dilaporkan sebagai baseline baru.
