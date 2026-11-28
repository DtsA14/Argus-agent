"""scripts/repin.py: recomputes the chat's static pins and the sheet pin; --check writes nothing; the viewer's SW pin is never touched."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "repin.py"


@pytest.fixture
def tree(tmp_path):
    for f in ("router/chat.py", "router/manager_route.py", "router/stage_viewer.py", "docs/CHAT_CAPABILITIES.md", "router/chat_static/index.html", "router/chat_static/app.js", "router/chat_static/app.css"):
        (tmp_path / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / f, tmp_path / f)
    return tmp_path


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def test_the_real_pins_match_in_this_checkout():
    r = run("--check")
    assert r.returncode == 0 and "all pins match" in r.stdout, r.stdout + r.stderr


def test_a_changed_file_makes_its_pin_stale_and_check_writes_nothing(tree):
    (tree / "router/chat_static/app.js").write_text((tree / "router/chat_static/app.js").read_text() + "\n// edit\n")
    before = (tree / "router/chat.py").read_text()
    r = run("--check", "--root", str(tree))
    assert r.returncode == 1 and "stale: router/chat.py app.js" in r.stdout and "index.html" not in r.stdout and "app.css" not in r.stdout
    assert (tree / "router/chat.py").read_text() == before


def test_repin_rewrites_only_the_stale_line_and_the_next_check_is_clean(tree):
    (tree / "router/chat_static/app.css").write_text((tree / "router/chat_static/app.css").read_text() + "\n/* edit */\n")
    (tree / "docs/CHAT_CAPABILITIES.md").write_text((tree / "docs/CHAT_CAPABILITIES.md").read_text() + "\nmore\n")
    before_chat, before_sheet, before_sw = (tree / "router/chat.py").read_text(), (tree / "router/manager_route.py").read_text(), (tree / "router/stage_viewer.py").read_text()
    r = run("--root", str(tree))
    assert r.returncode == 0 and "repinned: router/chat.py app.css" in r.stdout and "repinned: router/manager_route.py SHEET_SHA256" in r.stdout
    after_chat, after_sheet = (tree / "router/chat.py").read_text(), (tree / "router/manager_route.py").read_text()
    assert len([1 for a, b in zip(before_chat.splitlines(), after_chat.splitlines()) if a != b]) == 1 and len([1 for a, b in zip(before_sheet.splitlines(), after_sheet.splitlines()) if a != b]) == 1
    assert (tree / "router/stage_viewer.py").read_text() == before_sw
    assert run("--check", "--root", str(tree)).returncode == 0


def test_a_pin_that_cannot_be_found_once_refuses_and_writes_nothing(tree):
    p = tree / "router/chat.py"
    import re
    p.write_text(re.sub(r'"app\.js": "([0-9a-f]{64})', r'"app.jsx": "\1', p.read_text(), count=1))      # the pin line, not the content-type table that also has "app.js": "
    (tree / "router/chat_static/app.css").write_text("x")
    before = p.read_text()
    r = run("--root", str(tree))
    assert r.returncode != 0 and "app.js appears 0 times" in (r.stderr + r.stdout) and p.read_text() == before
