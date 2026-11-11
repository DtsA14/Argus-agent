# Pilot: model penulis issue lewat OpenRouter (Haiku 5.5, GPT-6 Luna, V4.1 Flash 1017)

**"Go live" Atha 2026-11-10 ("go live untuk eksperimen replay"), sesudah #415 merge.** Pertanyaan: model mana termurah
yang (1) menandai bahwa data API belum pasti dan (2) menulis issue yang konsisten soal bentrok, pada percakapan nyata p4.

**Replay.** Percakapan job j20261110_165623_7672 (p4), dua giliran per model, pesan Atha persis:
- w1: "Di halaman job, bagian stage apa aja yang ditampilkan sekarang? Jelasin singkat, belum usah bikin issue."
- w2: "Oke, tambahin durasi tiap stage di halaman job, misalnya \"2m 14s\", dari started_at sampai ended_at."

Repo argus-viewer dibekukan di `f68bc4c` (sebelum durasi stage, sama dengan p4) lewat worktree terpisah
`~/exp-viewer-f68` (detached; repo argus-viewer tidak berubah). Argus dijalankan dari worktree `~/wt-exp` di `main`
(sesudah #415) dengan `config.yaml` lokal yang tidak di-commit: `issue_writer.repos` + `viewer-f68`, role `issue_writer`
diganti per model (tanpa `params` thinking DeepSeek), `--jobs-dir ~/wt-exp/jobs-exp` (bukan jobs live). Haiku:
`issue_writer.turn.max_input_tokens` 40000 (batas gateway #415); yang lain 150000. Batas per giliran $0,10, per job $0,50
(seperti biasa); perkiraan total ≈ $0,10.

| # | model (role issue_writer) | perintah |
|---|---|---|
| 1 | `openrouter:deepseek/deepseek-v4.1-flash-1017` | `argus issue new --repo viewer-f68 --message-file w1.txt` lalu `argus issue reply --message-file w2.txt -- <job>` (`--key-file openrouter=... --yes`) |
| 2 | `openrouter:openai/gpt-6-luna` | sama |
| 3 | `openrouter:anthropic/claude-haiku-5.5` | sama, max_input 40000 |

Pembanding: p4 deepseek-flash langsung (w1 7,9 dtk/4 panggilan/$0,0012; w2 49,7 dtk/14/$0,0079; 5 clash; issue
mengklaim "existing tests keep passing unchanged"; menulis "the api now carries started_at" tanpa cek).

**Nilai (Claude, dari issue dan balasan, sebelum melihat model lain):** A) menandai bahwa `started_at`/`ended_at` belum
pasti dikirim API (ya/tidak); B) clash ditemukan (berapa, nyata?); C) issue konsisten (gerbang #413 berlaku: klaim ditolak,
daftar ditulis harness) dan jumlah submit ditolak; D) detik, panggilan, USD (ledger), dan apakah Haiku kena batas 40k.
Pemenang: termurah yang lulus A dan B. Hasil di `RESULT.md`; tidak ada job code yang dimulai.
