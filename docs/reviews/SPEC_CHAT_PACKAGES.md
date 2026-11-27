# SPEC_CHAT_PACKAGES: the foreman can propose a new npm package; Argus resolves, vets and builds the environment; a human confirms each step

Status: rev 0, 2026-11-27 (not reviewed yet). Strict lane (it adds a networked step and a new proposal route). Parents: `SPEC_PWA_VIEWER.md` section 3 E and E1 (the environment recipe; the repo's dependencies are a subset of the lock), `SPEC_DEP_UPGRADE_V0.md` (a new package is a new environment), `SPEC_CHAT_MANAGER_P1.md` to `_P4B.md` (the foreman, its cards and its context), `router/env_init.py` (the precedent: it never edits `config.yaml`). Atha 2026-11-27: "tulis speknya, jadikan capabilities untuk foreman dengan human in the loop", so that a package no longer needs Claude by hand.

## 1. What is true today (checked 2026-11-27)

- A new npm package is a new environment, done by hand: edit `package.json` and the lock, run `scripts/build_env_node.sh NAME` (its `npm ci --ignore-scripts` is the only networked step), run `scripts/check_env_image.py NAME`, then a PR that adds `environments/NAME/` and the `config.yaml` lines. Jobs never install anything (the sandbox has `--network none`, no shell, no npm).
- `build_env_node.sh` already refuses: a base not pinned by digest, a `package.json` version that is not exact, a locked package that is not from `registry.npmjs.org` with a sha512 (bundled packages excepted), a lockfile that is not v3. It honours `ARGUS_ENV_DEFS` and `ARGUS_ENV_OUT` (the tests use them). The pins are `.sandbox_image_NAME`, `.sandbox_image_NAME.json` and `.sandbox_image_NAME.check.json`, git-ignored, per checkout (`scripts/pin_status.py`).
- E1: a repo's `package.json` must be an exact subset of its environment's lock, or intake refuses the job.
- This host has no `node`, `npm` or `npx`; only Docker.
- The capability sheet tells the foreman "creating a new environment is not possible from the chat". The foreman proposes only `research`, `prd`, `ask`, `none`.
- The npm registry's package document carries, per version, the publish time (`time[version]`), `license`, `deprecated`, `dist.unpackedSize` and the package's `maintainers`. Checked on `@ui-sdk/react`. The lock npm writes marks a package with an install script (`hasInstallScript: true`): not seen in the example, so it is a test to write (section 8), not a fact.
- Example that this spec is built around: `@ui-sdk/react` 0.1.0-beta.18 was published 2026-11-26 (one day old) and needs `react >=19`; bulking-app is on React 18.3.1. Both rules below refuse it, which is the right answer.

## 2. What it does

Five steps, three of them a human's tap, none of them a model's decision:

1. **Propose** (foreman): a new route `package` with `repo` and `text`, one `name@version` per line (one to five lines).
2. **Prepare and confirm 1** (human): the card shows the lines as the harness parsed them; the human may edit; the confirm starts a job of kind `env` (no model, no money).
3. **Resolve and report** (machine): in one container with network, npm computes the candidate lock; the harness reads the result and shows the facts and the gates.
4. **Confirm 2** (human): the card shows the report and the candidate's sha; the confirm builds the image.
5. **Build, check, ready** (machine): the image is built and checked; the job ends `READY` with the environment's name, the image id, the check result and a printed adoption bundle. Adopting it is a pull request of its own, by a human (section 5).

## 3. The request (steps 1 and 2)

`manager_route`: `ROUTES` gains `package`; the proposal keeps its four keys; for `package` the `repo` must be a registered repository whose environment has `runner: vitest` (a Python repo gets `none`), the `text` is 10 to 600 characters, the `why` stays the foreman's own words and never reaches the machine. A proposal's `text` is a fill-in the human sees and may edit (the existing rule).

The harness, not the model, parses the lines (`router/env_packages.py`, pure): each line must `fullmatch` `((@[a-z0-9][a-z0-9._-]{0,63}/)?[a-z0-9][a-z0-9._-]{0,63})@(\d+\.\d+\.\d+)`; an exact version only, no range, tag, URL, git, file, alias, or `npm:` form; at most 5 distinct names; a name already in the environment's lock at another version is refused here (an upgrade is not in v1). The card shows the parsed list; a line that does not parse is an error the human sees, never repaired.

The prepare/confirm path reuses P2b: `env_new` takes `source_job` and `source_turn` like `research_new`, with the same checks and audit lines. `ACTIONS` gains `env_new` and `env_build`; no other action changes.

## 4. The job (steps 3 to 5)

A job of kind `env`, in `jobs/`, states `RESOLVING`, `AWAITING_HUMAN` (the report), `BUILDING`, `READY`, `REFUSED`, `FAILED`, `ABANDONED`. No model, no money, but it holds a lock (one `env` job at a time) and counts against `env_packages.max_per_day` (config, default 3).

**Resolve.** One `docker run --rm` of the environment's pinned base image, `--user` non-root, `--cap-drop ALL`, `--security-opt no-new-privileges`, `--read-only` with `/tmp` as tmpfs, the environment's `package.json` and lock mounted read-only, a harness-written `.npmrc` (registry fixed to `https://registry.npmjs.org/`, `ignore-scripts=true`, no token), a timeout of 300 s and an output cap. It runs `npm install --package-lock-only --ignore-scripts --no-audit --no-fund --save-exact NAME@VERSION ...`, then `npm view NAME@VERSION time license deprecated dist.unpackedSize --json` for each new package, and writes the candidate `package.json` and lock to `state/env_jobs/JOB/` (git-ignored, outside `environments/`). The host never runs npm.

**Report** (`router/env_packages.py`, pure; the registry's output is data and only regex-shaped fields are kept; no description, readme or free text is ever shown). Per new package: name, version, direct or transitive, publish time and age in days, license (`^[A-Za-z0-9.()+ -]{1,60}$` or "unreadable"), `deprecated` yes or no, `hasInstallScript`, unpacked size. Totals: new packages, changed existing packages. Gates:

- BLOCK (the job is `REFUSED`, nothing more is offered): a new package younger than `env_packages.min_age_days` (config, 14, the existing two-week rule); any existing locked package changes version (v1 does not upgrade; the report names it); more than `env_packages.max_new` (config, 200) new packages; a package not from the registry or without a sha512 (the build script's own check, run first); npm reports a peer-dependency conflict (`ERESOLVE`) or any error; a candidate that is not lockfile v3.
- WARN (shown, the human decides): `deprecated`; `hasInstallScript` (the script never runs, so the package may not work); a license that is unreadable or not a common permissive one; a package first published less than 90 days ago.

**Confirm 2** names the candidate lock's sha256 (12 hex shown). The build step re-reads the candidate and refuses if its sha differs (the PRD card's digest rule).

**Build.** `scripts/build_env_node.sh` and `scripts/check_env_image.py` on the new name `BASE_upN` (N the next free number; the name must not exist; `ARGUS_ENV_DEFS` points at the job's staged definition, base file copied from the environment). Whether `check_env_image.py` honours `ARGUS_ENV_DEFS` is not verified; if it does not, a small change adds it, in this spec's build. Timeout 900 s. The pins are written in the checkout like any build. A free-disk check (at least 3 GB) runs first.

## 5. Where it stops, and why

`READY` is the end. The harness never edits `config.yaml`, never writes to `environments/`, never commits and never touches the repo (the `env init` precedent). The job leaves in its directory an **adoption bundle** that is only printed and never applied: (a) the files for `environments/NAME_upN/`, (b) the `config.yaml` lines (the environment block and the repo's `environment:` change), (c) the exact dependency lines to add to the repo's `package.json`. A human (Atha, or Claude) adopts it as a PR: a change of config is reviewed, and an adopted environment is the point after which jobs run on it. Until then nothing running changes, and the old image is untouched.

This keeps Claude out of the hard part (resolving, vetting, building, checking) and in the one small, reviewable part. Automatic adoption is a later decision (section 10, Q2).

## 6. The foreman and the chat

- **Sheet and instruction.** `docs/CHAT_CAPABILITIES.md` gets the `package` route, its limits and the line "a new environment: only by a `package` proposal and the human's two confirms; adopting it is a pull request"; the pin `SHEET_SHA256` changes. `INSTRUCTION` gets one sentence about when to propose it (the user names an npm package or a library the repo does not have); a Python repo, a non-registry source, an upgrade of an existing package, or "install it now" is `none` with the reason.
- **Context.** `STEP_KINDS` gains `env`; `step_hint` gets fixed sentences for it (`RESOLVING`, `AWAITING_HUMAN`: "The package report waits for you in the chat", `BUILDING`, `READY`: "The environment is built and checked. Adopting it is a separate pull request; nothing changes until then", `REFUSED`). The foreman never sees a report.
- **Chat.** The proposal box shows "Prepare" for `package`; cards for `env_new` and `env_build` follow the existing card pattern (a server-built description, the labels, every string a text node, no `innerHTML`); a page for an `env` job shows the report and the two buttons, and the next-steps box links to it. The same epoch and double-send guards as P3 apply.
- **Audit.** `env_prepare`, `env_confirm`, `env_build_confirm` lines with the repo, the parsed `name@version` list, `source_job`, `source_turn`, the candidate sha. `why` is never written to a card.
- **Measurement.** `route_eval_v0` gets `package` cases (positive: a named npm library for a Node repo; negative: a Python repo, a git URL, "install now", an upgrade, an injected instruction in pasted text). The pass rate is reported, not assumed.

## 7. Threats and the rule that answers each

| Threat | Rule |
|---|---|
| A prompt-injected foreman proposes a malicious package | The human sees the exact names, versions and the facts; the foreman's `why` never reaches the machine; a typosquat is not proven away: the report shows age, license and maintainers count, labelled as facts, and the human decides. |
| A spec that is not a registry version (git, URL, range, tag) | The strict regex (section 3) and the build script's registry and sha512 check. |
| An install script runs | `--ignore-scripts` in resolve and in build; `hasInstallScript` is a WARN. |
| Registry text as an injection | Only regex-shaped fields are kept; no description or readme is shown or kept. |
| A package's code runs at test time | Same residual risk as every package today: it runs inside the sandbox (no network, read-only). Stated, not removed. |
| The network step is abused | One fixed registry, a non-root read-only container with dropped capabilities, a timeout and an output cap; the host runs no npm. Restricting egress to the registry alone is an open question (Q5). |
| A candidate changes between report and build | The confirm carries the lock's sha; the build re-checks it. |
| Disk or time exhaustion | One `env` job at a time, `max_per_day`, timeouts, a free-disk check. |
| The wrong environment is used silently | Nothing is adopted without a PR; pins are per name; a new name never replaces an old one. |

## 8. Tests and mutants (written, run once after the review)

Tests, new files: `tests/test_env_packages.py` (the parser with the refusals of section 3 each; the gates each, one test per BLOCK and WARN; the report shape; a hostile registry output of oversize, newline and control characters; a duplicate key), `tests/test_env_packages_run.py` (the resolve and build steps against a fake container runner: the argv is exactly the one of section 4, the sha re-check, the timeouts, a refused disk), `tests/test_chat_env.py` (prepare and confirm, the source checks, the audit lines, a stale confirm, one `env` job at a time, the daily limit), `tests/test_chat_env_ui.py` (JS facts and a vm smoke test like P3), plus `route_eval` cases. A live proof before merge: a real resolve, report and build on `bulking_node22` with one small harmless package at least two weeks old; the age gate refusing `@ui-sdk/react`; the hasInstallScript flag read on a package that has one.

Mutants (`verification/chat_env_mutants.py`, written, run once): drop each BLOCK gate; accept a range, a tag or a URL; drop `--ignore-scripts` from either argv; drop a container hardening flag; skip the sha re-check; allow a second `env` job; drop the daily limit; let `why` reach the card; show a registry free-text field; let an existing package change; treat `ERESOLVE` as a warning.

## 9. Not in this spec

Automatic adoption (the config edit and the PR); upgrading an existing package (React 18 to 19 is one: it changes locked packages, so it is a BLOCK and stays with Claude); Python packages (`pip`); packages from git or a URL; removing a package; letting any model read a package's docs; any money.

## 10. Questions for Atha (the review may add more)

- **Q1.** The age rule: 14 days like today's. Keep, or allow a human override for a named package?
- **Q2.** Stop at `READY` with a printed adoption bundle (recommended: the config change stays a reviewed PR), or later let the harness write an adoption that a human confirms a third time?
- **Q3.** v1 refuses any change to an existing locked package. Fine, or do you want upgrades in a later slice?
- **Q4.** `max_new` 200 and `max_per_day` 3: right sizes?
- **Q5.** Limit the resolve container's network to the registry alone (needs a small proxy or firewall rule on this host), or accept the fixed-registry rule for v1?

## 11. Build order

Each slice is a strict-lane PR with its own live proof: S1 `router/env_packages.py` (pure: parser, report, gates) with tests and mutants; S2 the `argus env add` CLI and the resolve runner; S3 the build and check wrapper and the `READY` bundle; S4 the chat actions, cards and page; S5 the foreman route, sheet, instruction, context kinds and `route_eval` cases. The live end-to-end proof with a harmless package closes it.
