# Pilot UI kontrol #6: kirim ulang dengan touches yang sama, enam submit per giliran

**"Go live" Atha 2026-11-11 ("Ok langsung go live")**, sesudah PR ini merge. Penyebab: giliran pertama issue ledger
(`j20261111_054721_cebd`) WRITE_FAILED: Haiku mengganti touches di tiap submit sesudah menerima kode, jadi daftar dan
kodenya berubah terus sampai jatah 4 submit habis. Perbaikan: penolakan, prompt dan skema menyebut "touches yang sama";
`max_submits` 4 → 6.

Claude menjalankan langkah berurutan, satu langkah = satu perintah (atau satu cek), mencatat output di `steps.md`, dan
berhenti di langkah pertama yang tidak sesuai harapan. Tanpa model. Port 8000, ledger dan proxy 8710 tidak disentuh.

| # | perintah / cek | harapan |
|---|---|---|
| 0 | `systemctl --user is-active argus-control`; `git -C ~/pilot3a_live log -1`, `status --short`; tidak ada job `issue` `WRITING` | `active`; HEAD `dd88aab` atau sesudahnya tanpa PR ini; bersih; tidak ada giliran berjalan |
| 1 | `git -C ~/pilot3a_live pull --ff-only` | fast-forward ke merge PR ini |
| 2 | `systemctl --user restart argus-control`; `is-active`; `ss -ltn` | `active`; 8711 hanya di `127.0.0.1:8711` |
| 3 | `curl` (Host `localhost:8711`): `GET /issues`, `GET /issues/j20261111_054721_cebd` | 200 dengan CSP; job WRITE_FAILED punya form balasan |

Selesai sesudah aksi Atha dari Safari: balasan ke `j20261111_054721_cebd` (giliran baru). Claude mencatat hasilnya
(submit, touches, baris tes, clash) di `RESULT.md`.

Rollback: `git -C ~/pilot3a_live checkout <HEAD langkah 0>` lalu restart `argus-control`; butuh "go live" sendiri.
