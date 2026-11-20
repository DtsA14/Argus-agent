"""`argus env init NAME --path DIR [--environment ENV]`: the steps of the ledger-cli pilot that were done by hand (pilots/ledger_cli_v0/README.md, Setup), as one command.

It makes a new local repository from a small Python scaffold (package under src/, one passing test, pytest configured to see src/, a README, a .gitignore, one
commit) and prints the one line of config.yaml that registers it (`issue_writer.repos`) and the next commands. It never edits config.yaml (a change of the
config is a PR of its own), never pushes, never calls a model and never builds an image: the environment must already exist under environments/ (the pilot
reused ledger_py312). The directory must not exist or must be empty, must not be inside this checkout, and the git identity must exist (none is made up)."""
import os
import re
import subprocess
from pathlib import Path

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


def init(name, path, *, description="A new project", environment="ledger_py312", root=ROOT):
    """Make the scaffold and its commit; returns {path, package, commit, config_line, files}. Refused (nothing made) on anything unexpected."""
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
    made = files(name, desc)
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
