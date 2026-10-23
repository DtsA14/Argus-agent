# Spec W2a: merah harus benar-benar karena assertion

Status: **spec, belum dikoding.** 2026-10-23. Ditulis Claude setelah pilot W2b-3 (`pilots/m6_w2b/w2b3/RESULT.md`).
**Keputusan yang diminta: bagian 5.**

## 1. Masalah

W2a berjanji bahwa node wajib dari tes baru (dan, sejak W2a-ext, dari tes yang diubah) **merah karena assertion** di
baseline. Yang dicek sekarang hanya status pytest: `FAIL` diterima, `ERROR` ditolak. Masalahnya, pytest melaporkan
pengecualian **apa pun** di dalam tubuh tes sebagai `FAILED`. Di W2b-3, dua tes draf gagal karena `KeyError: 'f6a'`
(tesnya memakai run sintetis yang tidak dibuat oleh fixture-nya). Tes itu tetap gagal apa pun patch-nya, tapi lolos
baseline. Akibatnya kriteria task mustahil dipenuhi: agen gagal dan $0,02 terbuang.

## 2. Aturan baru

Untuk setiap node wajib di file baru atau file yang diubah, yang di baseline berstatus `FAIL`, harness membaca
**baris `E   ` pertama** dari bagian traceback node itu (`--tb=short`, yang memang sudah selalu dipakai). Node itu
diterima sebagai merah hanya bila baris tersebut diawali salah satu dari:
- `assert ` (assert yang ditulis ulang pytest, misalnya `E   assert -4 == 0`);
- `AssertionError` (dengan atau tanpa pesan, termasuk perbandingan list atau dict);
- `Failed:` (`pytest.raises` dengan `DID NOT RAISE`, atau `pytest.fail(...)`).

Selain itu (`KeyError`, `TypeError`, `ImportError` di dalam tes, `AttributeError`, dan seterusnya), draf ditolak:
`new test <node> fails with "<baris E>", not by an assertion: it would fail whatever the fix is`.

Cara membaca bagian traceback, dicek pada pytest 9.1.1 di VM:
```
________________________________ TestC.test_m _________________________________
tests/test_a.py:29: in test_m
E   AssertionError: assert [1] == [2]
```
Header `TestC.test_m` atau `test_param[1]` dicocokkan ke node id (`path::TestC::test_m`) **bersama** path di baris
frame pertama (`tests/test_a.py:29: in ...`). Jadi nama yang sama di dua file tetap dibedakan. Node wajib yang `FAIL`
tetapi bagiannya tidak ditemukan atau tidak terbaca (misalnya output terpotong) juga ditolak. Fail closed.

## 3. Di mana

- `acceptance/validation.py`: `parse_pytest` mengumpulkan `failure_lines` {node: baris E pertama, maks 200 karakter}
  untuk node `FAIL`, dan `judge_result` memasukkannya ke evidence (maks 50 node, sama seperti `failed_nodes`). Ini data
  saja, tidak mengubah verdict acceptance.
- `acceptance/draft.py` `baseline_problems`: aturan di atas, untuk node wajib di `red_paths`.
- `codetask/drafter.py`: penolakan seperti ini diberi petunjuk: "buat tes gagal lewat assert: `d.get(k)` dibanding
  `d[k]`, `assert hasattr(...)` sebelum dipanggil, buat sendiri data yang dipakai tes".

## 4. Tes (gagal di kode lama; mutan)

1. Sandbox: tes baru wajib yang gagal karena `KeyError` di tubuhnya ditolak, dan nama node serta `KeyError` disebut.
2. Sandbox: `assert`, `AssertionError("msg")`, `pytest.raises` tanpa raise, `pytest.fail`, metode kelas, dan varian
   parametrize semuanya tetap diterima. Draf yang sekarang lolos tetap lolos.
3. Tanpa sandbox: `parse_pytest` memetakan header dan path ke node id, termasuk dua file dengan nama tes yang sama;
   bagian yang hilang berarti tidak terbaca.
4. Drafter (fake): petunjuknya sampai ke model.
5. Pilot W2b-3 dari draf yang sama: sekarang ditolak di baseline.

## 5. Keputusan

| | Pertanyaan | Usul |
|---|---|---|
| K1 | Apa yang dihitung "karena assertion" | `assert `, `AssertionError`, `Failed:` (raises, fail) |
| K2 | Bagian traceback tidak terbaca | Tolak (fail closed) |
| K3 | Cakupan | Hanya baseline W2a (node wajib file baru dan file yang diubah); acceptance agen tidak berubah |
| K4 | Setelahnya | Ulangi W2b-3 dengan job baru, issue yang sama |
