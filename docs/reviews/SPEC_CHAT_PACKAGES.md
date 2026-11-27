# SPEC_CHAT_PACKAGES: the foreman can propose a new npm package; Argus resolves, vets and builds the environment; a human confirms each step

Status: rev 1, 2026-11-27. Rev 0 was reviewed read-only by Opus the same day: **GO with fixes** (3 blockers, 17 fixes); rev 1 takes them all (section 12 maps them). Rev 1 needs a read-only re-review of the changed sections before S0 is built. Strict lane (it adds a networked step, a change to a safety gate and a new proposal route). Parents: `SPEC_PWA_VIEWER.md` section 3 E, `SPEC_DEP_UPGRADE_V0.md` (a new package is a new environment), `SPEC_CHAT_MANAGER_P1.md` to `_P4B.md` (the foreman, its cards, its context), `router/env_init.py` (the precedent: it never edits `config.yaml`). Atha 2026-11-27: "tulis speknya, jadikan capabilities untuk foreman dengan human in the loop", so that a package no longer needs Claude by hand.

## 1. What is true today (checked 2026-11-27, and again by the review)

- A new npm package is a new environment, done by hand: edit `package.json` and the lock, run `scripts/build_env_node.sh NAME` (its `npm ci --ignore-scripts` is the only networked step), run `scripts/check_env_image.py NAME`, then a PR that adds `environments/NAME/` and the `config.yaml` lines. Jobs never install anything (`--network none`, no shell, no npm).
- `build_env_node.sh` refuses: a base not pinned by digest, a `package.json` version that is not exact, a locked package not from `registry.npmjs.org` with a sha512 (bundled ones excepted), a lockfile that is not v3. It honours `ARGUS_ENV_DEFS` and `ARGUS_ENV_OUT`. It has no timeout of its own. It writes the pins `.sandbox_image_NAME`, `.sandbox_image_NAME.json` (with `lock_sha256`) and deletes `.check.json` (git-ignored, per checkout; `scripts/pin_status.py`). `verify_at.sh` copies every `.sandbox_image*` file.
- **`check_env_image.py` does not honour `ARGUS_ENV_DEFS`.** It reads `ROOT/environments/NAME/...` (lines 65, 122, 176) and needs `cfg["environments"][NAME]` (line 163) and a configured image (`tools/sandbox.py`, `sandbox_cfg` in `scripts/approve_draft.py`). So an environment that is not adopted yet cannot be checked today. S0 (section 11) changes this gate.
- The repo's-dependencies-are-a-subset-of-the-lock rule (E1) is enforced only at the viewer's deploy, for `pwa_node22` (`router/stage_viewer.py`). For bulking-app nothing enforces it; this spec does not rely on it.
- `check_problem` (`router/job.py`) compares only the image id, not the lock a check was run on.
- Job kinds `research`, `issue`, `prd`, `manager` have their own `LEGAL` state tables in `Job.move`; any other kind falls through to the code job's table. `.gitignore` has `jobs/` and `queues/`, not `state/`.
- This host has no `node`, `npm` or `npx`; only Docker.
- The capability sheet says a new environment is not possible from the chat. The foreman proposes only `research`, `prd`, `ask`, `none`.
- The registry's package document carries, per version, the publish time (`time[version]`), `license`, `deprecated`, `dist.unpackedSize`; the package has `time.created` and `maintainers`. Checked on `@ui-sdk/react`. `hasInstallScript` appears in the lock npm writes, only when true; not seen in the example, so reading it is a test (section 8).
- Example: `@ui-sdk/react` 0.1.0-beta.18 was published 2026-11-26 and needs `react >=19`; bulking-app is on React 18.3.1. It is a prerelease, so the parser refuses it (section 3) before any gate runs; the age gate's live proof uses another package (section 8).

## 2. What it does

1. **Propose** (foreman): a route `package` with `repo` and `text`, one line per package, `name` or `name@x.y.z`, one to five lines.
2. **Prepare and confirm 1** (human): the card shows the lines as the harness parsed them; the human may edit; the confirm starts a job of kind `env` (no model, no money).
3. **Resolve and report** (machine): in one container with network, npm computes a candidate lock; the harness reads the result and shows facts and gates.
4. **Confirm 2** (human): the card shows the report and the candidate's sha; the confirm builds the image.
5. **Build, check, ready** (machine): built and checked; the job ends `READY` with the environment's name, the image id, the check result and a printed adoption bundle. Adopting it is a pull request of its own, by a human (section 5).

## 3. The request (steps 1 and 2)

`manager_route`: `ROUTES` gains `package`; the proposal keeps its four keys. For `package`: `repo` is a registered repository whose environment has `runner: vitest` (a Python repo, or `repo: null`, is refused by `proposal_problems`, which gets its own branch), `text` 10 to 600 characters, `why` the foreman's own words, never sent to the machine. A proposal's text is a fill-in the human sees and may edit.

The harness parses the lines (`router/env_packages.py`, pure). Lines are split on `\n` after removing `\r`; each is stripped; blank lines are dropped; at most 5 remain; each must `fullmatch` `((@[a-z0-9][a-z0-9._-]{0,63}/)?[a-z0-9][a-z0-9._-]{0,63})(@([0-9]+\.[0-9]+\.[0-9]+))?` (`[0-9]`, never `\d`: Python's `\d` matches other scripts' digits). So: lower-case registry names, optional exact stable version, **no prerelease, build metadata, range, tag, URL, git, file, alias or `npm:` form**. A name appears once. A name already in the environment's lock is refused (an upgrade is not in v1). A line that does not parse is an error the human sees, never repaired.

**Name-only lines are allowed** (the foreman has no registry access and would guess a version): the harness then lets npm choose the newest stable version published before the age cutoff (`--before`, section 4), and the report shows the version it chose.

`env_new` reuses P2b (`source_job`, `source_turn`, the same checks and audit lines). `ACTIONS` gains `env_new` and `env_build`.

## 4. The job (steps 3 to 5)

A job of kind `env` in `jobs/JOB/` (not in a new `state/` directory). States: `RESOLVING`, `AWAITING_HUMAN` (the report), `BUILDING`, `READY`, `REFUSED`, `FAILED`, `ABANDONED`. `router/job.py` gets an `env` branch in `Job.move`, in resume and in status; `argus list` handles the kind; the kind stays out of the viewer's snapshot (`stage_data.py`). No model, no money.

**Argv (one fixed shape each; the package lines travel in a 0600 file, never as arguments):** `argus env add --repo R --job-id J --packages-file F --via ui --yes` and `argus env build J --sha 12HEX --via ui --yes`. The Spawner removes the file as for the foreman's files. `chat.py` does not contain the word "spawn"; execution stays in `chat_actions.py`.

**Lock and recovery.** The CLI holds an `flock` on the job directory for its whole run (the Spawner's in-memory `busy` is not enough: other processes exist). Only one `env` job is live at a time. A job left in `RESOLVING` or `BUILDING` with no live lock holder becomes `FAILED` on the next read. The container is started `--name argus-env-JOB` and removed with `docker rm -f` on timeout (killing the docker client leaves a `--rm` container running); `build_env_node.sh` runs in its own process group, killed on timeout (900 s). `env_packages.max_per_day` (config, 3) counts every `env` job of the day, refused ones included, read from `jobs/`.

**Resolve.** One `docker run --rm --name argus-env-JOB` of the environment's pinned base image: `--user` non-root, `--cap-drop ALL`, `--security-opt no-new-privileges`, `--read-only`, `--tmpfs /tmp:size=...`, `--memory`, `--pids-limit`, `--cpus` (the values from `stage_viewer`'s limits), `HOME=/tmp`, `npm_config_update_notifier=false`, `--cache /tmp/c`, `--userconfig` a harness-written `.npmrc` (registry fixed to `https://registry.npmjs.org/`, `ignore-scripts=true`, no token). The environment's `package.json` and lock are mounted read-only and **copied into `/tmp/w`** (npm writes there); one output directory is mounted writable. Names are passed as arguments to a fixed command or read by a fixed script from a JSON file, never inside an `sh -c` string. Timeout 300 s, output capped.

The command: `npm install --package-lock-only --ignore-scripts --strict-peer-deps --save-exact --no-audit --no-fund --before=<now minus min_age_days> NAME[@VERSION] ...`. `--before` makes npm pick old-enough versions for transitive packages too, so the age gate does not refuse a job for a package the human never named. Any npm error, any `ERESOLVE` line (including "overriding peer dependency" warnings, which `--strict-peer-deps` turns into errors) and a non-zero exit are a BLOCK; a lock written beside a failed run is discarded.

Then `npm view NAME@VERSION --json` for each new package (the full manifest, with `time` and `maintainers`; fields are picked from it, never from a field list that npm may unwrap). Output is data: only the regex-shaped fields below are kept. Measured in S2: 200 `npm view` calls must fit the timeout, else `max_new` is lowered. The candidate `package.json` and lock are written to `jobs/JOB/`.

**Report** (pure functions in `router/env_packages.py`). Per new package: name, version, direct or transitive, publish time (`time[version]`) and age in days, license (`^[A-Za-z0-9.()+ -]{1,60}$` or "unreadable"), `deprecated` yes or no, `hasInstallScript`, unpacked size, maintainers count. Totals: new packages, changed existing packages. The candidate lock is data and is never shown or read by an agent (section 5).

Gates, on **every** new package of the candidate, not only the named ones:
- BLOCK (`REFUSED`, nothing more is offered): `time[version]` missing (age unknown) or younger than `env_packages.min_age_days` (14; age is `now - time[version]`, never `modified`); an existing locked entry changes version, is removed, or flips `dev` or `optional`; a **new entry of an existing name at another version** (a second copy, for example a nested second React: two copies break tests); an entry whose lock `name` differs from its key (an alias); a lock key that does not match the name regex; more than `env_packages.max_new` (200) new packages; a package not from the registry or without a sha512 (the build script's own check, run first); the lock is not v3; any npm error as above.
- WARN (shown; the human decides): `deprecated`; `hasInstallScript` (the script never runs, so the package may not work); a license unreadable or not a common permissive one; a package first published less than 90 days ago (`time.created`).

**Confirm 2** names the candidate lock's sha256 (12 hex shown, the full value stored). The build step re-hashes the candidate it is about to use and refuses on any difference; it uses that verified copy and never re-reads the original.

**Name of the new environment.** The base name loses a trailing `_upN` (`bulking_node22_up1` is based on `bulking_node22`), then gets `_upN` with the smallest N not taken. "Taken" means present in any of: `environments/`, the names in `config.yaml`, the `.sandbox_image_*` pins in the checkout, and names reserved by `env` jobs that have not ended (the job record stores its reserved name at creation). The name must fit the 32-character limit of `build_env_node.sh` and `sandbox.py`. A pin is never overwritten.

**Build.** `scripts/build_env_node.sh` on a staged definition (the base file copied from the environment, the verified `package.json` and lock) with `ARGUS_ENV_OUT` pointing at the job's directory, then `check_env_image.py` with the S0 options (section 11) reading the same staged definition and the job's pins. Only after the check passes the harness moves the pins into the checkout with one rename each, so `verify_at.sh` and `pin_status` never see a half-built pin; a failed or refused build removes its own image and files. Disk: before a build, free space of Docker's root and of the host `/tmp` must be at least 3 GB (the build copies `node_modules` there); `env_packages.max_ready_images` (5) unadopted `READY` images stop new jobs until a human prunes. Do not run a build beside `verify_at`.

## 5. Where it stops, and why

`READY` is the end. The harness never edits `config.yaml`, never writes to `environments/`, never commits and never touches the repo. The job leaves an **adoption bundle**, only printed: (a) the files for `environments/NAME_upN/`, (b) the `config.yaml` lines (the environment block and the repo's `environment:` change), (c) the exact dependency lines for the repo's `package.json`. A human (Atha, or Claude) adopts it as a PR. **The adopter copies the files by sha and does not read the candidate lock** (it holds registry text: deprecation messages, funding URLs). At adoption, `check_problem` requires the adopted `environments/NAME/package-lock.json` sha256 to equal `lock_sha256` in `.sandbox_image_NAME.json` (S3), so a different lock under the same name fails the check. Until adoption nothing running changes and the old image is untouched.

This keeps Claude out of the hard part (resolving, vetting, building, checking) and in the one small, reviewed part. Automatic adoption is a later decision (Q2).

## 6. The foreman and the chat

- **Sheet and instruction.** `docs/CHAT_CAPABILITIES.md` (its "new environment is not possible" lines, 21 and 23) gets the `package` route, its limits and the line "a new environment: only by a `package` proposal and the human's two confirms; adopting it is a pull request"; `SHEET_SHA256` changes. `INSTRUCTION` enumerates the routes and says "for ask and none the repo is null": more than one sentence is rewritten, with one sentence on when to propose `package` (the user names an npm library the repo does not have). A Python repo, a non-registry source, an upgrade, or "install it now" is `none` with the reason. The foreman never sees a report.
- **Context.** `STEP_KINDS` gains `env`; `ENDED_STATE` and `step_hint` handle `READY` and `REFUSED` explicitly (today neither reads as ended): fixed sentences for `RESOLVING`, `AWAITING_HUMAN` ("The package report waits for you in the chat"), `BUILDING`, `READY` ("The environment is built and checked. Adopting it is a separate pull request; nothing changes until then"), `REFUSED`, `FAILED`.
- **Chat.** `ROUTE_ACTION` gains `package` to `env_new` (it feeds `manager_source` and `next_steps`, whose kind filter gains `env`). In `execute`, the env branches run before `key_file` is called (they take no key), as `prd_approve` does. `exposure_of` returns 0 for env cards; `job.json` is written atomically (an unreadable one makes the daily cap unknown). The proposal box shows "Prepare" for `package`; the cards and an env page (report and two buttons) follow the existing pattern (server-built text, labels, text nodes only, no `innerHTML`); epoch and double-send guards as P3. `STATIC_SHA256` is recomputed.
- **Locks to update.** `JS.count("action:")` in `tests/test_chat_ui.py` (15 to 17); its one-`href` lock (the next-steps button uses `fn`, not a link); `test_route_eval.py`'s case count; `test_chat_manager*.py` route lists; the P1 rule "one fixed argv" gets a second amendment (section 4 defines two more shapes, for `env` only).
- **Audit.** `env_prepare`, `env_confirm`, `env_build_confirm` lines with the repo, the parsed lines, `source_job`, `source_turn`, the candidate sha; `why` is never written to a card.
- **Measurement.** `route_eval_v0` gets `package` cases (positive: a named npm library for a Node repo; negative: a Python repo, a git URL, "install now", an upgrade, an injected instruction in pasted text). The existing cases c04 (Dexie vs idb) and c06 (a chart library) name npm libraries and may now route to `package`: re-measure them, report the pass rate, assume nothing.

## 7. Threats and the rule that answers each

| Threat | Rule |
|---|---|
| A prompt-injected foreman proposes a malicious package | The human sees names, versions and facts; `why` never reaches the machine; a typosquat is not proven away: the report shows age, first-publish date, license and maintainers count as facts, and the human decides. |
| A spec that is not a registry version | The strict parser (section 3) and the build script's registry and sha512 check. |
| An install script runs | `--ignore-scripts` in resolve and build; `hasInstallScript` is a WARN. |
| Registry text as an injection | Only regex-shaped fields kept; no description or readme; the candidate lock is never read by an agent. |
| A fresh malicious release as a transitive | `--before` and the age gate on every new package. |
| A package's code runs at test time | The same residual risk as every package today: it runs in the sandbox (no network, read-only). Stated, not removed. |
| The network step is abused | One fixed registry, a non-root read-only container with dropped capabilities and resource limits, a timeout, an output cap; the host runs no npm. Limiting egress to the registry alone is a later item (Q5). |
| A candidate changes between report and build | The confirm carries the sha; the build re-hashes and uses the verified copy. |
| Two jobs take one name and overwrite pins | Section 4: the name rule, reservation, no overwrite. |
| A crash leaves a job half done | `flock`, container name and `docker rm -f`, process-group kill, `FAILED` on a dead holder. |
| Disk or time exhaustion | One live job, `max_per_day`, `max_ready_images`, timeouts, a free-disk check of Docker's root and `/tmp`. |
| A different lock adopted under a built name | The sha check at adoption (section 5). |
| The wrong environment is used silently | Nothing is adopted without a PR; pins are per name. |

## 8. Tests and mutants (written, run once after the re-review)

Tests, new files: `tests/test_env_packages.py` (the parser's refusals each, including `[0-9]` vs other-script digits, CRLF, blank lines, a sixth line, a repeated name, a name already locked; each BLOCK and WARN gate; the report shape; hostile registry output of oversize, newline, control characters and a duplicate key; nested duplicate, removed entry, alias, bad key, flag flips), `tests/test_env_packages_run.py` (the resolve and build against a fake container runner: the exact argv, the names passed as arguments, `--strict-peer-deps`, `--before`, the container name and the kill on timeout, the sha re-check on the verified copy, the name rule against all four sources and the 32-character limit, the pin moves, the disk and image-count refusals, `FAILED` on a dead lock holder), `tests/test_check_env_image_defs.py` (S0), `tests/test_chat_env.py` (prepare and confirm, source checks, audit lines, a stale confirm, one live job, the daily count, `env_build` refused unless the job is `AWAITING_HUMAN`, of kind `env`, created via ui), `tests/test_chat_env_ui.py` (JS facts, a vm smoke test), the `route_eval` cases.

Live proof before merge: a real resolve, report, build and check on a copy of `bulking_node22` with one small stable package at least two weeks old; the age gate refusing a stable package younger than 14 days (chosen on the day from the registry); a `package.json` or name-only line resolved through `--before`; `hasInstallScript` read on a package that has one; the prerelease `@ui-sdk/react` refused by the parser; `npm view` output parsed for a single-field case.

Mutants (`verification/chat_env_mutants.py`, written, run once): parser: `\d` for `[0-9]`; `match` for `fullmatch`; upper case or a trailing newline accepted; a sixth line; a repeated name; a locked name treated as new. Argv: names through `sh -c`; `--strict-peer-deps`, `--before` or `--save-exact` dropped; the `.npmrc` registry changed; a container flag, the tmpfs size, `--memory`, `--pids-limit` or the container name dropped; no kill on timeout. Facts and gates: a missing `time[version]` treated as old; age from `modified`; the gate on named packages only; a nested duplicate, a removed entry, an alias, a bad lock key or a flag flip passing; lockfile v3 unchecked; an `ERESOLVE overriding` warning ignored; a non-zero npm exit with a lock accepted; an output-cap overflow treated as success; a license with a newline kept. Sha and naming: the sha compared on 12 hex only; the original re-read after the check; the definition taken from `environments/BASE`; N computed from `environments/` only; a pin overwritten; a name over 32 characters accepted. Check: the config overlay leaking into other environments; a record written on FAIL; `locked()` reading the base lock; pins moved before the check passes. Concurrency: an in-memory lock only; a stale lock never released; `RESOLVING` left forever; refused jobs not counted per day. Chat: `env_new` adding exposure or needing a key; `env_build` accepted in the wrong state, kind or origin; report fields reaching `steps_context`; `READY` or `REFUSED` read as still going; `next_steps` dropping `env`; `proposal_problems` accepting a Python repo, a null repo or 601 characters. Adoption and viewer: the bundle containing the lock's free text; the harness writing into `environments/` or `config.yaml`; an adopted lock with another sha passing; an `env` job in the viewer snapshot.

## 9. Not in this spec

Automatic adoption; upgrading an existing package (React 18 to 19 is one: it changes locked packages, so it is a BLOCK and stays with Claude); Python packages; packages from git or a URL; removing a package; any model reading a package's docs; any money; limiting the container's egress to the registry alone.

## 10. Questions for Atha (the review's recommendations in brackets)

- **Q1.** Age rule 14 days, no override in v1? [keep; `--before` handles transitives]
- **Q2.** Stop at `READY` with a printed bundle and the lock-sha check at adoption, or later a third confirm that adopts? [stop at `READY`]
- **Q3.** v1 refuses any change to an existing locked package? [yes; upgrades are a later slice]
- **Q4.** `max_new` 200 (only after the resolve time is measured), `max_per_day` 3, `max_ready_images` 5? [yes]
- **Q5.** Accept the fixed registry for v1 (no package code runs with lock-only and `--ignore-scripts`), and a later item for a dedicated Docker network that drops the metadata address and private ranges? [accept]

## 11. Build order

Each slice is a strict-lane PR with its own live proof. **S0** `check_env_image.py`: options `--defs DIR` (definitions root instead of `ROOT/environments`), `--runner vitest` (an in-memory config overlay for that run only, never written), `--out DIR` (where the pins are read), and `locked()` reading the staged lock; it changes the safety gate, so it has its own tests and mutants. **S1** `router/env_packages.py` (pure: parser, report, gates, the name rule). **S2** `argus env add`, the `env` job kind in `job.py`, the resolve runner, the lock and recovery. **S3** `argus env build`, the build and check wrapper, the pin moves, the `READY` bundle and the lock-sha check at adoption. **S4** the chat actions, cards and page. **S5** the foreman route, sheet, instruction, context kinds and `route_eval` cases. The live end-to-end proof closes it.

## 12. What the review changed (rev 0 to rev 1)

B1: S0 and the staged check (sections 4, 11). B2: the name rule and reservation (section 4). B3: `--strict-peer-deps` and every `ERESOLVE` line a BLOCK. Fixes: 1 E1 corrected (section 1); 2 prereleases refused on purpose, the live proof changed; 3 resolve copies into `/tmp/w`, `HOME`, cache, userconfig, resource limits; 4 no shell string; 5 `[0-9]` and line splitting; 6 `npm view NAME@VER --json`, missing time a BLOCK, age from `time[version]`, 90 days from `time.created`; 7 maintainers count in the report; 8 `--before` and the gate on every new package; 9 nested duplicates, removed entries, aliases, bad keys and flag flips; 10 the candidate lock never read, adopter copies by sha; 11 the sha check at adoption; 12 `jobs/JOB/` instead of `state/`; 13 the `env` kind in `job.py`, `argus list`, the viewer; 14 `flock`, recovery, container name and kill, process group; 15 the argvs defined; 16 disk of Docker's root and `/tmp`, retention; 17 name-only lines. Integration items are in section 6.
