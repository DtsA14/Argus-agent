# SPEC_T6_ENV_BUILD (rev 0, 2026-11-21)

Strict lane for the parts that fetch packages and build the sandbox image (supply chain: `router/env_*.py`, `environments/`, the build scripts). Display and docs parts are light lane.

## 1. Where T6 stands (checked against the code, 2026-11-21)
Built already: `argus env propose "<sentence>"` (a model proposes name and one-line description, $0.02 cap, nothing made), `argus env init NAME --path DIR [--register]` (a small Python scaffold
under `src/`, one passing test, one commit, and the one `issue_writer.repos` line; `--register` opens a PR, never merges; it REUSES an environment already under `environments/`: `ledger_py312`
(Python 3.12 + pytest) or `pwa_node22` (React + vitest, `.argus/protected`)). Two pilots ran on it (ledger-cli, ledger-browser).
NOT built: an environment for a repo that needs third-party packages. Today that is about 10 manual steps (athena_py312, Atha 2026-11-15: resolve, PyPI dates, download, hashes, build, check, baseline; two hidden
dependencies, `yfinance` and `tzdata`, were found only by the baseline). Until it exists a new project can only be stdlib + pytest (or the node scaffold).
Also open from the pilots (frictions 2, 3, 9 of `pilots/ledger_cli_v0/README.md`): the first issue of a new repo has no runnable example, the PRD writer cannot run the examples of items 2..n, a stdlib
setup in an example (`Decimal`, `date`) is "not showable as numbers" and closes the install card.

## 2. Decision
T6 is built in two slices, in this order. Slice A is the strict one.
A. `argus env build NAME --repo DIR` (no model): from a repository's declared dependencies make `environments/NAME/{base,requirements.txt,README}` with exact versions and hashes, build the image,
   run the existing checks, run the repository's own baseline tests in the sandbox, report. The environment definition is then a PR of its own (never merged by the command) together with the `config.yaml` line.
B. First-issue handling for a new repo (light-to-strict by part, specified after A has been used once): the writer says "no runnable example yet" as a stated, checked kind (not a defect), stdlib setups
   in the card grammar, examples of items 2..n run when the item starts instead of at queue time.

## 3. Rules of slice A
1. Input: `DIR` is a local repository (clean tree, its own `.git`, outside this checkout) with `pyproject.toml` (`[project].dependencies`, optional `[project.optional-dependencies].dev`) or `requirements*.txt`.
   Anything else (poetry, setup.py only, extras with environment markers the resolver cannot evaluate) is refused with the reason; nothing is guessed.
2. Resolution: for every requirement pick the newest release that is at least 14 days old (PyPI upload time of the release files; a yanked file is never picked; pre-releases never), compatible with
   the base image's Python; transitive dependencies are resolved the same way. The 14-day rule is the supply-chain rule of the project (a just-published malicious release is not taken). The network
   step is the builder container only (as `build_env_from_base.sh` does it: the one step with network); the resolver's own reads of pypi.org are plain HTTPS GETs of the JSON API with a size cap.
3. Hashes: taken from the files pip downloads in the builder, every line `name==version --hash=sha256:...` (the format `build_env_from_base.sh` already enforces, `--require-hashes`).
4. Base: the pinned digest in an existing `environments/*/base` of the same Python minor (never a floating tag); a different Python needs its own human-chosen base, refused here.
5. Output only inside `environments/NAME/` of a new branch/worktree and `.sandbox_image_NAME*` (git-ignored); `NAME` must not exist; the name matches `^[a-z][a-z0-9_]{0,31}$`.
6. Checks: `scripts/check_env_image.py NAME` must pass (the router and the grader refuse an environment without that record). Then the baseline: the repo's tests run in the sandbox with the new image, no network;
   the report lists every import that failed (the way `yfinance` and `tzdata` were found) and every test that failed; a baseline that fails is reported, the definition is NOT proposed.
7. Money: none (no model). Time: minutes. Disk: the pip cache `~/.cache/argus-pip`.
8. Human gates: (a) the 14-day picks and the resulting `requirements.txt` are printed as a table (name, version, release date, license if the metadata has one) for the human to read before the PR is opened;
   (b) the PR adds `environments/NAME/*` and one `config.yaml` line (`issue_writer.repos` and `environments`); it is never merged by the command; (c) merging a PR that changes `environments/` or `config.yaml` is the human's word.
9. Pins: `.sandbox_image_NAME*` are git-ignored, so after a build the command prints where they are and how to copy them to the checkout that serves the chat (`pilot3a_live`); a missing pin there is what stopped the chat once (2026-11-17).
10. Frontend (Node) repos: out of slice A (`pwa_node22` exists for a vitest scaffold); a lockfile-based node builder is a later slice, made when a real frontend issue needs it.

## 4. Tests and trial
Resolver with a recorded PyPI JSON fixture (14-day cut, yanked, pre-release, Python-requires, a package with no usable release), refusals (no deps file, poetry, dirty tree, inside the checkout, name taken, base missing),
the generated `requirements.txt` accepted by `build_env_from_base.sh`'s validator, the PR text, no model call, no write outside `environments/NAME/` and the git-ignored pins. A real build of one small public repo with two
or three third-party packages, run once by hand (Atha present), is the trial; its result goes in `pilots/t6_env_build_v0/RESULT.md`. Mutants once after the review.

## 5. Not here
Slice B (written after A is used), node builders, linters and type-check gates (separate parked item), the one-prompt connector T5, changing `web.environments`.
