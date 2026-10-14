# Desain 2c: worker loop + memo per langkah

Branch `m2-2c` dari `main` `d9f3e78`. DoD dari GPT (2026-10-14) di bawah; urutan kerja: memo dan
tes crash-resume dulu, baru worker loop.

## DoD (GPT)

1. Worker menjalankan loop tool-calling dengan batas langkah, budget tetap ditegakkan.
2. Memo persisten per langkah dengan kunci stabil: run, task, step, dan identitas input.
3. Hasil tool di-commit sebelum worker lanjut ke langkah berikutnya.
4. Crash setelah langkah berhasil tidak membuat langkah itu dipanggil ulang saat resume.
5. Memo lama tidak dipakai kalau input, spesifikasi, atau versi tool berubah.
6. Tes membuktikan **jumlah panggilan ulang nol** untuk langkah yang sudah selesai, bukan cuma hasil akhirnya sama.
7. Memo bukan exactly-once: tool dengan efek samping butuh idempotency key atau rekonsiliasi.

## Keputusan desain

**Kunci memo memuat identitas input.** Memo DB per run (`memo.sqlite`), jadi run sudah implisit.
- Langkah LLM: `("llm", node, task, iteration, step, sha256(pesan sejauh ini + skema tool + model))`.
- Langkah tool: `("tool", node, task, iteration, step, tool_call_id, sha256(nama + argumen), versi tool)`.

Karena hash pesan ikut di kunci, replay langkah 0..k dari memo menghasilkan pesan yang identik dan
kuncinya cocok. Kalau instruksi, feedback, model, atau versi tool berubah, hash berubah dan memo lama
tidak terpakai (DoD 5).

**Urutan per langkah:** panggil model → commit balasan ke memo → jalankan setiap tool call →
commit hasil tool → baru lanjut (DoD 3).

**Ledger tetap sumber kebenaran biaya, memo hanya mencegah panggilan ulang.** Masalah yang ditemukan
saat mendesain: setelah crash, node yang belum selesai dijalankan ulang dengan reservasi baru yang
penuh, jadi node bisa menghabiskan sampai 2× estimasinya di dua proses. Solusinya, reservasi node
diinisialisasi dari ledger: semua `llm_call` sebelumnya dengan `(node, task, iteration)` yang sama,
termasuk `unknown_after_crash` dengan biaya worst case, sudah dihitung terpakai. Replay dari memo tidak
di-charge lagi (biayanya sudah ada di ledger). Dengan begitu batas per node berlaku lintas crash, dan
`tokens_used` di state cocok dengan ledger. Ini juga diterapkan ke orchestrator 2b, yang punya celah
yang sama.

**Jendela yang tersisa (didokumentasikan, diuji):** crash setelah model membalas tapi sebelum memo
ter-commit membuat panggilan itu diulang. Ledger mencatat keduanya dan reservasi menghitung keduanya,
jadi ulangan ini kelihatan dan tetap dalam batas.

**Efek samping (DoD 7):** tool menerima idempotency key (kunci memo langkahnya). Di 2c tool-nya hanya
`read_data` (tanpa efek samping) dan `SubmitResult`; `write_file` (atomic, temp lalu rename) dan
`run_python` menyusul di 2d dengan aturan yang sama.

**Worker loop:**
- Konteks worker hanya: instruksi task, feedback, deskripsi data, format output dari kontrak, tools.
- Selesai lewat tool `SubmitResult`; nilainya divalidasi harness terhadap skema output kontrak
  (mis. `top3` = 3 pasang `[produk, total]`). Tidak valid → error dikembalikan ke model, dihitung satu langkah.
- Tool tak dikenal atau argumen tidak valid → error sebagai `ToolMessage`, dihitung satu langkah.
- `max_steps` habis, reservasi habis, atau error model permanen → worker mengembalikan hasil gagal
  dengan alasannya; evaluator menilai output itu gagal, dan orchestrator bisa merevisi di iterasi berikutnya.

**Tes lintas proses dengan worker paralel:** provider `fake` dapat skrip per task (dipilih dari
`Task id:` di prompt), dengan posisi skrip per task di file, supaya urutan worker paralel tidak
mengacak skrip. Jumlah panggilan model dihitung dari posisi skrip, dan jumlah eksekusi tool dari
event `step_committed kind=tool`.

Titik crash baru: `worker@after_llm` (sebelum commit, jendela yang tersisa), `worker@llm_committed`,
`worker@tool_committed`.

## Hasil implementasi

- Ditemukan saat pengujian: kunci memo tool awalnya hanya `(langkah, id call, nama, argumen, versi)`.
  Saat feedback berubah, langkah LLM memanggil ulang tapi hasil tool lama ikut terpakai karena
  nama/argumen/id-nya kebetulan sama (melanggar DoD 5). Kunci tool sekarang memuat kunci langkah LLM
  induknya.
- Bukti "nol panggilan ulang" (DoD 6): jumlah panggilan model nyata dihitung dari posisi skrip palsu
  per task lintas proses, jumlah eksekusi tool dari event `step_committed kind=tool`. Crash setelah
  commit: task yang crash tepat 2 panggilan (sama dengan tanpa crash) dan ReadData sekali. Crash
  sebelum commit: tepat satu panggilan diulang, tercatat di ledger, dan ditanggung reservasi node.
- Reservasi lintas crash: dengan batas 4000 token, node yang sudah memakai 3651 sebelum crash menolak
  langkah berikutnya (reservasi baru akan mengizinkannya).
- Orchestrator: tidak di-memo per percobaan (rencana dibeli ulang setelah crash di tengah planning),
  tapi reservasinya dipulihkan dari ledger, jadi biaya ulangannya terhitung dan dibatasi.
