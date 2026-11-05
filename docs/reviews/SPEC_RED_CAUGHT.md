# Spek: gate "tes menelan traceback" menilai exception yang benar-benar ditangkap

Status: **disetujui Atha 2026-11-05** ("Ok gas bro ikut saran lu": jalur `caught` dengan jatuh ke aturan lama, R4 di PR yang sama). Jalur ketat (gate drafter, kode red check di sandbox).
Alur: spek → tes yang gagal di kode lama → kode → mutants → `/code-review medium` → `verify.sh` sekali → "merge" Atha.
Sumber masalah: `PENDING.md` ("Gate tes menelan traceback salah tolak", argus-ledger 008, submit 2 dari 3).

## 1. Masalah

`swallowed_problems` (`codetask/drafter.py`, SPEC_DRAFT_CALL_PATH 2.1, SPEC_RED_TESTS_PER_NODE 2.2) menolak tes wajib yang
gagal lewat assertion bila **pesannya menyebut nama exception lain** (`message_names`, dibaca dari kata-kata tes sendiri) dan
tidak ada satu pun berkas kode repo di traceback-nya atau rantainya. Maksudnya: tes menangkap exception, membuang
traceback-nya, dan hanya menyisakan namanya. Gate itu tidak tahu apakah ada exception yang benar-benar ditangkap, jadi ia
menolak juga tiga hal yang tidak menelan apa pun:

| Bentuk | Contoh | Ditolak sekarang? | Seharusnya |
|---|---|---|---|
| Tes **mengharapkan** exception yang kode lama tidak raise | `pytest.fail("must raise ValueError")` | ya (salah) | lolos: tidak ada yang ditelan |
| `TypeError` di titik panggilan (argumen tak dikenal) | `except TypeError as e` lalu gagal | ya (salah) | lolos: tidak ada frame repo yang bisa hilang |
| Exception diraise dan ditangkap **di dalam** kode repo | repo `try/except ValueError`, tes menulis "must raise ValueError" | ya (salah) | lolos |
| Exception repo ditangkap tes, traceback hilang | `err = e` di `except`, `pytest.fail(...)` di luarnya | ya | tetap ditolak |

Akibat di 008: satu submit terbuang, dan drafter "mengakali" dengan mengganti kata di pesan, sehingga gate mengukur
kata-kata tes, bukan perilakunya.

## 2. Bukti (tanpa model, 2026-11-05)

`docs/reviews/spec_red_caught/` (`mod.py.txt`, `cases.py.txt`, `plugin.py.txt`, `output.txt` (berkas `.txt` agar pytest tidak mengumpulkannya)): lima bentuk di atas, dijalankan
dengan plugin pytest kecil di Python 3.12.3. Plugin memakai `sys.monitoring` (`EXCEPTION_HANDLED`): saat sebuah `except`
di **kode tes** menangani exception yang traceback-nya memuat frame di kode repo, plugin mencatat nama kelasnya dan semua
kelas induknya. Hasil: bentuk 1 (`ValueError` dari repo) dan bentuk 4 (`KeyError`, pesan menyebut `LookupError`) tercatat;
bentuk 2 (tak ada exception), 3 (`TypeError` di titik panggilan) dan 5 (ditangkap di dalam repo) **tidak** tercatat.
Aturan lama menolak kelimanya; aturan baru hanya yang benar-benar ditelan.

## 3. Rancangan

**R1. Red check mencatat exception yang ditangkap (hanya pytest, Python ≥ 3.12).** Plugin `Record` (di `RED_CHECK`)
mendaftarkan callback `EXCEPTION_HANDLED` pada satu tool id `sys.monitoring` (ID 4, bukan debugger/coverage/profiler/
optimizer) selama fase `call` sebuah tes. Untuk exception yang ditangkap, ia mencatat bila ada frame traceback **lebih
dalam daripada frame penangkap** yang berkas aslinya di `/workspace` (bukan site-packages):
`{"names": [kelas dan induknya], "handler": path penangkap, "paths": [berkas frame yang lebih dalam]}`.
Callback pertama-tama menyaring dengan berkas kode (cache per berkas), jadi frame pytest dan stdlib tidak membebani.
Disimpan per tes sebagai `caught` (batas `RED_LIMITS`: 20 catatan, 20 path, 20 nama; pemotongan dicatat).

**R2. Gate memakai `caught` bila ada.** Tes wajib yang gagal lewat assertion ditolak hanya bila ada catatan `caught` dengan:
nama yang beririsan dengan `message_names`, penangkap **bukan** kode repo (`_repo_code` false: berkas tes), dan paling
sedikit satu path yang kode repo (`_repo_code`), sementara traceback tes dan rantainya tidak memuat berkas repo (syarat
lama tetap). Bila `message_names` kosong: tetap lolos seperti sekarang.

**R3. Fail-closed.** `caught` adalah `null` (bukan daftar kosong) bila `sys.monitoring` tidak ada (Python < 3.12, mis.
`sympy_py39`) atau tool id ID 4 sudah dipakai, atau callback gagal: gate memakai aturan lama (nama di pesan, tanpa berkas
repo → tolak), jadi tidak pernah lebih longgar dari sekarang di lingkungan itu. Rekaman **tanpa kunci** `caught` (rekaman lama
dan vitest) diperlakukan sama dengan `null`: aturan lama, tidak pernah lebih longgar dan hasil yang sudah tersimpan tidak berubah
saat dibaca ulang (crash-resume). `caught` yang bukan daftar, atau isinya bukan `{names, handler, paths}`, = `UNREAD`. Lebih dari
20 catatan = `null` (bukan dipotong: tes yang menangkap banyak exception tidak boleh menyembunyikan satu yang ditelan). Daftar
kosong berarti "dipantau, tidak ada yang ditangkap".

**R4. Pesan penolakan** tetap `SWALLOWED`, ditambah satu kalimat: exception mana (nama dan berkas repo-nya) yang
ditangkap, supaya drafter memperbaiki tesnya, bukan mengganti kata.

Tidak berubah: vitest (rekorder JS-nya tetap), `message_names`, `repo_paths`, aturan "tes yang sudah hijau diwajibkan",
semua jaminan AGENTS.md. Tidak ada panggilan model baru.

## 4. Yang dijamin dan dites (tes harus gagal bila jaminannya rusak; mutants)

1. Lima bentuk di §1 dengan plugin nyata di sandbox (tes docker; skip tidak dihitung lulus): bentuk 1 dan 4 ditolak,
   bentuk 2, 3 dan 5 lolos.
2. `caught = null` (Python 3.9 atau tool id terpakai) → aturan lama: bentuk 2 ditolak seperti sekarang.
3. Rekaman tanpa `caught` → aturan lama (bukan `UNREAD`); `caught` yang bukan daftar atau berisi entri rusak → `UNREAD`; lebih dari
   20 catatan → `null`.
4. Penangkap di kode repo tidak dihitung; path hanya berkas tes (helper tes) tidak dihitung.
5. Batas `RED_LIMITS` dan pemotongan; callback tidak mengubah hasil tes (sebuah tes yang lolos tetap lolos, exception
   tidak ditelan oleh callback).
6. Ukuran: waktu red check di `argus-ledger` (19 tes merah) tidak naik lebih dari 10%.

## 5. Di luar cakupan

Mengubah aturan untuk vitest; memantau exception di thread lain selain yang dilaporkan `EXCEPTION_HANDLED`; menilai
"tes menelan" di luar kegagalan assertion; menyentuh Python 3.9 (tetap aturan lama; `sympy_py39` bukan target).

## 6. Pertanyaan untuk Atha

1. Setuju gate memakai `caught` bila ada dan jatuh ke aturan lama bila tidak ada (R3), tanpa menunggu Python 3.9 yang
   tidak punya `sys.monitoring`?
2. R4 (pesan penolakan menyebut exception dan berkasnya) ikut PR yang sama, atau PR terpisah?

## 7. Implementasi (2026-11-05)

- `acceptance/validation.py` (`RED_CHECK`): tool id 4 `sys.monitoring`, callback `EXCEPTION_HANDLED` hanya selama fase `call`
  sebuah tes; `caught` per tes ({names, handler, paths}); `null` bila `sys.monitoring` tidak ada, id tidak bisa diambil,
  callback gagal (tes dengan `__name__` yang melempar error), atau lebih dari 20 catatan berbeda. `RED_LIMITS["caught"] = 20`.
  Catatan: catatan hanya dibuat bila ada frame berkas repo **lebih dalam** daripada penangkap, jadi `TypeError` di titik
  panggilan dan exception yang diraise di `<string>` tidak tercatat (bentuk 2 dan 3 di §1 jadi daftar kosong).
- `codetask/drafter.py` (`swallowed_problems`, `_caught_kept`): R2-R4. Rekaman tanpa `caught` (lama, vitest) = aturan lama.
  Pesan penolakan menambah "The test caught <nama> raised in <berkas repo>".
- Tes: `tests/test_red_caught.py` (32: 17 gerbang dari rekaman, 7 sandbox nyata, fallback id tak terambil, >20 catatan,
  callback gagal, hasil tes tidak berubah, batas); `tests/test_draft.py` diperbarui: `test_long` (hanya menyebut nama,
  tidak menangkap apa pun) dan `test_exec_frame` (`<string>`) tidak lagi ditolak, yang ditelan sungguhan (`swallowed`,
  `from None`) tetap.
- `verify.sh`: PASS 728a8b7 (2956 passed, 0 skipped; `verification/verify-20261105T043121Z-aarch64.log`). Percobaan pertama FAIL di ae5f4f0 (1 error: `test_cases.py` bukti ikut dikumpulkan pytest; log `.FAIL-doc-file-collected.log`), berkas bukti jadi `.txt`.
- Mutants 19/19 (satu selamat pertama kali, callback yang gagal tidak dicatat `null`; diperbaiki dengan tes).
- Waktu red check di `argus-ledger` 4e947a0 (137 tes lulus, `ledger_py312_up1`): 44,0 s tanpa, 46,0 s dengan (+4,5%).

### 7a. Review (`/code-review medium`, 2026-11-05, 8 temuan)

Diperbaiki:
- **Setup dan teardown ikut dipantau** (hook `pytest_runtest_protocol`, bukan hanya `call`): fixture yang menangkap exception repo
  dicatat. Tes sandbox: `test_a_catch_in_a_fixture_counts...`.
- **Traceback lebih dari 1000 frame** (rekursi dalam) = `caught: null`, bukan daftar terpotong yang menyembunyikan frame terdalam.
- **Callback didaftarkan sekali** saat mulai, bukan per tes; per tes hanya `set_events`.
- **Penjelasan menyebut kelas yang ditangkap** (mis. `KeyError`), bukan kelas dasar yang dinamai pesan (`LookupError`).

Dijawab tanpa perubahan kode:
- **`caught: []` = "dipantau, tidak ada"**: exception yang ditangkap di proses anak (subprocess) tidak terlihat dari proses
  pytest; traceback-nya biasanya ada di stderr yang masuk pesan, bukan hilang. Batas ini diterima dan dicatat di sini.
- **`with`, `finally`, `pytest.raises` ikut tercatat**: terbukti (`EXCEPTION_HANDLED` sama untuk semuanya). Hasilnya sama
  ketatnya dengan aturan nama lama untuk bentuk itu, jadi bukan kemunduran; dites (`..._with_and_finally_handlers`) agar
  perubahan di masa depan disengaja.
- **Aturan baru melonggarkan** `test_long` dan `test_exec_frame` di `tests/test_draft.py`: disengaja (§7). Pemulihan aturan lama
  saat `caught` null dites di `test_red_caught.py` (`without_caught_the_old_rule`, `a_tool_id_that_cannot_be_taken...`).
- **`inside()` di jalur panas**: sudah di-cache per nama berkas (`_real`); biaya terukur +4,5%.
- **Plugin bukti di `docs/reviews/spec_red_caught/`** adalah prototipe eksplorasi (pemisahan repo/tes dengan nama berkas); perilaku
  yang dijamin dites memakai plugin yang dikirim (`RED_CHECK`), bukan prototipe itu.
- Tool id 4 tidak dibebaskan: proses red check berakhir sesudah satu `pytest.main`; kegagalan mengambilnya = `null`
  (gate aturan lama), terlihat di rekaman (`caught: null`).
