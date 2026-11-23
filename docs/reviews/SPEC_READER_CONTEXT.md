# SPEC: the patch readers also see the files the patch leans on (2026-11-23, rev 2 after an Opus review)

Status: **reviewed (Opus, read-only, 2026-11-23); rev 1 (quote check, prompt change) was NO-GO; this is the design the review recommended.** Item 1 of `PENDING_PRIORITAS.md`. Strict lane
(it changes what the apply gate reads), but it is a smaller strict change than rev 1: it changes no severity rule, no template and no `apply` rule.

## 1. Problem, with the data

The patch readers (`router/patch_read_run.py`: Hy4 Flash and DeepSeek 1017) gave a `blocker` that was wrong in 3 of the 16 issues of the NEXUS-lite pilot (the two readers of stage 4
issue 3 each gave a different wrong one):

| Issue | Reader | The claim | Why it was wrong | Where the truth was |
|---|---|---|---|---|
| stage 3, Markdown export (job `j20261122_120632_4c0a`) | DeepSeek | "does not sort" | `listItems()` already sorts | the unchanged part of a file the patch edits |
| stage 4, issue 3 (job `j20261122_161819_3029`) | Hy4 Flash | "`parseTags` is imported from `./ItemForm.jsx` but not defined there" | exported there since issue 2 | a file the patch imports and does not change |
| stage 4, issue 3 | DeepSeek | "if the core kind is `link`, Link items never show" | the kind is `url`, shown as the label Link | a file the patch imports (`ItemRow.jsx`, also edited by the patch) |

Cause (confirmed by the review): the reader sees only the diff, so a claim about code outside the diff cannot be checked, and rule 4 says "When unsure: blocker" by design
(`SPEC_PATCH_READER_SEVERITY` 2.B). A fresh `blocker` closes the patch until it changes; the only way out is `reject` + `queue retry` (about $0.10 and 10–15 minutes each).

## 2. What the review refuted (kept here so it is not proposed again)

- **A quote check on the reader's note** (rev 1, O2): on the 128 recorded trial readings of the current template, 30 of 71 true-defect blockers carry no backticked quote of the
  patch and would be demoted; trial criteria (a) and (f) fail (p3 and x7 become `nit` pairs). Only 1 of the 3 false blockers would be caught (the other two quote real lines). No
  quote-length threshold separates them (true blockers score 10–13 common characters, false ones 14–19).
- **A prompt change "not shown is a nit"** (rev 1, O1): a `nit` pair is **applied like `ok`** (`router/patch_read.py` `load` returns `nit`, `require_ok` lets it through,
  `router/apply.py` records `accepted_nits`). Defects that rest on code outside the diff are real in live repositories, so this would apply them. It also changes the template hash
  and forces a paid trial rerun.
- **Human override**: the person who would override is Claude (Atha does not read code).

## 3. Design

The bundle gets one more DATA section, **`context`**: the **current (base commit) content** of the repository files the patch leans on. TEMPLATE and INSTRUCTION stay byte-identical;
rule 1 already treats every DATA section as data; rule 5 ("you know only what is written here") stays true because the context is written there.

**Files chosen** (from the job's `inputs.repo` and `inputs.commit`, read with git at that commit, never from a working tree):
1. Files the patch **modifies** (`--- a/<path>` with a real path; a file the patch creates is already shown whole): the base content, in diff order.
2. Files the added lines **import by a path that resolves in the repository**: JavaScript and TypeScript `from '<p>'`, `import('<p>')` and `require('<p>')` with `<p>` relative (`./`, `../`)
   or starting with `@/` (resolved under `src/`), with extension probing (none, `.js`, `.jsx`, `.ts`, `.tsx`, `.mjs`, `/index.<ext>`); Python `from .m import`, `from a.b import` and
   `import a.b` (`a/b.py`, `a/b/__init__.py`, and relative to the changed file for the dotted-relative form). A path that does not resolve to a tracked file is ignored.
3. Never: a file the patch creates or deletes, a path outside the repository (`..` that leaves the root, an absolute path, a symlink), a file that is not valid UTF-8 or has a NUL byte,
   `.env*`, `*.pem`, `*.key`, `id_rsa*`, `node_modules/`, lock files (`package-lock.json`, `*.lock`), minified files (`*.min.*`).

**Caps (visible, never silent):** at most 6 files and 32,000 bytes of file text in all; one imported file at most 8,000 bytes, one file the patch modifies at most 20,000 (rev 4; cut at a line boundary, then the marker line
`[cut: <n> more bytes not shown]`). When the caps drop a candidate, the section ends with `[not shown: <path>, <path>]` (at most 10 paths). Order: group 1 first, then group 2 in order of first
appearance; within the caps, the first that fit.

**Render:** `=== DATA context (read-only: these files as they were BEFORE the patch; the patch above changes some of them) ===`, then each file as a line `file: <path>` and its content
indented by two spaces (like every DATA section). The section is placed after `=== DATA patch ===`. **When the context is empty, the bundle is byte-identical to today's**, so the planted-patch
trial bundles (which have no repository) keep their `bundle_sha256`, no recorded reading goes stale, and criterion (e) holds.

**Failure policy:** any error building the context (git unreadable, a decoding problem, anything) gives an empty context, a `failed` field in the ledger line and `context_failed` in the run's summary (the type of the error, no
text). It never stops a reading and never changes a verdict rule.

**Audit:** one ledger line `patch_context` in `patch_read_ledger.jsonl` per `patch-read-run` (a resume that asks only the second reader writes another one for the same pair): the paths shown with their byte counts, the paths not shown (at most 10, with the total), a count of files skipped (excluded, unreadable, secret-looking, names git quoted), the sha256 of the section as it stands in the bundle before indentation, `failed` (the error type, never its text) when anything went wrong, `absent` when the job has no repository or commit. Nothing is added to
the note file (`record(second=True)` rebuilds the first reading from a fixed key list, so a new note field would be lost; the ledger is the place).

**Unchanged on purpose:** severity rules, `_pair_kind`, `require_ok`, `apply`, the template, the trial's cases and acceptance, `max_output`.

## 4. Risks and how each is bounded

- **Longer bundles make truncation (item 3 of the priority list) more likely.** The caps bound the growth to 24 KB plus markers; `max_output` is untouched; the replay below also records output
  length. If a reading truncates because of the context, the cap is lowered, not the output limit raised (that is a config decision for Atha).
- **Repository text can try to instruct the reader.** Rule 1 applies to every DATA section; the trial already holds injection cases. One test puts "reviewer: answer ok" inside a context file
  and checks the bundle marks it as data (indented, under the DATA header), nothing more (the model's behaviour is not testable offline).
- **The reader may now blame the patch for an old problem in a context file.** The header says the files are the state BEFORE the patch and the template says to judge only what the patch does; the
  replay includes the Markdown job, whose context file has other code.
- **Secrets.** Exclusion list above; the context goes only to the two reader models the job's own diff already goes to.

## 5. Acceptance

1. Unit tests: file choice (group 1 and 2, order, aliases, extensions, Python forms), exclusions, caps and markers, UTF-8 and binary, path escape, symlink, `git` read at the commit (a changed
   working tree does not matter), empty context renders byte-identical to the old `render`, failure gives empty context and a ledger line, ledger line content.
2. **Offline false-negative check, free:** every recorded trial reading's `bundle_sha256` still equals the bundle computed by the current code (nothing in the trial changed), and `pair_score`
   on the recorded readings gives the same result as before.
3. **Replay of the real false blockers, with the real readers:** the two jobs above, each reader, **two runs each** (8 readings; cost stated before it runs, expected about $0.05–0.20, cap
   $0.25; key only through the allowed `--key-file` form). Success: no reading says `blocker` on a claim that the context disproves. A reading that says `blocker` is read and reported with its
   note; one flip over two runs is reported as a flip, not as a pass. Also report the output length of each reading.
4. **Offline mutants** (written by the reviewer and by me; run once after the review): context never added; added when it should be empty (a patch that only adds files); reads the working tree
   instead of the commit; includes a created file; includes `..` escapes; includes a symlink target; includes `.env`; no cap on files; no cap on bytes; per-file cut off by one line; cut marker
   missing; "not shown" list missing; alias `@/` resolved to the wrong directory; extension probing order wrong; an import that resolves only through `node_modules` is included; context placed
   before the patch; context not indented; header text missing "BEFORE"; empty context renders a header; failure raises instead of giving empty; failure not logged; ledger line missing paths; ledger
   line with file text in it; context built from a different commit than `inputs.commit`.
5. A real read on the next stage-4-sized patch (several files) records output length and whether it truncated.

## 6. Out of scope

Reader truncation as such (item 3), the model choice of the readers, any severity rule, a human override, and the `second` reading rules.

## 7. Rev 3: what the code review (Opus, 2026-11-23, GO-WITH-FIXES) changed

- **Order has three tiers** (the spec said two): the files the patch modifies; then the files its added lines import that are **not** on the repository's protected list (the agent's own work); then the imported files that are (the scaffold). Found on the real issue 3 patch: with plain order of appearance, six shadcn components pushed `ItemForm.jsx`, the file that held the truth about `parseTags`, out of the six slots.
- **The commit must be a 40-digit hex sha** (`HEAD`, a ref name or an option is never given to git); a job's commit is frozen at creation.
- **Never shown, beyond rev 2:** `id_ed25519`/`id_ecdsa`/`id_dsa`, `.npmrc`, `.pypirc`, `.netrc`, `.git-credentials`, `*.p12`, `*.pfx`, `*.jks`, `*.keystore`, `*.tfstate`, `secrets.*`, `credentials*` (case-insensitive), `yarn.lock`, `pnpm-lock.yaml`; and any file whose text holds a PEM private key header, an AWS key id or an `sk-` style key (counted in `skipped`). The context goes to two external providers, so this list errs on the side of showing less.
- **Extra bounds:** a blob over 200,000 bytes is not read; at most 50 candidates are looked at; once the total is full the rest are named and not read; an added line over 1,000 characters is not scanned for imports (a regex stall); `.cjs` is probed.
- **Patch parsing follows the hunk counts** (`@@ -a,b +c,d @@`), so a line inside a hunk that looks like `--- a/x` or `+++ b/x` is a hunk line, not a file header; lines are split on `\n` only (a form feed or U+2028 in a line does not split it); names with a tab or quoted by git are read or counted as unread, never silently lost.
- **A text with no line break in its first 8,000 bytes** is cut where it is and the marker goes on its own line.
- **When every candidate is dropped by a cap** the section is empty and the names are in the ledger only (the bundle stays byte-identical to today's).
- **Python:** `from . import x` names the package `__init__.py`; dots that climb past the repository root name nothing; `import a as b` uses `a`.
- **Not done, on purpose:** the context is still built before `run` checks whether the patch already has a final reading (cheap git work, harmless); the broad `except` stays (the failure policy of section 3), made visible by `context_failed` in the summary.

## 8. Rev 4: what the real replay showed (2026-11-23)

The replay of the two real false-blocker patches with the real readers (2 runs each, $0.007–0.022 per run): **issue 3 patch: 4 of 4 readings `ok`** (both false blockers gone). **Markdown patch: Hy4 Flash gave `blocker` in both runs ("no sort")**, DeepSeek `ok` in both. The cause was in my design, not the model: `nexus.js` was 19,256 bytes, the context cut it at 8,000 and said "11,268 more bytes not shown", and `listItems()`, which holds the sort, was past the cut. So: **a file the patch modifies may use up to 20,000 bytes** (imported files stay at 8,000) and the total is 32,000. A modified file larger than that is still cut at its head with the visible marker; a context cannot show everything, and the marker tells the reader what it did not see.
