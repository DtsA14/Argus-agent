# Spek: staging hardening (temuan /code-review di kode staging v0)

Status: **disetujui Atha 2026-10-29/30** ("Staging v0 jadi PR terpisah aja", "Ok gas"). Jalur ketat (`router/stage.py`).
Sumber: `/code-review medium` yang tidak sengaja dijalankan pada merge #244 (staging v0) saat review #246; temuan yang
dipilih Claude, disetujui Atha. Tidak ada perilaku baru untuk operator selain penolakan yang lebih jujur.

## Perubahan dan jaminan (dites; mutants)

1. **State terakhir, event dulu.** Saat rilis baru menjadi live, `releases.jsonl` (`live`) ditulis dulu, `state.json`
   terakhir. Gagal menulis apa pun sebelum `state.json` → container baru dihentikan dan **state tetap menyebut rilis lama**
   (dulu: state sudah menyebut rilis baru yang container-nya dihentikan, lalu `reconcile` berikutnya mematikan yang lama).
   Untuk deploy dan rollback.
2. **`state.json` rusak tidak dibaca sebagai "tidak ada yang live".** Tidak ada berkas = staging baru. Berkas yang tidak
   terbaca, bukan JSON, atau tidak berbentuk state (`history` daftar string, `live` null atau ada di `history`) →
   deploy dan rollback ditolak **sebelum `reconcile`** (tidak ada container yang dihentikan), `status` menulis sebabnya.
   Pemulihan manual dari `releases.jsonl`.
3. **`docker rm` dicek.** Gagal selain "No such container" → `Refused` ("may still be running"), tidak pernah dicatat
   `stopped`.
4. **`docker logs` yang macet tidak menahan stop.** Setelah rilis baru live, kegagalan apa pun saat menyalin log rilis
   lama (termasuk `TimeoutExpired`) tidak mencegah rilis lama dihentikan.
5. **Smoke menunggu socket mendengar**, bukan hanya berkasnya ada (uvicorn membuat berkas saat `bind()`, sebelum
   `listen()`): connect dicoba sampai berhasil atau `SOCKET_WAIT_S` habis.

## Tidak diubah (dicatat)

- `job.note("staged")` sesudah lock staging dilepas: job sibuk → CLI melapor gagal padahal rilis sudah live (`status`
  benar). Jarang (tidak ada perintah job lain selama staging); dibiarkan.
- `reconcile()` sebelum konfirmasi lalu "nothing was changed" bila N: hanya menghentikan container staging yang memang
  bukan live; teks dibiarkan.
- Format image `repo@sha256:…` vs id di `docker inspect`: pin kita selalu id (`sha256:`), tidak terjadi.
- Symlink di rilis dan `snapshot` (`SPECIAL`): argus-ledger tidak punya symlink; dicatat sebagai batas.
