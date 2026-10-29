# Spek: stage riset `r1` di router (Alur A → B, pilot pertama)

Status: **draf untuk keputusan Atha**, 2026-10-29. Jalur ketat: stage baru yang memanggil model dan membuka jaringan
(ReadDocs), dengan ledger dan crash-resume. Berlaku penuh AGENTS.md: spek → tes yang gagal di kode lama → kode → mutants →
`/code-review medium` + `/security-review` → `verify.sh` sekali di commit final → "merge" Atha.

## 1. Kenapa, dan kenapa kecil

Task Atha "Documentation-Guided Dependency Fix": Alur A meneliti dokumentasi resmi tanpa mengubah kode lalu menyerahkan
temuan (Problem, Relevant API behavior, URL + kutipan, Recommended change, Uncertainties); Alur B memakai temuan itu untuk
fix + tes regresi. Kalau bukti kurang: berhenti dan lapor, jangan mengarang.

Bukti kebutuhan masih tipis: di pilot K7 (`--web`) agen tidak pernah memanggil ReadDocs. Karena itu stage ini dibuat
sekecil mungkin dan langsung diuji dua lengan pada satu bug yang jawabannya hanya ada di dokumentasi (§7).

## 2. Kandidat bug (issue 013, argus-ledger)

Direproduksi 2026-10-29 di `ledger_py312` (Starlette 1.8.0, FastAPI 0.143.0), tanpa model: dengan
`create_app(d, allowed_hosts=["www.dashboard.example"])`, request dengan `Host: dashboard.example` dijawab **307** ke
`http://www.dashboard.example/jobs`, padahal README dan docstring `create_app` menjanjikan **400** untuk host di luar
daftar. Host lain tetap 400; tes yang ada hanya menguji `evil.example`.

Issue 013 hanya menulis **gejala** dan janji README. Nama parameter Starlette dan perbaikannya tidak disebut. Agen tidak
bisa membaca `site-packages` (root tool = snapshot repo), jadi dokumentasi adalah satu-satunya sumber bukti.

## 3. Alur job

```
argus code --research ...   NEW → RESEARCHING (r1) → AWAITING_RESEARCH_REVIEW
                                                    → RESEARCH_INCONCLUSIVE   (verdict INSUFFICIENT_EVIDENCE: selesai, bukan gagal)
                                                    → RESEARCH_FAILED         (gate tidak lolos, budget, model gagal)
argus research-ok <job> <sha>   → d1 (drafter) dengan handoff → AWAITING_APPROVAL → approve → agen   (seperti sekarang)
```

- `--research` = izin jaringan untuk r1 (ReadDocs), diberikan manusia saat `argus code`, ditampilkan di layar konfirmasi
  seperti `approve --web`. Hanya untuk environment di `web.environments` (aturan SPEC_WEB_TOOLS 3); job tanpa
  `--environment` yang termasuk daftar itu ditolak sebelum dibuat.
- **Gate manusia di antara A dan B:** `research-ok` terikat pada sha `handoff.json` yang ditampilkan `status` (aturan sama
  dengan approve draft: minimal 12 karakter, berubah sesudah ditampilkan → ditolak). Di jalur fast lane argus-ledger,
  Claude yang menjalankan `research-ok` sesudah meninjau handoff (seperti approve draft); "go live" Atha tetap per job.
- Drafter dan agen menerima handoff sebagai bagian issue: `issue + "\n\nReviewed research handoff (r1):\n" + render`
  (bila issue + handoff melebihi `MAX_ISSUE`, `research-ok` ditolak; tidak pernah dipotong diam-diam). Agen tidak otomatis dapat ReadDocs;
  `approve --web` tetap keputusan terpisah.
- `abandon`, `reject`, `status`, `resume` bekerja untuk r1 seperti untuk d1. `status` menampilkan handoff (render penuh) dan
  hasil gate.

## 4. Stage r1

**Tool:** `ListFiles`, `SearchFiles`, `ReadFile` pada `<run>/source` (snapshot intake, read-only, sama dengan drafter),
`ReadDocs` (allowlist dan limit `web` yang sama, budget per run), dan `SubmitHandoff`. **Tidak ada** Write, Edit,
RunValidation, atau tool lain: "jangan mengubah kode" dipaksa toolbox, bukan prompt. Sesudah stage, `<run>/source` dicek
tidak berubah (seperti drafter).

**Fakta versi dari harness, bukan dari model:** prompt memuat daftar paket terpasang dari `requirements.txt` environment
job (`environments/<env>/requirements.txt`, `nama==versi`, tanpa hash), ditandai sebagai fakta harness.

**`SubmitHandoff` (satu-satunya tool call di balasannya):**

```
verdict: SUPPORTED | INSUFFICIENT_EVIDENCE
problem: str (≤ 2000)
api_behavior: str (≤ 3000)
dependency: {package, version}
sources: [{url, quote}]   1..5, quote 20..600 karakter
recommended_change: str (≤ 3000)   (kosong boleh hanya untuk INSUFFICIENT_EVIDENCE)
uncertainties: [str]      ≥ 1 untuk INSUFFICIENT_EVIDENCE
```

**Gate harness (semua harus lolos; masalahnya dikembalikan ke model, maksimal `research.max_submits` = 3 submit):**

1. G1 URL: setiap `sources[].url` adalah halaman yang **berhasil diambil ReadDocs di run ini** (ada di
   `<run>/web/pages/`, `ok: true`). URL yang hanya disebut model ditolak.
2. G2 kutipan: setiap `quote`, sesudah normalisasi spasi (semua whitespace → satu spasi, strip) dan tanpa normalisasi lain,
   adalah substring teks halaman yang tersimpan untuk URL itu. Bukan fuzzy match.
3. G3 versi: `dependency.package` dan `version` cocok persis dengan satu baris daftar terpasang (nama dinormalisasi PEP 503).
4. G4 bentuk: batas panjang di atas; `SUPPORTED` butuh ≥ 1 sumber dan `recommended_change` tidak kosong.
5. G5 `INSUFFICIENT_EVIDENCE` tetap butuh G1–G3 untuk sumber yang disebutnya (boleh 0 sumber), dan ≥ 1 uncertainty.

Gate tidak menilai apakah kesimpulannya benar; itu tugas peninjau di `research-ok`. Gate menjamin: setiap URL benar-benar
dibaca, setiap kutipan benar-benar ada di sana, versi adalah versi terpasang. Batas klaim: kutipan bisa benar tapi diambil
dari halaman versi lain (banyak dokumentasi hanya "latest"); model wajib menulisnya di uncertainties, peninjau mengecek.

**Output:** `handoff.json` (argumen tervalidasi + `gate` per sumber: url, fetched_at, sha256 halaman), `HANDOFF.md`
(render untuk Atha/Claude), event `research_end`.

**Jaminan yang sama dengan drafter:** semua panggilan lewat `LLMCaller` dalam reservasi dari ledger (cap stage
`router.research_max_usd`, usul **$0,30**; attempt $0,25), setiap balasan dan hasil tool di-commit ke memo sebelum loop
lanjut, `SubmitHandoff` yang sudah di-commit tidak dinilai ulang, checkpoint `durability="sync"`, crash-resume lewat
`argus resume`. Batas langkah `research.max_steps` = 20.

**Implementasi:** modul baru `codetask/research.py` dengan loop sendiri yang mengikuti pola `make_drafting` (memo key,
commit, crash point, final-steps note), bukan mengubah loop drafter. Toolbox dan `DocsReader` dipakai apa adanya.

## 5. Tes (masing-masing gagal kalau jaminannya dirusak; mutants)

1. Toolbox r1 tidak menawarkan dan menolak WriteFile/EditFile/RunValidation; `<run>/source` berubah → stage gagal.
2. G1: URL yang tidak diambil, diambil tapi refusal, atau beda satu karakter → ditolak.
3. G2: kutipan yang ada (dengan whitespace berbeda) lolos; kutipan yang diubah satu kata, digabung dari dua tempat, atau
   dari halaman lain → ditolak.
4. G3: versi lain, paket tidak terpasang → ditolak; `Starlette` vs `starlette` lolos.
5. INSUFFICIENT_EVIDENCE → RESEARCH_INCONCLUSIVE, tidak ada d1, tidak ada uang lagi keluar.
6. `research-ok` dengan sha salah / handoff berubah sesudah ditampilkan → ditolak; yang benar → d1 menerima handoff di issue.
7. Tanpa `--research`: ReadDocs tidak ada; `--research` untuk environment di luar `web.environments` → ditolak sebelum job
   dibuat; layar konfirmasi memuat baris izin jaringan.
8. Crash-resume: crash sesudah balasan dan sesudah SubmitHandoff → resume tidak membeli ulang dan tidak mengambil halaman lagi.
9. Ledger: biaya r1 masuk `spent` job dan `status`.

## 6. Yang tidak diubah

Drafter, agen, approve, grader, ReadDocs (allowlist, SSRF, limit), sandbox (tetap `--network none`). Router dengan model
(memilih A/B otomatis) tetap ditunda.

## 7. Pilot sesudah merge (butuh "go live")

Issue 013, dua job, keduanya off-peak:
- **A:** `argus code --research` → handoff → `research-ok` → draft → approve (tanpa `--web`) → agen.
- **B:** `argus code` biasa (tanpa riset, tanpa web).

Diukur: handoff lolos gate dan benar (Claude cek terhadap source Starlette terpasang **sesudah** handoff dikirim, bukan
sebelum); kedua lengan DONE atau tidak; fix benar (host non-www → 400); biaya dan jumlah keputusan. Kalau B sama baiknya
dengan biaya lebih rendah, itu temuan: riset belum perlu untuk bug kelas ini (seperti K7).

## 8. Pertanyaan untuk Atha

1. Gate manusia antara A dan B (`research-ok`) — usul: **ya**, sesuai "hasil research dan implementasi dapat ditinjau
   terpisah". Alternatif: A langsung lanjut ke drafter bila gate lolos (lebih cepat, satu keputusan lebih sedikit).
2. Cap r1 **$0,30** per stage (drafter $0,75; riset biasanya ≤ 10 langkah baca). Setuju?
3. Pilot dua lengan (A dengan riset, B tanpa) pada issue 013 sesudah merge?
