# Spec router: waktu keputusan manusia, perintah apply, dan alasan gagal di `status`

Status: **spec, belum dikoding.** 2026-10-24. Ditulis Claude atas permintaan Atha ("Ok 1-3 bro"). Isinya menutup tiga
celah antara `SPEC_ROUTER_V0.md` dan `router/job.py`. **Keputusan yang diminta: bagian 5.**

## 1. Masalah

Router v0 sudah di `main` sejak #163 dan dipakai di setiap pilot sejak router pilot #1. Jaminan intinya (kunci per job,
cap job, cap tahap tetap saat resume, approve terikat ke sha draf) sudah ada dan sudah dicek mutan. Tiga hal dari spek
v0 belum dibuat:

1. **Waktu keputusan manusia** (spek v0 §3 poin 4: "catat waktu (konfirmasi, kunci, selesai) ke `job.json` untuk ukuran
   supervisi"). Sekarang hanya jalur `--yes` yang mencatat (`confirmed_by_flag`, `key_from_file`). Konfirmasi `[y/N]` di
   terminal, penolakan "N", dan kunci yang diketik tidak tercatat sama sekali. Butir PENDING "supervisi per pilot"
   berencana memakai `go_live.sh` untuk mencatat waktu terminal, tapi script itu tidak pernah dibuat, dan run lewat
   router tidak memakai gerbang per pilot lagi.
2. **Perintah apply di `REVIEW_READY`** (spek v0 §5: "router mencetak `PR.md`, letak `changes.patch`, dan perintah untuk
   menerapkannya"). Sekarang `status` hanya mencetak `review package: <dir> (valid)`.
3. **Alasan gagal** (spek v0 §5: "`AGENT_FAILED` dengan ringkasan verdict"). Untuk `AGENT_FAILED`, `DRAFT_FAILED`,
   `BLOCKED`, `REJECTED`, dan `ABANDONED`, `status` hanya mencetak nama state. Alasannya (`stagnant`, `budget: ...`,
   `contract_changed`, kriteria yang gagal) hanya ada di log `job.json` dan `result.json` run, jadi harus dibuka manual.

## 2. Usulan

### 2.1 Waktu keputusan (di `live()`)

Setiap tahap live mencatat ke log `job.json` (entri `{"at", "what", ...}` seperti yang sudah ada):

| Entri | Kapan |
|---|---|
| `limits_shown` | layar batas dicetak atau ditanyakan (sebelum `[y/N]`), dengan isi layarnya (`screen`) |
| `confirmed` | jawaban `y` di terminal |
| `not_confirmed` | jawaban selain `y`; tahap tidak dimulai (seperti sekarang) |
| `confirmed_by_flag` | `--yes` (sudah ada, tidak berubah) |
| `key_typed` | kunci diketik dan lolos cek bentuk. **Hanya waktu**: tidak ada isi, panjang, atau prefiks kunci |
| `key_from_file` | kunci dari `--key-file` (sudah ada, tidak berubah) |

Waktu selesai tahap sudah tercatat (`stages.<id>.ended_at`). Dengan ini, waktu yang dihabiskan manusia di terminal
untuk satu tahap = `confirmed` − `limits_shown` (membaca dan memutuskan) dan `key_typed` − `confirmed` (mengetik kunci).
Dengan `--yes`, keputusan ada di chat, jadi selisih itu bukan ukuran waktu manusia; jumlah keputusannya tetap terhitung
dari entri `confirmed_by_flag`.

Penolakan karena kunci salah bentuk, kunci kosong, atau tanpa terminal tidak mencatat `key_typed`. Isi kunci tetap tidak
pernah ditulis di mana pun (jaminan lama, tesnya diperluas ke entri baru).

`job.json` dibaca, bukan diubah, oleh `status` (tanpa kunci, seperti sekarang). Penjumlahan per pilot (jumlah keputusan,
menit terminal) **tidak** masuk PR ini. Claude menghitungnya dari log saat menulis `RESULT.md`. Bila ternyata dipakai
berulang, bisa menyusul sebagai `pilot_report.py`.

### 2.2 `REVIEW_READY`: apa yang diterapkan dan bagaimana

`status` (dan output akhir `argus approve`/`resume`, yang mencetak `status`) untuk `REVIEW_READY` mencetak:

```
review package: <dir> (valid)
  PR description: <dir>/PR.md
  patch:          <dir>/changes.patch
apply (by hand, in the target repository):
  git -C <repo> checkout -b argus/<job> <commit intake, 40 karakter>
  git -C <repo> apply --whitespace=nowarn <dir>/changes.patch
```

- Commit diambil dari `job.json` `intake.commit` (commit yang benar-benar di-intake, bukan `--commit` yang bisa berupa
  `HEAD`). Ini perintah yang sama dengan yang ditulis `review.py` di `PR.md`, hanya dengan path lengkap.
- Router **hanya mencetak**, tidak menjalankan apa pun (K6 v0 tetap: menerapkan patch dilakukan manusia).
- `REVIEW_INVALID`: tetap mencetak masalahnya (seperti sekarang) dan letak `PR.md`, **tanpa** perintah apply.

### 2.3 Alasan gagal

`status` untuk state akhir yang bukan sukses mencetak satu baris `why:` dari entri log transisi ke state itu (field
`reason`), lalu baris `next:` dengan perintah yang sah dari state itu:

| State | `why:` | Tambahan | `next:` |
|---|---|---|---|
| `DRAFT_FAILED` | `reason` transisinya (`stop_reason` drafter) | | `argus redraft <job>` / `argus reject <job> "..."`; bila masih ada draf yang diterima, juga perintah approve (sudah dicetak sekarang) |
| `AGENT_FAILED` | `reason` transisinya (`stop_reason` agen) | dari `runs/<a1>/result.json` (hanya dibaca): `status`, jumlah attempt, `verdict.failing` | `argus abandon <job> "..."` (agen tidak diulang dalam job yang sama, spek v0 §5) |
| `BLOCKED` | `reason` transisinya (mis. `budget: ...`, `contract_changed: ...`, `intake: ...`) | | `argus abandon <job> "..."` |
| `REJECTED`, `ABANDONED` | `reason` transisinya, dan `by` | | tidak ada |

- Job lama yang `result.json`-nya hilang atau rusak tetap bisa di-`status`: baris tambahannya menjadi `agent result:
  unreadable`, bukan error.
- `list` tidak berubah (tetap satu baris per job).

## 3. Yang tidak berubah

State, transisi, uang, kunci per job, approve, dan alur live tidak berubah. Tidak ada panggilan model baru. Tidak ada
perintah baru. `argus apply` (K6 v0) dan mengulang agen dalam job yang sama tetap di luar PR ini (masing-masing butuh
spek sendiri karena mengubah alur). Cek bentuk kunci DeepSeek juga ditunda (Atha: "4 nanti aja").

## 4. Tes (gagal di kode lama; mutan)

1. **Konfirmasi di terminal tercatat:** tahap live dengan `confirm` palsu yang menjawab `y` dan kunci yang diketik
   mencatat `limits_shown`, `confirmed`, `key_typed` dalam urutan itu, dengan waktu dari `clock` palsu, sebelum entri
   state tahapnya. Jawaban "N" mencatat `limits_shown` dan `not_confirmed`, tanpa `confirmed`/`key_typed`, dan tidak ada
   tahap yang dimulai.
2. **Kunci tidak tercatat:** tes kunci yang sudah ada (tidak ada di `job.json`, log, env setelah tahap) juga mencakup
   entri baru. Kunci salah bentuk atau kosong tidak mencatat `key_typed`.
3. **`--yes` tidak berubah:** `confirmed_by_flag` dan `key_from_file` tetap seperti sekarang; `confirmed` dan
   `key_typed` tidak muncul.
4. **`REVIEW_READY`:** `status` mencetak path `PR.md` dan `changes.patch` (keduanya ada di disk), dan dua baris apply
   dengan repo, `argus/<job>`, dan commit intake 40 karakter (bukan `HEAD`). `REVIEW_INVALID` mencetak `PR.md` dan tidak
   mencetak `git ... apply`.
5. **Alasan gagal:** untuk `DRAFT_FAILED`, `AGENT_FAILED` (dengan `failing` dari `result.json`), `BLOCKED` (budget dan
   `contract_changed`), `REJECTED`, dan `ABANDONED`, `status` mencetak `why:` dengan alasan dari log dan `next:` sesuai
   tabel 2.3. `AGENT_FAILED` dengan `result.json` yang hilang mencetak `unreadable` dan tidak error.
6. **`status` tetap hanya membaca:** `job.json` tidak berubah oleh `status` di semua state di atas (tes yang ada
   diperluas).

Mutan untuk setiap baris tabel di atas, lalu `verify.sh` penuh di latar belakang. Bukti di `verification/`.

## 5. Keputusan

| | Pertanyaan | Usul |
|---|---|---|
| K1 | Nama entri log | `limits_shown`, `confirmed`, `not_confirmed`, `key_typed`; dua entri `--yes` yang sudah ada tidak diganti nama |
| K2 | Penjumlahan supervisi | Tidak di PR ini; Claude menghitung dari log per pilot, `pilot_report.py` bila nanti berulang |
| K3 | Nama branch di perintah apply | `argus/<job>` |
| K4 | `next:` | Dicetak, hanya perintah yang sah dari state itu |

Juga di PR spek ini: `PENDING.md` dan baris status `SPEC_ROUTER_V0.md` diperbarui (router v0 sudah dikoding di #163,
bukan "belum dikoding").
