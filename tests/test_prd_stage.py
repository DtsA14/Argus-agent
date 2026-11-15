"""SPEC_PRD_STAGE (part B1): `argus prd check` and `approve` (router/prd.py): a PRD folder is checked against the paths that pass through Argus
(the running proxy regex and the snapshot's tables), read once, and approved once into a PENDING queue. No model, no money."""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_drafter as td  # noqa: E402
import test_queue as tq  # noqa: E402
import test_router as tr  # noqa: E402
from router import job as rj  # noqa: E402
from router import prd as rp  # noqa: E402
from router import queue as rq  # noqa: E402
from router import stage_data as sd  # noqa: E402
from router import stage_viewer as sv  # noqa: E402

JID = "j20261112_053107_1929"


@pytest.fixture
def qe(tmp_path, monkeypatch):
    return tq.Q(tmp_path, monkeypatch)


class Folder:
    def __init__(self, qe, tmp_path):
        self.qe, self.dir = qe, tmp_path / "prd"
        self.dir.mkdir()

    def write(self, texts=None, items=None, prd="# PRD\n\nThe contract is frozen here.\n", **spec):
        texts = texts or [f"{td.ISSUE}\n\nitem {i}" for i in (1, 2)]
        items = items if items is not None else [{"n": i} for i in range(1, len(texts) + 1)]
        body = {"repo": "demo", "commit": tq.git(self.qe.repo, "rev-parse", "HEAD"), "max_usd": 3.0, "items": items, **spec}
        (self.dir / "PRD.md").write_text(prd)
        (self.dir / "issues.json").write_text(json.dumps(body))
        for i, t in enumerate(texts, 1):
            (self.dir / f"issue-{i}.md").write_text(t)
        return self

    def check(self):
        return rp.report(self.dir, cfg=self.qe.cfg, queues_dir=self.qe.queues, jobs_dir=self.qe.jobs)

    def sha(self):
        return rp.folder_sha(rp.read_folder(self.dir))

    def approve(self, sha=None):
        return rp.approve(self.dir, sha or self.sha()[:12], cfg=self.qe.cfg, deps=self.qe.env.deps, queues_dir=self.qe.queues, jobs_dir=self.qe.jobs)


@pytest.fixture
def fo(qe, tmp_path):
    return Folder(qe, tmp_path).write()


def blocked(fo, needle):
    text, ok = fo.check()
    assert not ok and any(l.startswith("BLOCK") and needle in l for l in text.splitlines()), text
    return text


def with_text(fo, line, **path):
    texts = [f"{td.ISSUE}\n\n{line}", f"{td.ISSUE}\n\nitem 2"]
    return fo.write(texts=texts, **path)


# ---- the happy path and what the check reads ------------------------------------------------------------------------

def test_a_sound_folder_passes_and_prints_its_sha(fo):
    text, ok = fo.check()
    assert ok and f"prd sha {fo.sha()}" in text and not any(l.startswith("BLOCK ") for l in text.splitlines())


def test_check_writes_nothing(fo, qe):
    before = {p: p.read_bytes() for p in fo.dir.iterdir()}
    fo.check()
    assert {p: p.read_bytes() for p in fo.dir.iterdir()} == before and not qe.queues.exists()


# ---- the real shape of Stage 19 ----------------------------------------------------------------------------------------

def test_an_issue_that_names_a_ledger_endpoint_without_declaring_it_is_blocked(fo):
    with_text(fo, "Add `GET /scoreboard/models`, the model calls per model.")
    blocked(fo, "/scoreboard/models but it is not in this item's paths")


def test_a_ledger_path_the_viewer_will_call_through_the_proxy_is_blocked_with_the_regex_line(fo):
    with_text(fo, "Add `GET /scoreboard/models`.", items=[{"n": 1, "paths": [{"side": "ledger", "path": "/scoreboard/models", "via_proxy": True}]}, {"n": 2}])
    assert "stage_viewer.py:76" in blocked(fo, "/api/scoreboard/models is not forwarded")


def test_a_ledger_path_that_the_viewer_never_calls_passes(fo):
    with_text(fo, "Add `GET /scoreboard/models`.", items=[{"n": 1, "paths": [{"side": "ledger", "path": "/scoreboard/models", "via_proxy": False}]}, {"n": 2}])
    assert fo.check()[1]


def test_a_ledger_path_must_say_whether_it_goes_through_the_proxy(fo):
    with_text(fo, "Add `GET /scoreboard`.", items=[{"n": 1, "paths": [{"side": "ledger", "path": "/scoreboard"}]}, {"n": 2}])
    blocked(fo, "via_proxy must be true or false")


def test_a_ledger_path_cannot_start_with_api_to_silence_the_text_rule(fo):
    with_text(fo, "Add `GET /api/x`.", items=[{"n": 1, "paths": [{"side": "ledger", "path": "/api/x", "via_proxy": False}]}, {"n": 2}])
    blocked(fo, "must start with / and not with /api")


# ---- the proxy's own rule, through the running code -----------------------------------------------------------------------------

def vpath(fo, path, line=None):
    fo.write(texts=[f"{td.ISSUE}\n\n{line or ''}", f"{td.ISSUE}\n\nitem 2"], items=[{"n": 1, "paths": [{"side": "viewer-api", "path": path}]}, {"n": 2}])
    return fo.check()


@pytest.mark.parametrize("path", ["/api/summary", "/api/scoreboard", "/api/jobs", f"/api/jobs/{JID}", f"/api/jobs/{JID}/draft"])
def test_the_paths_the_proxy_forwards_pass(fo, path):
    assert vpath(fo, path)[1]


@pytest.mark.parametrize("path", ["/api/scoreboard/models", "/api/scoreboard?kind=code", "/api/jobs?x=1", "/api/summary/", "/API/summary", "/api/summary\n", "/api/sum mary",
                                  "/api/jobs/not-an-id"])
def test_the_paths_the_proxy_does_not_forward_are_blocked(fo, path):
    text, ok = vpath(fo, path)
    assert not ok and "BLOCK" in text


def test_the_check_uses_the_running_proxy_regex_not_a_copy(fo, monkeypatch):
    assert not vpath(fo, "/api/zzz")[1]
    import re
    monkeypatch.setattr(sv, "API", re.compile(r"^/api/(zzz)$"))
    assert vpath(fo, "/api/zzz")[1]


def test_via_proxy_belongs_to_the_ledger_side(fo):
    fo.write(items=[{"n": 1, "paths": [{"side": "viewer-api", "path": "/api/summary", "via_proxy": True}]}, {"n": 2}])
    blocked(fo, "via_proxy belongs to side ledger")


# ---- paths in the text ----------------------------------------------------------------------------------------------------------

DECL = [{"n": 1, "paths": [{"side": "viewer-api", "path": "/api/scoreboard"}]}, {"n": 2}]


@pytest.mark.parametrize("line", ["See /api/scoreboard.", "(/api/scoreboard)", "`/api/scoreboard`,", '"/api/scoreboard"', "/api/scoreboard: the totals", "GET /api/scoreboard"])
def test_punctuation_around_a_declared_path_is_not_a_finding(fo, line):
    with_text(fo, line, items=DECL)
    assert fo.check()[1]


def test_a_forwarded_path_that_the_text_names_but_the_item_does_not_declare_is_still_blocked(fo):
    with_text(fo, "The viewer reads /api/scoreboard.")
    blocked(fo, "/api/scoreboard but it is not in this item's paths")


@pytest.mark.parametrize("line", ["Call /api/jobs/<id>/draft", "Call /api/jobs/${id}/draft", "Call /api/jobs/:id/draft", "Call /api/jobs/{id}/draft"])
def test_a_templated_path_is_a_warning_not_a_block(fo, line):
    with_text(fo, line)
    text, ok = fo.check()
    assert ok and any(l.startswith("WARN") and "/api/jobs/" in l for l in text.splitlines())


def test_a_file_path_with_api_in_it_is_not_a_path(fo):
    with_text(fo, "Edit src/api/client.js and the module path ledger/api.py.")
    assert fo.check()[1]


# ---- fields ------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("ref", ["JOB_FIELDS.max_usd", "STAGE_FIELDS.usd", "LOG_FIELDS.what", "EVENT_FIELDS.llm_call.usd_nano", "JOB_FIELDS.title", "JOB_FIELDS.stages"])
def test_published_fields_pass(fo, ref):
    fo.write(items=[{"n": 1, "fields": [ref]}, {"n": 2}])
    assert fo.check()[1]


@pytest.mark.parametrize("ref", ["JOB_FIELDS.repo", "JOB_FIELDS.as_is", "JOB_FIELDS.commit", "EVENT_FIELDS.llm_call.nope", "EVENT_FIELDS.nope.x", "FOO.bar", "max_usd"])
def test_fields_the_snapshot_does_not_publish_are_blocked(fo, ref):
    fo.write(items=[{"n": 1, "fields": [ref]}, {"n": 2}])
    blocked(fo, f"field {ref}")


def test_the_check_uses_the_running_tables(fo, monkeypatch):
    fo.write(items=[{"n": 1, "fields": ["JOB_FIELDS.zzz"]}, {"n": 2}])
    assert not fo.check()[1]
    monkeypatch.setitem(sd.JOB_FIELDS, "zzz", None)
    assert fo.check()[1]


def test_what_the_snapshot_publishes_for_a_job_is_covered_by_the_tables_and_the_extras():
    raw = {"job": JID, "kind": "code", "state": "APPLIED", "created_at": "2026-11-12T05:31:07Z", "max_usd": 1.0, "inputs": {"issue": "A title\nbody"}, "stages": {},
           "log": [{"at": "2026-11-12T05:31:07Z", "what": "created"}]}
    out = sd.project_job(raw, JID)
    assert set(out) <= set(sd.JOB_FIELDS) | rp.PUBLISHED_EXTRA["JOB_FIELDS"], set(out) - set(sd.JOB_FIELDS)


# ---- the folder and its input ---------------------------------------------------------------------------------------------------

def test_the_same_validator_as_queue_new_refuses_the_same_things(fo, qe):
    qe.cfg["issue_writer"]["repos"]["argus"] = {"path": str(rj.ROOT), "environment": tq.ENV}
    for bad, why in (({"repo": "argus"}, "never runs on the Argus checkout"), ({"repo": "nope"}, "is not one of issue_writer.repos"), ({"max_usd": 5.01}, "at most"),
                     ({"max_usd": 0.5}, "less than one job's cap"), ({"commit": "0" * 40}, "rev-parse|repository")):
        fo.write(**bad)
        text, ok = fo.check()
        assert not ok and "BLOCK" in text
        with pytest.raises(rj.Refused):
            fo.approve()
    fo.write()
    fo.write(commit=tq.git(qe.repo, "rev-parse", "HEAD"))
    assert fo.check()[1]


def test_a_commit_that_is_not_head_is_blocked(fo, qe):
    fo.write(commit="0" * 40)
    blocked(fo, "repository")
    first = tq.git(qe.repo, "rev-parse", "HEAD")
    tq.git(qe.repo, "commit", "-q", "--allow-empty", "-m", "later")
    fo.write(commit=first)
    blocked(fo, "HEAD")


def test_an_unfinished_queue_on_the_repository_blocks_the_check_and_the_approval(fo, qe):
    qe.new()
    blocked(fo, "is not finished")
    with pytest.raises(rj.Refused, match="not finished"):
        fo.approve()


@pytest.mark.parametrize("mut,why", [
    (lambda d: (d / "issues.json").write_text("not json"), "not valid"),
    (lambda d: (d / "issue-2.md").unlink(), "issue-2.md"),
    (lambda d: (d / "extra.txt").write_text("x"), "unexpected entries"),
    (lambda d: (d / "issue-1.md").write_bytes(b"\xff\xfe bad"), "UTF-8"),
    (lambda d: (d / "issue-1.md").write_text("x" * 20000), "larger than"),
    (lambda d: (d / "issue-2.md").write_text("  "), "is empty"),
    (lambda d: (d / "PRD.md").write_text("x" * 300000), "larger than"),
])
def test_a_damaged_folder_is_refused(fo, mut, why):
    mut(fo.dir)
    text, ok = fo.check()
    assert not ok and why in text
    with pytest.raises(rj.Refused):
        fo.approve(sha="0" * 12)


def test_a_symlink_in_the_folder_is_never_followed(fo, tmp_path):
    secret = tmp_path / "secret.md"
    secret.write_text("a secret " * 5)
    (fo.dir / "issue-2.md").unlink()
    os.symlink(secret, fo.dir / "issue-2.md")
    text, ok = fo.check()
    assert not ok and "issue-2.md" in text


@pytest.mark.parametrize("spec", [{"extra": 1}, {"items": [{"n": 1, "x": 1}, {"n": 2}]}, {"items": [{"n": 1}, {"n": 3}]}])
def test_unknown_keys_and_an_n_that_jumps_are_blocked(fo, spec):
    body = json.loads((fo.dir / "issues.json").read_text())
    body.update(spec)
    (fo.dir / "issues.json").write_text(json.dumps(body))
    assert not fo.check()[1]


def test_the_sha_covers_where_the_bytes_are(fo):
    a = fo.sha()
    one, two = (fo.dir / "issue-1.md").read_bytes(), (fo.dir / "issue-2.md").read_bytes()
    (fo.dir / "issue-1.md").write_bytes(two)
    (fo.dir / "issue-2.md").write_bytes(one)
    assert fo.sha() != a


# ---- approve ----------------------------------------------------------------------------------------------------------------------

def test_approve_makes_a_pending_queue_with_the_prd_recorded_and_no_money_goes(fo, qe):
    q = fo.approve()
    assert q["approved"] is None and q["prd"] == {"sha": fo.sha(), "dir": str(fo.dir.resolve())} and qe.status(q) == "PENDING"
    assert [json.loads((qe.queues / q["id"] / "queue.json").read_text())["items"][i]["job"] for i in (0, 1)] == [None, None] and qe.calls == []
    with pytest.raises(rj.Refused, match="not approved"):
        qe.step(q)


def test_approve_wants_the_sha_the_folder_has(fo, qe):
    for bad in ("0" * 12, fo.sha()[:11]):
        with pytest.raises(rj.Refused, match="not the"):
            fo.approve(sha=bad)
    assert not qe.queues.exists() or not list(qe.queues.glob("q*"))
    assert fo.approve(sha=fo.sha()[:12])["prd"]["sha"] == fo.sha()


def test_a_folder_changed_after_the_check_is_not_what_was_approved(fo):
    seen = fo.sha()
    (fo.dir / "issue-1.md").write_text(f"{td.ISSUE}\n\nchanged after the check")
    with pytest.raises(rj.Refused, match="not the"):
        fo.approve(sha=seen[:12])


def test_approve_with_a_block_makes_no_queue_and_no_directory(fo, qe):
    with_text(fo, "Add `GET /scoreboard/models`.")
    with pytest.raises(rj.Refused, match="BLOCK"):
        fo.approve()
    assert not qe.queues.exists() or not list(qe.queues.iterdir()) or all(p.name.startswith(".") for p in qe.queues.iterdir())


def test_the_queue_texts_are_the_bytes_that_were_hashed(fo, qe):
    q = fo.approve()
    d = qe.queues / q["id"]
    assert (d / "issue-1.md").read_text() == (fo.dir / "issue-1.md").read_text().strip()


# ---- the queue's side of it ------------------------------------------------------------------------------------------------------------

def test_a_queue_without_prd_has_the_sha_it_had_before_prd_existed():
    q = {"repo": "/home/ubuntu/argus-ledger", "name": "argus-ledger", "environment": "ledger_py312_up2", "base_commit": "1aeb82d3e220371dd5071d9d398b22c33bf0b83f",
         "max_usd": 3.0, "job_cap_usd": 1.0, "jobs_dir": "/home/ubuntu/Argus-agent/jobs",
         "items": [{"issue_sha256": h} for h in ("c830f3fb4502d5c7b6cfa0c7d600e42ca7f8bd23ac34e151f992c24ad3fecef9", "2754b7109b980833194baa2870c29f19a6aa4e78cc59c5faab864a4876355188",
                                                 "5835aef5f621d06c3a3fd68d206f0e13c78429129cc55a9045050e754a264488")]}
    assert rq.list_sha(q) == "7397b671c4d6f13a2d8550d7a6ac3a7d9aa612923cd13d535d9d54d7186c7294"       # q20261115T175659Z-94a1, approved and run
    assert rq.list_sha({**q, "prd": {"sha": "a" * 64, "dir": "/x"}}) != rq.list_sha(q)


@pytest.mark.parametrize("edit", [lambda q: q.pop("prd"), lambda q: q["prd"].update(sha="b" * 64), lambda q: q.update(prd="x"), lambda q: q["prd"].update(sha="zz")])
def test_the_prd_of_an_approved_queue_cannot_be_changed_or_damaged(fo, qe, edit):
    q = qe.go(fo.approve())
    data = qe.q(q)
    edit(data)
    (qe.queues / q["id"] / "queue.json").write_text(json.dumps(data))
    with pytest.raises(rj.Refused, match="damaged|not approved|changed since"):
        qe.step(q)


def test_an_approved_queue_with_its_prd_still_steps(fo, qe):
    q = qe.go(fo.approve())
    qe.step(q)
    assert len(qe.calls) == 1


# ---- Fable's review of the diff ---------------------------------------------------------------------------------------------------------

def test_a_deeply_nested_issues_json_is_a_finding_not_a_traceback(fo):
    (fo.dir / "issues.json").write_text("[" * 100000 + "]" * 100000)
    text, ok = fo.check()
    assert not ok and "BLOCK" in text


def test_a_nul_in_the_commit_is_a_finding(fo):
    body = json.loads((fo.dir / "issues.json").read_text())
    body["commit"] = "a" * 39 + "\0"
    (fo.dir / "issues.json").write_text(json.dumps(body))
    assert not fo.check()[1]


def test_a_fifo_named_prd_md_does_not_hang_the_check(fo):
    (fo.dir / "PRD.md").unlink()
    os.mkfifo(fo.dir / "PRD.md")
    text, ok = fo.check()
    assert not ok and "not a regular file" in text


def test_a_symlinked_prd_md_is_refused(fo, tmp_path):
    (tmp_path / "other.md").write_text("contract")
    (fo.dir / "PRD.md").unlink()
    os.symlink(tmp_path / "other.md", fo.dir / "PRD.md")
    assert not fo.check()[1]


@pytest.mark.parametrize("line", ["the /api/ routes", "all /api/* routes", "see the /api-docs page", "import x from '@/api/client'", "GET /", "the \\/api\\/ prefix"])
def test_prose_about_the_api_prefix_is_not_a_path(fo, line):
    with_text(fo, line)
    assert fo.check()[1]


@pytest.mark.parametrize("line", ["curl http://127.0.0.1:8710/api/scoreboard/models", "<code>/api/scoreboard/models</code>", "/api/scoreboard/models$", "PUT /scoreboard/models",
                                  "DELETE /jobs/x", "/api/scoreboard/models:list"])
def test_paths_in_urls_markup_and_other_verbs_are_seen(fo, line):
    with_text(fo, line)
    blocked(fo, "is not in this item's paths")


def test_a_declared_template_is_not_a_warning(fo):
    with_text(fo, "Call /api/jobs/<id>/draft", items=[{"n": 1, "paths": [{"side": "viewer-api", "path": "/api/jobs/j20261112_053107_1929/draft"}]}, {"n": 2}])
    text, ok = fo.check()
    assert ok and "WARN  the text names a templated" not in text


@pytest.mark.parametrize("spec", [{"max_usd": True}, {"max_usd": "3.0"}, {"commit": "HEAD"}, {"commit": "abc1234"}])
def test_loose_types_in_issues_json_are_blocked(fo, spec):
    body = json.loads((fo.dir / "issues.json").read_text())
    body.update(spec)
    (fo.dir / "issues.json").write_text(json.dumps(body))
    assert not fo.check()[1]


@pytest.mark.parametrize("n", [True, 1.0])
def test_n_must_be_an_integer(fo, n):
    fo.write(items=[{"n": n}, {"n": 2}])
    assert not fo.check()[1]


def test_a_ledger_path_that_stays_off_the_proxy_still_has_plain_characters(fo):
    fo.write(items=[{"n": 1, "paths": [{"side": "ledger", "path": "/x y\n", "via_proxy": False}]}, {"n": 2}])
    blocked(fo, "space or a control character")


def test_an_unknown_key_in_a_path_object_is_blocked(fo):
    fo.write(items=[{"n": 1, "paths": [{"side": "viewer-api", "path": "/api/summary", "extra": 1}]}, {"n": 2}])
    assert not fo.check()[1]


def test_the_sha_covers_prd_md_and_is_pinned(fo):
    a = fo.sha()
    (fo.dir / "PRD.md").write_text("# PRD\n\nThe contract changed.\n")
    assert fo.sha() != a
    import hashlib
    files = {"PRD.md": b"p", "issues.json": b"j", "issue-1.md": b"a"}
    want = hashlib.sha256(json.dumps([["PRD.md", hashlib.sha256(b"p").hexdigest()], ["issues.json", hashlib.sha256(b"j").hexdigest()],
                                      ["issue-1.md", hashlib.sha256(b"a").hexdigest()]], separators=(",", ":")).encode()).hexdigest()
    assert rp.folder_sha(files) == want


def test_queue_new_refuses_a_damaged_prd_argument_before_writing(qe):
    with pytest.raises(rj.Refused, match="prd must be"):
        qe.new(prd="x")
    assert not list(qe.queues.glob("q*"))


def test_the_command_line_exits_1_on_a_block_and_0_on_a_sound_folder(fo, qe, monkeypatch, capsys):
    sys.path.insert(0, str(tr.ROOT / "scripts"))
    import argus
    monkeypatch.setattr(argus, "load_config", lambda *_a, **_k: qe.cfg)
    monkeypatch.setattr(argus, "sandbox_cfg", lambda *_a, **_k: {})
    base = ["--jobs-dir", str(qe.jobs), "--queues-dir", str(qe.queues), "prd"]
    assert argus.main([*base, "check", str(fo.dir)], deps=qe.env.deps) == 0
    assert argus.main([*base, "approve", str(fo.dir), "--sha", fo.sha()[:12]], deps=qe.env.deps) == 0
    assert "PENDING" in capsys.readouterr().out
    with_text(fo, "Add `GET /scoreboard/models`.")
    assert argus.main([*base, "check", str(fo.dir)], deps=qe.env.deps) == 1
