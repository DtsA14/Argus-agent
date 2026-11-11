# Pilot UI kontrol #7: baris tes yang ditunjukkan bukan clash dengan sendirinya

**"Go live" Atha 2026-11-11 ("Kalo beres, langsung kerjain #1 dan #2 bro"; #2 = perbaikan ini).** Penyebab: issue viewer
judul (`j20261111_043029_53f7`) mendaftar 6-7 clash bersyarat ("Fixture has no title") karena penolakan harness meminta
"put each in clashes". Perbaikan: penolakan menyebut hanya tes yang PASTI gagal dengan fixture-nya sendiri; prompt sama.

Claude menjalankan langkah berurutan, satu langkah = satu perintah (atau satu cek), mencatat output di `steps.md`, dan
berhenti di langkah pertama yang tidak sesuai harapan. Tanpa model. Port 8000, ledger dan proxy 8710 tidak disentuh.

| # | perintah / cek | harapan |
|---|---|---|
| 0 | `systemctl --user is-active argus-control`; `git -C ~/pilot3a_live log -1`, `status --short`; tidak ada job `issue` `WRITING` | `active`; HEAD `f065ce7` (#423) atau sesudahnya tanpa PR ini; bersih; tidak ada giliran berjalan |
| 1 | `git -C ~/pilot3a_live pull --ff-only` | fast-forward ke merge PR ini |
| 2 | `systemctl --user restart argus-control`; `is-active`; `ss -ltn` | `active`; 8711 hanya di `127.0.0.1:8711` |
| 3 | `curl` (Host `localhost:8711`): `GET /issues`, `GET /issues/new` | 200 dengan CSP; form ada |

Hasil diukur pada issue berikutnya yang menyentuh tes lama (clash hanya yang pasti gagal).
Rollback: `git -C ~/pilot3a_live checkout <HEAD langkah 0>` lalu restart `argus-control`; butuh "go live" sendiri.
