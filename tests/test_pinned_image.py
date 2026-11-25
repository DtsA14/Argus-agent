"""SPEC_CHAT_UI1 F16: pinned_image is a pure lookup (variable, pin file, configured image) with the pin file read as the CLI would
but never written to the environment. Real files in a tmp root; nothing is faked."""
import os

import pytest

from router import job as rj
from tools import sandbox as sb

SHA = "sha256:" + "a" * 64
CFG = {"environments": {"envx": {"image": "configured@sha256:" + "c" * 64}, "envy": {}}}


@pytest.fixture(autouse=True)
def no_variable(monkeypatch):
    monkeypatch.delenv("ARGUS_SANDBOX_IMAGE_ENVX", raising=False)
    monkeypatch.delenv("ARGUS_SANDBOX_IMAGE_ENVY", raising=False)


def pin(root, name, text):
    (root / f".sandbox_image_{name}").write_text(text)


def test_the_variable_wins_over_the_file_and_the_configured_image(tmp_path, monkeypatch):
    pin(tmp_path, "envx", SHA + "\n")
    monkeypatch.setenv("ARGUS_SANDBOX_IMAGE_ENVX", "sha256:" + "b" * 64)
    assert sb.pinned_image(CFG, "envx", tmp_path) == ("sha256:" + "b" * 64, None)


def test_the_file_wins_over_the_configured_image_and_is_stripped(tmp_path):
    pin(tmp_path, "envx", SHA + "\n")
    assert sb.pinned_image(CFG, "envx", tmp_path) == (SHA, None)


def test_no_file_means_the_configured_image_or_none(tmp_path):
    assert sb.pinned_image(CFG, "envx", tmp_path) == ("configured@sha256:" + "c" * 64, None)
    assert sb.pinned_image(CFG, "envy", tmp_path) == (None, None)


def test_a_named_digest_is_accepted(tmp_path):
    pin(tmp_path, "envx", "argus-sandbox-envx@sha256:" + "d" * 64)
    assert sb.pinned_image(CFG, "envx", tmp_path)[1] is None


@pytest.mark.parametrize("text", ["", "junk", "sha256:abc", SHA + "\nsecond line", "x" * 400, SHA.upper().replace("SHA256", "sha256")])
def test_a_pin_file_that_is_not_one_digest_is_refused_never_a_fallback(tmp_path, text):
    pin(tmp_path, "envx", text)
    image, problem = sb.pinned_image(CFG, "envx", tmp_path)
    assert image is None and "unreadable" in problem


def test_a_pin_file_that_is_a_link_or_a_directory_is_refused(tmp_path):
    real = tmp_path / "real"
    real.write_text(SHA)
    os.symlink(real, tmp_path / ".sandbox_image_envx")
    assert sb.pinned_image(CFG, "envx", tmp_path)[0] is None
    (tmp_path / ".sandbox_image_envy").mkdir()
    assert sb.pinned_image(CFG, "envy", tmp_path)[0] is None


def test_an_unknown_environment_keeps_the_old_problem(tmp_path):
    assert "unknown sandbox environment" in sb.pinned_image(CFG, "nope", tmp_path)[1]


def test_a_file_rebuilt_between_two_asks_changes_the_answer_and_the_environment_is_never_written(tmp_path):
    before = dict(os.environ)
    pin(tmp_path, "envx", SHA)
    assert sb.pinned_image(CFG, "envx", tmp_path)[0] == SHA
    pin(tmp_path, "envx", "sha256:" + "e" * 64)
    assert sb.pinned_image(CFG, "envx", tmp_path)[0] == "sha256:" + "e" * 64
    assert dict(os.environ) == before


def test_environment_pin_reads_the_file_in_its_root(tmp_path):
    (tmp_path / "environments").mkdir()
    pin(tmp_path, "envx", SHA)
    image, problem = rj.environment_pin({"sandbox": CFG}, "envx", tmp_path)
    assert (image, problem) == (SHA, None)
