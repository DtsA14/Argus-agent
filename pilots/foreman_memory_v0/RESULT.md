# foreman_memory_v0: does the foreman remember after the compaction? (2026-11-28)

`run.py`, through `argus manager turn` (the production path) with the manager's model (DeepSeek V4.1 Flash 1017; Morph first since 2026-11-28). A synthetic 30 turn conversation (about 117,000 characters, over `context_chars` 80,000) with 6 planted facts (a repository, a number, a name, a decision, a constraint, an open question) and filler is written into a session by code. Per round one turn runs on it (in the new arm that turn compacts), then 6 recall questions and 1 control question (an unplanted fact: the answer should admit it does not know) each run on a fresh copy of that session. Scored by code: a few accepted regular expressions per fact. 3 rounds per arm.

| arm | recall (6 facts x 3 rounds) | control (does not invent) | spent |
|---|---|---|---|
| new: compaction (this change) | **18 / 18** | 3 / 3 | $0.0150 |
| old: the 4 KB cut (main before this change) | 3 / 18 | 3 / 3 | $0.0062 |

- In the old arm the only fact it kept is the repository name (3 / 3), which is also in the list of registered repositories in the system prompt, so it can be guessed; every other fact was lost, and the foreman said, with confidence, that no such thing had been agreed ("belum pernah menyepakati angka buffer apa pun").
- The summary of round 1 covers the first 48 conversation entries, is 821 characters, keeps all six facts, and says that the filler turns held no decisions. The compaction call cost $0.0051; a reply on the compacted context $0.0015.
- Not shown: real conversations (these are synthetic and the facts are stated plainly, once), facts that change during the conversation, a compaction of a compaction (a second summary), an injection planted in the older turns, languages other than Indonesian, and a model other than the manager's. The recall test is a floor for plain facts, not proof that nothing is lost.
