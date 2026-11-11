# Pilot: replay n = 3 dengan gerbang amandemen 4 (Haiku 5.5, V4.1 Flash 1017)

**"Go live" Atha 2026-11-11 ("Ok merge dan go live replay 3x setelah verify lolos")**, sesudah #417 merge (`45ebe87`).
Pertanyaan: dengan harness yang menyodorkan baris tes lama (`touches` + `clash_check`), apakah Haiku kini menemukan clash
sebanyak 1017 (target 6 pada p4 w2) dan tetap menandai data API yang belum pasti?

**Replay.** Sama dengan `pilots/issue_writer_models_v0` (w1.txt, w2.txt persis, repo `~/exp-viewer-f68` di `f68bc4c`,
`--jobs-dir ~/wt-exp/jobs-exp`), Argus dari `~/wt-exp` di `45ebe87` dengan config lokal tidak di-commit: repo
`viewer-f68`, role `issue_writer` per model tanpa param thinking; Haiku `max_input_tokens` 40000, 1017 150000.
3 job per model, masing-masing w1 lalu w2, berurutan (6 job, 12 giliran). Batas per giliran $0,10, per job $0,50;
perkiraan total ≈ $0,06-0,10. Tidak ada job code yang dimulai.

| model | job |
|---|---|
| `openrouter:anthropic/claude-haiku-5.5` | `j20261111_030001_a401`, `_030002_a402`, `_030003_a403` |
| `openrouter:deepseek/deepseek-v4.1-flash-1017` | `j20261111_030011_b401`, `_030012_b402`, `_030013_b403` |

Perintah per job: `argus.py --jobs-dir jobs-exp issue new --repo viewer-f68 --job-id <job> --message-file w1.txt
--key-file openrouter=~/.config/argus/openrouter_key --yes`, lalu `issue reply ... --message-file w2.txt -- <job>`.

**Nilai per giliran w2 (Claude):** A) menandai `started_at`/`ended_at` belum pasti dari API; B) clash nyata ditemukan dari
6 (timeline 183/216/243, share 132/157/224); C) `touches` yang dipakai, penolakan `clash_check` muncul, submit ditolak;
D) detik, panggilan, USD. Berhenti pada penyimpangan pertama (error harness, biaya giliran > $0,10). Hasil di `RESULT.md`.
Keputusan default (PR B) tetap Atha.
