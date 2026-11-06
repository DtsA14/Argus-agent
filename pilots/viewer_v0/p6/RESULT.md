# Pilot viewer v0 #6: hasil

**Berhenti di langkah 1 (penyimpangan); live tidak berubah: rilis 020 `j20261106_085425_46a7-0b02b87bad84`.**

| # | hasil |
|---|---|
| 0 | sesuai: live rilis 020, container ledger `f81794a9979b` |
| 1 | **ditolak**, exit 2: `refused: job j20261106_151840_e81c was applied with changes that differ from the reviewed patch (as_is False); only the reviewed patch is deployed` |
| 2-5 | tidak dijalankan |

Sebab: kesalahan Claude. `argus applied` mencatat commit `ab4376154948`, commit tes fresh-load yang ditambahkan Claude di
atas commit patch `518b34f`. `applied` membandingkan diff commit itu sendiri (git patch-id) dengan patch review: diff
`ab43761` hanya berisi berkas tes (`00119a583342`), diff `518b34f` sama dengan patch (`546ca35ced69` keduanya). Penjaga
`viewer-deploy` (router/stage.py) bekerja sesuai rancangan. Job sudah `APPLIED`, jadi `applied` tidak bisa diulang dengan
commit yang benar; jalan keluarnya keputusan Atha.
