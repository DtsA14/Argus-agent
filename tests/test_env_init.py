"""`argus env init` (T6, first step): a scaffold with one commit and the config line; it makes nothing it was not asked for."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from router import env_init as ei  # noqa: E402
from router import job as rj  # noqa: E402


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    (h / ".gitconfig").write_text("[user]\n\tname = Some Person\n\temail = some@example.org\n")
    monkeypatch.setenv("HOME", str(h))
    for k in [k for k in os.environ if k.startswith("GIT_")]:
        monkeypatch.delenv(k)
    return h


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "checkout"
    (r / "environments" / "ledger_py312").mkdir(parents=True)
    return r


def test_it_makes_the_scaffold_with_one_commit_and_prints_the_config_line(tmp_path, root):
    out = ei.init("shop-tools", tmp_path / "shop-tools", description="Tools for a shop", root=root)
    d = Path(out["path"])
    assert out["files"] == [".gitignore", "README.md", "pyproject.toml", "src/shop_tools/__init__.py", "tests/test_smoke.py"]
    assert (d / "src/shop_tools/__init__.py").read_text().count('__version__ = "0.0.1"') == 1
    assert out["config_line"].strip() == f'shop-tools: {{path: "{d}", environment: ledger_py312}}'
    assert subprocess.run(["git", "-C", str(d), "rev-list", "--count", "HEAD"], capture_output=True, text=True).stdout.strip() == "1"
    assert subprocess.run(["git", "-C", str(d), "status", "--porcelain"], capture_output=True, text=True).stdout == ""
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=d, capture_output=True, text=True)
    assert r.returncode == 0 and "1 passed" in r.stdout


def test_the_config_line_keeps_a_tilde_path(tmp_path, root, home):
    out = ei.init("tilde-app", "~/tilde-app", root=root)
    assert out["config_line"].strip() == 'tilde-app: {path: "~/tilde-app", environment: ledger_py312}'
    assert (home / "tilde-app" / "pyproject.toml").is_file()


@pytest.mark.parametrize("name", ["", "a", "Shop", "shop_tools", "-shop", "shop-", "a" * 50, "sh op", "../x"])
def test_a_bad_name_is_refused(tmp_path, root, name):
    with pytest.raises(rj.Refused, match="env init"):
        ei.init(name, tmp_path / "x", root=root)
    assert not (tmp_path / "x").exists()


def test_an_unknown_environment_or_a_missing_parent_is_refused(tmp_path, root):
    with pytest.raises(rj.Refused, match="builds no image"):
        ei.init("good-name", tmp_path / "x", environment="nope", root=root)
    with pytest.raises(rj.Refused, match="builds no image"):
        ei.init("good-name", tmp_path / "x", environment="../etc", root=root)
    with pytest.raises(rj.Refused, match="parent directory"):
        ei.init("good-name", tmp_path / "no" / "x", root=root)


def test_a_directory_that_is_not_empty_or_is_inside_the_checkout_is_refused(tmp_path, root):
    d = tmp_path / "busy"
    d.mkdir()
    (d / "f").write_text("x")
    with pytest.raises(rj.Refused, match="not an empty directory"):
        ei.init("good-name", d, root=root)
    assert (d / "f").read_text() == "x"
    with pytest.raises(rj.Refused, match="inside"):
        ei.init("good-name", root / "sub", root=root)
    empty = tmp_path / "empty"
    empty.mkdir()
    ei.init("good-name", empty, root=root)                          # an empty directory is fine
    assert (empty / ".git").is_dir()


def test_no_git_identity_is_refused_and_none_is_made_up(tmp_path, root, home):
    (home / ".gitconfig").write_text("")
    with pytest.raises(rj.Refused, match="no git identity"):
        ei.init("good-name", tmp_path / "x", root=root)
    assert not (tmp_path / "x").exists()


def test_a_failed_git_step_leaves_nothing_behind(tmp_path, root, monkeypatch):
    real = ei._git

    def broken(path, *args):
        if args and args[0] == "commit":
            return subprocess.CompletedProcess(args, 1, "", "boom")
        return real(path, *args)
    monkeypatch.setattr(ei, "_git", broken)
    with pytest.raises(rj.Refused, match="git commit failed"):
        ei.init("good-name", tmp_path / "x", root=root)
    assert not (tmp_path / "x").exists()


def test_the_description_is_one_clean_line_and_cannot_break_the_toml(tmp_path, root):
    out = ei.init("quoted-app", tmp_path / "q", description='say "hi"\nand \\ more', root=root)
    text = (Path(out["path"]) / "pyproject.toml").read_text()
    import tomllib
    assert tomllib.loads(text)["project"]["description"] == "say 'hi' and / more"


def test_the_command_prints_the_next_steps_and_edits_no_config(tmp_path, root, capsys, monkeypatch):
    import argus
    monkeypatch.setattr(ei, "ROOT", root)
    monkeypatch.setattr(ei, "init", lambda *a, **k: real_init(*a, **{**k, "root": root}))
    assert argus.main(["env", "init", "cmd-app", "--path", str(tmp_path / "cmd-app")], deps=None) == 0
    out = capsys.readouterr().out
    assert "cmd-app: {path:" in out and "nothing was edited" in out and "prd new" in out


real_init = ei.init
