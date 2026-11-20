"""`argus env init NAME --path DIR [--environment ENV]`: the steps of the ledger-cli pilot that were done by hand (pilots/ledger_cli_v0/README.md, Setup), as one command.

It makes a new local repository from a small Python scaffold (package under src/, one passing test, pytest configured to see src/, a README, a .gitignore, one
commit) and prints the one line of config.yaml that registers it (`issue_writer.repos`) and the next commands. It never edits config.yaml (a change of the
config is a PR of its own), never pushes, never calls a model and never builds an image: the environment must already exist under environments/ (the pilot
reused ledger_py312). The directory must not exist or must be empty, must not be inside this checkout, and the git identity must exist (none is made up)."""
import json
import os
import re
import subprocess
from pathlib import Path

import yaml

from router import job as rj

ROOT = Path(__file__).resolve().parent.parent
NAME = re.compile(r"[a-z][a-z0-9-]{1,38}[a-z0-9]")
DESC_MAX = 200
GIT_TIMEOUT = 30


def _refuse(why):
    raise rj.Refused(f"env init: {why}; nothing was made")


def _git(path, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, timeout=GIT_TIMEOUT, env=env)


def files(name, description):
    pkg = name.replace("-", "_")
    return {
        "pyproject.toml": f'[project]\nname = "{name}"\nversion = "0.0.1"\ndescription = "{description}"\nrequires-python = ">=3.12"\n\n[tool.pytest.ini_options]\npythonpath = ["src"]\ntestpaths = ["tests"]\n',
        ".gitignore": "__pycache__/\n*.pyc\n.pytest_cache/\n",
        "README.md": f"# {name}\n\n{description}\n\nRun the tests: `python -m pytest`.\n",
        f"src/{pkg}/__init__.py": f'"""{name}: {description}"""\n\n__version__ = "0.0.1"\n',
        "tests/test_smoke.py": f"import {pkg}\n\n\ndef test_the_package_imports_and_has_a_version():\n    assert {pkg}.__version__ == \"0.0.1\"\n",
    }


PROTECTED = """# Files the coding agent never changes, one glob per line (Argus contract globs). Read by the Argus harness from the job's commit (SPEC_PROTECTED_FILES).
# A new test file (*.test.*) may be added; an existing one never changes. Build and tool configuration is executed at build or test time, so none of it may be added either.
package.json
**/package.json
package-lock.json
.npmrc
**/.npmrc
index.html
vite.config.js
vitest.setup.js
"""
SETUP = """// Every test fails when the code under test calls console.error (React reports invalid markup and other misuse only there).
// Protected: the coding agent cannot change or remove it (.argus/protected).
import { AssertionError } from 'node:assert'
import { format } from 'node:util'
import { afterEach, beforeEach } from 'vitest'

const original = console.error
let errors = []

beforeEach(() => {
  errors = []
  console.error = (...args) => {
    errors.push(format(...args))
    original(...args)
  }
})

afterEach(() => {
  console.error = original
  if (errors.length > 0) {
    throw new AssertionError({ message: `console.error was called ${errors.length} time(s): ${errors[0].slice(0, 300)}` })
  }
})
"""


def node_files(name, description, root=ROOT):
    """The scaffold of a vitest environment: the packages are exactly the environment's (a new package is a new environment)."""
    env_pkg = json.loads((Path(root) / "environments" / "pwa_node22" / "package.json").read_text(encoding="utf-8"))
    pkg = {"name": name, "private": True, "type": "module", "description": description,
           "dependencies": env_pkg["dependencies"], "devDependencies": env_pkg["devDependencies"]}
    title = name.replace("-", " ")
    return {
        "package.json": json.dumps(pkg, indent=2) + "\n",
        ".gitignore": "node_modules/\ndist/\n",
        "README.md": f"# {name}\n\n{description}\n\nThe tests run with vitest (`npx vitest run`) in the Argus sandbox environment; no package outside that environment's lock can be added.\n",
        "vite.config.js": "import react from '@vitejs/plugin-react'\n\nexport default { plugins: [react()], test: { environment: 'jsdom', setupFiles: ['./vitest.setup.js'] } }\n",
        "vitest.setup.js": SETUP,
        ".argus/protected": PROTECTED,
        "index.html": f'<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>{title}</title>\n</head>\n<body>\n<div id="root"></div>\n<script type="module" src="/src/main.jsx"></script>\n</body>\n</html>\n',
        "src/main.jsx": "import { createRoot } from 'react-dom/client'\nimport App from './App.jsx'\n\ncreateRoot(document.getElementById('root')).render(<App />)\n",
        "src/App.jsx": f"export default function App() {{\n  return <h1>{title}</h1>\n}}\n",
        "src/App.test.jsx": f"import {{ render, screen }} from '@testing-library/react'\nimport {{ expect, test }} from 'vitest'\nimport App from './App.jsx'\n\ntest('the app shows its name', () => {{\n  render(<App />)\n  expect(screen.getByText('{title}')).not.toBeNull()\n}})\n",
    }


def runner_of(environment, root=ROOT):
    """'vitest' or 'pytest' as config.yaml (sandbox.environments) says for the environment; pytest when there is no config or no runner."""
    try:
        cfg = yaml.safe_load((Path(root) / "config.yaml").read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return "pytest"
    return (((cfg.get("sandbox") or {}).get("environments") or {}).get(environment) or {}).get("runner") or "pytest"


def init(name, path, *, description="A new project", environment="ledger_py312", root=ROOT):
    """Make the scaffold and its commit; returns {path, package, commit, config_line, files}. Refused (nothing made) on anything unexpected.
    A vitest environment (runner: vitest in config.yaml) gets a React + vitest scaffold with .argus/protected; any other gets the Python one."""
    if not isinstance(name, str) or not NAME.fullmatch(name):
        _refuse("the name is lowercase letters, digits and hyphens, 3 to 40 characters, starting with a letter")
    desc = " ".join(str(description).split())[:DESC_MAX].replace('"', "'").replace("\\", "/")
    if not desc:
        _refuse("the description is empty")
    if not isinstance(environment, str) or not re.fullmatch(r"[A-Za-z0-9_]{1,40}", environment) or not (Path(root) / "environments" / environment).is_dir():
        _refuse(f"environment {environment!r} is not one under environments/ (this command builds no image)")
    target = Path(os.path.expanduser(str(path))).absolute()
    real_root = Path(root).resolve()
    if target == real_root or real_root in target.resolve().parents or target.resolve() in real_root.parents:
        _refuse("the directory is inside (or contains) the Argus checkout")
    if target.exists() and (not target.is_dir() or any(target.iterdir()) or target.is_symlink()):
        _refuse(f"{target} exists and is not an empty directory")
    if not target.parent.is_dir():
        _refuse(f"the parent directory {target.parent} does not exist")
    identity = [_git(target.parent, "config", "--get", k).stdout.strip() for k in ("user.name", "user.email")]
    if not all(identity):
        _refuse("no git identity (user.name and user.email): set them globally; none is made up")
    made = node_files(name, desc, root) if runner_of(environment, root) == "vitest" else files(name, desc)
    try:
        target.mkdir(exist_ok=True)
        for rel, text in made.items():
            f = target / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8")
        for step in (("init", "-q", "-b", "main"), ("add", "-A"), ("commit", "-q", "-m", f"scaffold: {name}")):
            r = _git(target, *step)
            if r.returncode:
                raise rj.Refused(f"env init: git {step[0]} failed: {r.stderr.strip()[:200]}")
        commit = _git(target, "rev-parse", "HEAD").stdout.strip()
    except Exception:
        import shutil
        shutil.rmtree(target, ignore_errors=True)         # a half made scaffold is not left behind
        raise
    shown = str(path) if str(path).startswith("~") else str(target)
    return {"path": str(target), "package": name.replace("-", "_"), "commit": commit, "files": sorted(made),
            "config_line": f'    {name}: {{path: "{shown}", environment: {environment}}}'}
