"""scripts/pin_status.py: the preflight of sandbox pins in a checkout (PENDING 2026-10-30)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import pin_status as ps  # noqa: E402

IMG = "sha256:" + "a" * 64


def fake(monkeypatch, pins, have=(IMG,)):
    monkeypatch.setattr(ps, "environment_pin", lambda cfg, name, root=None: pins[name])
    monkeypatch.setattr(ps, "docker_has", lambda image: image in have)


def test_a_usable_pin_is_ok_and_each_problem_is_named(monkeypatch):
    fake(monkeypatch, {"a": (IMG, None), "b": (None, "has not been checked"), "c": ("sha256:" + "b" * 64, None)})
    got = {n: p for n, _, p in ps.rows(["a", "b", "c"], {})}
    assert got["a"] is None and got["b"] == "has not been checked" and got["c"].startswith("Docker has no image")


def test_a_pin_that_differs_from_the_other_checkout_is_a_problem(monkeypatch, tmp_path):
    fake(monkeypatch, {"a": (IMG, None)})
    monkeypatch.setattr(ps, "ROOT", tmp_path / "here")
    (tmp_path / "here").mkdir()
    (tmp_path / "there").mkdir()
    (tmp_path / "here" / ".sandbox_image_a").write_text(IMG + "\n")
    assert "no pin there" in ps.rows(["a"], {}, tmp_path / "there")[0][2]
    (tmp_path / "there" / ".sandbox_image_a").write_text("sha256:" + "c" * 64)
    assert "pinned differently" in ps.rows(["a"], {}, tmp_path / "there")[0][2]
    (tmp_path / "there" / ".sandbox_image_a").write_text(IMG)
    assert ps.rows(["a"], {}, tmp_path / "there")[0][2] is None
