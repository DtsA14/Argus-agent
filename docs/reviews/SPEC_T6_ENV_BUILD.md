# SPEC_T6_ENV_BUILD (rev 1, 2026-11-21)

Strict lane (supply chain: `router/env_*.py`, `environments/`, the build scripts, `config.yaml`). Rev 1 answers the Opus review of rev 0 (GO with fixes, 17 corrections, all taken).

## 1. Where T6 stands (checked against the code)
Built: `argus env propose "<sentence>"` (a model proposes name and description, $0.02 cap, nothing made) and `argus env init NAME --path DIR [--environment ENV] [--register]`
(router/env_init.py): a small scaffold with one commit (a vitest scaffold when config says `runner: vitest` for that environment, else Python; `env_init.py:94-101,113,126`),
the `issue_writer.repos` line printed, and with `--register` a PR for THAT line only (`env_propose.py:88-108`; `config_with` refuses a repo already registered, `:105-106`).
It does not build or choose an environment: it takes one already under `environments/` (any directory there). `env init` was made after the ledger-cli pilot (that scaffold was by hand,
`dd4d72f`) and ran for ledger-browser only. Small known bug: `--environment sympy_py39` writes `requires-python = ">=3.12"`.
NOT built: an environment for a repo that needs third-party packages: about 10 manual steps today (athena_py312). Hidden-dependency evidence, corrected: `yfinance` WAS declared in athena's
`requirements.txt:5` (athena_py312 was picked from athena's venv); only `tzdata` was hidden (pandas lists it for win32 only; the slim image has no zoneinfo data). The same file has
`uvicorn[standard]`, which athena_py312 left out on purpose (README:3): a resolver fed that file would not reproduce athena_py312 without `--exclude`/`--only`.
Open from the pilots (frictions 2, 3, 9 of `pilots/ledger_cli_v0/README.md`): first issue of a new repo has no runnable example, the PRD writer cannot run examples of items 2..n, a stdlib setup
in an example closes the install card. That is slice B, written after slice A has been used.

## 2. Decision
`argus env build NAME --repo DIR` (no model) is built in five strict PRs, smallest first; each stands alone and is merged only after its own review/mutants/precheck/verify_at.
- **PR1 builder hardening.** `scripts/build_env_from_base.sh` (pip line, ~:28-30) gets `--only-binary :all:` and an explicit `--index-url https://pypi.org/simple` (today an sdist line that passes the
  validator regex at :22 runs its setup code in a container with full network and a writable shared cache `-v $CACHE:/cache`). Test; rebuild one existing environment once to show nothing changes.
- **PR2 offline resolver.** Pure function: recorded PyPI JSON + per-file core-metadata fixtures, a tag/marker environment, a cutoff date -> pins (name, version, file, sha256) and a flag table. Built on
  `pip._vendor.resolvelib` 1.0.1 and `packaging` 24.0 (present on the host python; pip 24.0 and the base image's pip 25.0.1 have no `--uploaded-prior-to`, no uv here). No network, no build.
- **PR3 fetcher + `argus env build ... --dry-run`.** The bounded HTTPS fetcher for pypi.org (reusing the bounded fetch of `tools/web_fetch.py`; NOT the agent's `web.hosts`, which stays as is) and the table only.
  First real use: REPLAY `ledger_py312` and `athena_py312` with their own cutoffs (athena: 2026-11-01, README:6) and diff against the hand-made `requirements.txt`: an objective oracle.
- **PR4 build, check, baseline.** In a new git worktree: `environments/NAME/`, build, `scripts/check_env_image.py NAME`, the baseline, the report, the plugin/`.pth` scan.
- **PR5 registration PR.** `config_with` generalized (add OR change an `issue_writer.repos` line) and the second block `sandbox.environments.NAME: {image: null}` (`config.yaml:589-629`; without it
  `tools/sandbox.py:74` refuses the name). The PR is never merged by the command.

## 3. Rules
1. Input: a local repository (clean tree, own `.git`, outside this checkout, no symlinked manifest) with `pyproject.toml` (read with `tomllib` only: `[project].dependencies`, optional-dependencies,
   `[dependency-groups]` or refused explicitly) or ONE `requirements*.txt` (say which if several). Every pip option and non-name requirement is refused: `-r`/`-c` outside the file, `-e`, `--index-url`,
   `--extra-index-url`, `--trusted-host`, direct URLs (`pkg @ https://`), VCS, local paths. Names normalized (PEP 503). `--only NAME,...` and `--exclude NAME,...` select what goes in; `--extra REQ` adds one
   (the human's answer to a failed import).
2. Resolution: candidates are only FILES (wheels) uploaded at least 14 days before `--cutoff DATE` (default: today minus 14 days; recorded in the README so a result is reproducible); a release counts only if ALL
   its files are older than the cutoff (the READMEs' rule, `ledger_py312/README:4`: a wheel added late to an old release is the attack); yanked and pre-releases never; newest preferred, by a backtracking
   resolution (not "newest of each"). Dependencies come from the chosen wheel's own METADATA (core-metadata), never the per-release JSON `requires_dist` (often null). Rounds, requests and bytes are bounded.
   The 14-day rule is project practice (READMEs), stated here as this command's rule.
3. Platform: tags and marker environment are READ from inside the pinned base with `--network none` (`packaging.tags.sys_tags()`, `markers.default_environment()`: aarch64, glibc, cp312), not hand-coded;
   every marker including `extra ==` is evaluated against it; no compatible wheel, or an sdist-only package, is refused and NAMED. The README states the image is arm64-only (one hash per line, `build_env_from_base.sh:22`).
4. Hashes: the sha256 of the exact file the resolver chose, from PyPI JSON `digests`; the builder's `--require-hashes` then verifies it. This is still trusting PyPI; the cutoff is the only time defence. Said in the README.
5. Base: the digest in an existing `environments/*/base` of the same Python minor; another Python is refused. `pytest` is added at the version Argus's parser was built on (9.1.1; `check_env_image.py:108`
   requires `pytest` pinned) and a repo that excludes or conflicts with it is refused.
6. Names: `^[a-z][a-z0-9_]{0,31}$`, must not exist under `environments/` AND must not be in `sandbox.environments` (`argus`, `sympy`: `router/job.py:241-242` skips the check-record requirement when no `environments/NAME`).
7. Output only inside `environments/NAME/` of a new worktree and the git-ignored `.sandbox_image_NAME*`; `check_env_image.py` reads `ROOT/environments/NAME` and `ROOT/.sandbox_image_NAME.json`, so build and check run in
   that worktree; all three pin files are copied to the checkout that serves the chat, checked with `scripts/pin_status.py --against`.
8. Plugins and start-up hooks: a wheel cannot run code at install, but in the sandbox a `*.pth` file runs on every interpreter start and a `pytest11` entry point loads into every pytest run
   (nothing sets `PYTEST_DISABLE_PLUGIN_AUTOLOAD`; `acceptance/validation.py:56` pins only `-p no:cacheprovider`): a package could change test outcomes in validations, the check and the grader.
   The report lists per package every `.pth`, `pytest11` entry point and console script, and refuses any not on a small allowlist (the pytest plugins of `pytest`'s own known set, `anyio`'s).
9. Baseline: the repo's tests run in the sandbox with the new image, no network, read-only workspace, the sandbox defaults (60 s, 512m). Import and collection errors BLOCK the proposal and are reported by MODULE
   (an import name is never turned into a package: `yaml` is not PyYAML; the human answers with `--extra`). Other failures need a named `--allow-failing NODE` with a reason, recorded in the README
   (athena's own baseline has a date-dependent failure).
10. Human gate, honest: the table (name, version, file date, project's FIRST upload date, license if present, compiled or pure, plugin/.pth flags, "in no existing environment") is a labelled Claude read plus these
    mechanical flags, not something Atha can judge (a typosquat is a young project; a 15-day-old squat passes the cutoff). The PR is the human's to merge; merging a PR that changes `environments/` or `config.yaml` is his word.
11. Frontend (Node) repos: out of this spec (`pwa_node22` exists for a vitest scaffold); a lockfile-based builder is made when a real frontend issue needs it.
12. Money: none (no model). Disk: the pip cache `~/.cache/argus-pip`. The existing check-record gap stays noted (the record is not tied to `requirements_sha256`, `job.py:244-254`).

## 4. Tests and trial
PR1: the script with a fixture that has an sdist line (refused), a wheel line (accepted). PR2: file-level upload time (a late wheel on an old release), `requires_dist` null (deps from metadata), markers
(tzdata win32 not picked; extras), x86-only or sdist-only refused, a conflict refused, bounds, pytest added and a pytest conflict refused, the cutoff in the output. PR3: refusals (no manifest, poetry,
dirty tree, inside the checkout, name taken or in `sandbox.environments`, every pip option/URL/VCS line), the replay of `ledger_py312` and `athena_py312` against their hand-made files (the objective oracle),
no write outside. PR4: plugin and `.pth` flagged or refused, an import failure reported by module with no package auto-added, `--allow-failing`, pins copied. PR5: add and change of a config line, both blocks.
Trial: one small public repo with 2-3 third-party packages, once by hand with Atha present, `pilots/t6_env_build_v0/RESULT.md`. Mutants once per PR after its review; the reviewer's 20 (all in code that exists today:
`build_env_from_base.sh` regexes and `--require-hashes`/`--no-deps`, `router/job.py` check-record conditions, `check_env_image.py` pytest pin and `all(...)`, `env_propose.py:105`, `env_init.py:121`, `tools/sandbox.py:74`)
guard the existing gates this relies on; each PR adds its own.

## 5. Not here
Slice B (first-issue handling), node builders, lint/type-check gates, the one-prompt connector T5, changing `web.hosts` or `web.environments`.
