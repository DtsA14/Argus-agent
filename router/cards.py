"""Read-only cards for the chat (docs/reviews/SPEC_CHAT_CARDS.md rev 1, T2): a PRD job, a queue, and the examples of an issue, with the
status of every example as the machine recorded it.

Nothing here writes, starts a process, calls a model or runs git. Every file is read one name at a time through a directory file
descriptor, never through a symlink, never a FIFO, never past its limit. A status is shown only when the file it was computed for is the
file read now (the sha of the issue, the sha of the folder, the digest of the examples); otherwise `results` is None and no status is
shown at all. Every string goes through the chat's own `scrub`; a JSON value is written as one scrubbed string; a key pattern anywhere in a
card withholds its examples.

Origin of a field: `mesin` (a value the harness validated), `model` (text or code a model wrote), `keluaran-kode` (what the code of an
example printed). The cards say which (the page marks `model` text); `pass` only says the example's own code reported a match in the
sandbox, and that code is written by a model and can forge it (SPEC_EXAMPLE_GATE 5).
"""
import hashlib
import json
import os
import re
import stat
from pathlib import Path

from codetask import examples as ex
from router import example_gate as eg
from router import prd as rp
from router import queue as rq
from router import stage_data as sd

UI_ID = re.compile(r"j[0-9]{8}_[0-9]{6}_[0-9a-f]{4}")
TURN = re.compile(r"w[0-9]{1,3}")
JOB_JSON_MAX = 4 * 1024 * 1024
DOC_MAX = 64 * 1024                  # PRD.md, issues.json, an examples file
QUEUE_MAX = 100 * 1024
ISSUE_MAX = sd.TEXT_MAX
SCAN_JOBS, SCAN_QUEUES, ROWS_MAX, SCAN_BYTES = 200, 200, 50, 32 * 1024 * 1024
ITEMS_MAX = 8
NOT_RUN = "not_run"
NOT_RUN_WHY = "dijalankan saat job code item ini mulai"
KINDS = ("none", "stale", "pending", "error", "skipped", "results")
OPEN_DIR = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
OPEN_FILE = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK


def _open_dir(name, dir_fd=None):
    return os.open(name, OPEN_DIR, dir_fd=dir_fd)


def _read(dir_fd, name, limit):
    """The bytes of regular file `name` in dir_fd: never through a symlink, never a FIFO (O_NONBLOCK, then fstat), at most `limit`
    bytes; FileNotFoundError when it is not there, OSError for anything else wrong with it."""
    fd = os.open(name, OPEN_FILE, dir_fd=dir_fd)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise OSError(f"{name} is not a regular file")
        if st.st_size > limit:
            raise OSError(f"{name} is larger than {limit} bytes")
        with os.fdopen(fd, "rb", closefd=False) as f:
            raw = f.read(limit + 1)
        if len(raw) > limit:
            raise OSError(f"{name} grew past {limit} bytes")
        return raw
    finally:
        os.close(fd)


def _exists(dir_fd, name):
    try:
        os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
        return True
    except OSError:
        return False


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


class Cards:
    def __init__(self, jobs_dir, queues_dir, scrub):
        self.jobs_dir, self.queues_dir, self.scrub = Path(jobs_dir), Path(queues_dir), scrub

    # ---- strings and JSON values ------------------------------------------------------------------------------------------

    def s(self, v):
        return self.scrub(v) if isinstance(v, str) else ""

    def j(self, v):
        """A JSON value written as one scrubbed string (an `actual`, an `expect`, the overrides)."""
        try:
            return self.scrub(json.dumps(v, sort_keys=True, ensure_ascii=False))
        except (TypeError, ValueError, RecursionError):
            return ""

    # ---- opening ------------------------------------------------------------------------------------------------------------

    def _job_dir(self, job_id):
        """(sfd, jfd) of a job directory, or None; the caller closes both."""
        if not isinstance(job_id, str) or not UI_ID.fullmatch(job_id):
            return None
        try:
            sfd = _open_dir(str(self.jobs_dir))
        except OSError:
            return None
        try:
            return sfd, _open_dir(job_id, sfd)
        except OSError:
            os.close(sfd)
            return None

    def _job_json(self, jfd):
        try:
            data = json.loads(_read(jfd, "job.json", JOB_JSON_MAX))
        except (OSError, ValueError, RecursionError):
            return None
        return data if isinstance(data, dict) else None

    def read_job(self, job_id, kind):
        """job.json of job `job_id` when it is a job of `kind` with an `inputs` object, else None."""
        d = self._job_dir(job_id)
        if d is None:
            return None
        try:
            data = self._job_json(d[1])
        finally:
            for fd in d:
                os.close(fd)
        if data is None or data.get("kind") != kind or not isinstance(data.get("inputs"), dict):
            return None
        return data

    # ---- examples -----------------------------------------------------------------------------------------------------------

    def _calls(self, text):
        """(calls, examples) of the argus-examples block of an issue text: what the code job will read."""
        present, parsed, problems = eg.extract(text)
        if not present or problems:
            return [], []
        return [{"id": e["id"], "tier": e["tier"], "setup": self.s(e["setup"]), "run": self.s(e["run"]),
                 **({"expect": self.j(e["expect"])} if "expect" in e else {"raises": self.s(e["raises"])}),
                 **({"overrides": self.j(e["overrides"])} if e.get("overrides") else {}), "says": self.s(e["says"])}
                for e in parsed], parsed

    def _result_rows(self, results, where):
        out = []
        for r in results:
            row = {"id": r["id"], "tier": r["tier"], "status": r["status"], "where": where}
            for k in ("actual", "base_actual"):
                if k in r:
                    row[k] = self.j(r[k])
            out.append(row)
        return out

    def examples(self, text, stored, bound):
        """The examples card of one issue. text: the issue text read now (None: not readable). stored: what the writer's turn kept
        ({examples, results, no_examples, note, tier_moves}) or None. bound: the file read now is the one the stored results belong to."""
        card = {"calls": [], "results": None, "why": None, "no_examples": None, "note": None, "tier_moves": []}
        if text is None:
            card["why"] = "teks issue tidak terbaca"
            return card
        calls, parsed = self._calls(text)
        card["calls"] = calls
        if not isinstance(stored, dict):
            if not calls:
                card["why"] = "tanpa contoh"
            else:                       # an item the writer did not run (a PRD item after the first): its code job will
                card["why"] = NOT_RUN_WHY
                card["results"] = [{"id": c["id"], "tier": c["tier"], "status": NOT_RUN, "where": "belum"} for c in calls]
            return card
        if stored.get("absent"):
            card["why"] = "dari sebelum gerbang contoh"
            return card
        card["no_examples"] = self.s(stored["no_examples"]) if isinstance(stored.get("no_examples"), str) else None
        card["note"] = eg.RUNNER_NOTE if stored.get("note") else None
        card["tier_moves"] = [{"id": m["id"], "from": m["from"], "to": m["to"]} for m in stored.get("tier_moves") or []
                              if isinstance(m, dict) and isinstance(m.get("id"), str) and ex.ID.fullmatch(m["id"])
                              and m.get("from") in ex.TIERS and m.get("to") in ex.TIERS]
        results = stored.get("results")
        if not isinstance(results, list) or not results:
            return card
        ids = [c["id"] for c in calls]
        same = eg.digest(parsed) == eg.digest(stored.get("examples") if isinstance(stored.get("examples"), list) else [])
        clean = [eg._result(r, set(ids)) for r in results]
        if not bound or not same:
            card["why"] = "berkas tidak cocok dengan hasil"
        elif any(r is None for r in clean) or len({r["id"] for r in clean}) != len(clean) or {r["id"] for r in clean} - set(ids):
            card["why"] = "id tidak cocok"
        else:
            card["results"] = self._result_rows(clean, "penulis")
        return card

    def code_results(self, code_job_id, parsed):
        """{at_base, after_agent} of a code job from its two files, each {kind, why, results}: nothing is read when there is no job."""
        out = {"at_base": None, "after_agent": None}
        d = self._job_dir(code_job_id) if code_job_id else None
        if d is None or not parsed:
            return out
        sfd, jfd = d
        try:
            data = self._job_json(jfd)
            if data is None or data.get("kind") != "code":
                return out
            snap = (data.get("intake") or {}).get("snapshot_sha256")
            if isinstance(snap, str):
                out["at_base"] = self._stored(jfd, eg.INTAKE_FILE, eg.intake_key(snap, parsed), parsed, "intake")
            sids = sorted((k for k, st in (data.get("stages") or {}).items() if isinstance(st, dict) and st.get("kind") == "agent"
                           and re.fullmatch(r"a[0-9]{1,3}", k)), key=lambda k: int(k[1:]))
            if sids:
                patch = (((data["stages"][sids[-1]]).get("review")) or {}).get("patch_sha256")
                if isinstance(patch, str):
                    out["after_agent"] = self._stored(jfd, f"examples_audit_{sids[-1]}.json", eg.audit_key(patch, parsed), parsed,
                                                      "audit")
        finally:
            os.close(jfd)
            os.close(sfd)
        return out

    def _stored(self, jfd, name, key, parsed, where):
        try:
            raw = _read(jfd, name, DOC_MAX)
        except FileNotFoundError:
            return {"kind": "none", "why": None, "results": None}
        except OSError:
            return {"kind": "error", "why": None, "results": None}
        kind, val = eg.parse_stored(raw.decode("utf-8", "replace"), key, parsed)
        return {"kind": kind, "why": self.s(val) if isinstance(val, str) else None,
                "results": self._result_rows(val, where) if kind == "results" else None}

    def withhold_keys(self, card):
        """A key pattern anywhere in the card (a key split across `setup` and `run`) withholds every examples field of it."""
        if not sd.KEY.search(json.dumps(card, ensure_ascii=False).encode("utf-8")):
            return card

        def strip(o):
            if isinstance(o, dict):
                return {k: ({"withheld": True} if k == "examples" else strip(v)) for k, v in o.items()}
            if isinstance(o, list):
                return [strip(v) for v in o]
            return o
        return strip(card)

    # ---- the issue job's examples (a field of GET /api/issues/<job>) ---------------------------------------------------------

    def issue_examples(self, data, issue_raw):
        """The examples card of an issue job: the writer's message whose issue_sha256 is the job's (never conversation[-1]), bound to the
        issue file; None when the job has no issue yet. Sent on to the code job's results once the job is handed off."""
        want = data.get("issue_sha256")
        if not isinstance(want, str) or issue_raw is None:
            return None
        msg = next((m for m in reversed(data.get("conversation") or []) if isinstance(m, dict) and m.get("from") == "writer"
                    and m.get("issue_sha256") == want), None)
        if msg is None:
            return None
        text = issue_raw.decode("utf-8", "replace")
        card = self.examples(text, msg.get("examples") if msg.get("examples") else {"absent": True}, _sha(issue_raw) == want)
        handoff = (data.get("handoff") or {}).get("job")
        if isinstance(handoff, str):
            card.update(self.code_results(handoff, self._calls(text)[1]))
        return self.withhold_keys(card)

    # ---- PRD jobs -------------------------------------------------------------------------------------------------------------

    def _folder(self, jfd, turn, items):
        """({name: bytes}, why) of the folder prd-<turn>: PRD.md, issues.json and issue-1..N.md, read here, or (None, why)."""
        if not isinstance(turn, str) or not TURN.fullmatch(turn):
            return None, "nama giliran tidak sah"
        try:
            dfd = _open_dir(f"prd-{turn}", jfd)
        except OSError:
            return None, "folder tidak terbaca"
        try:
            files = {"PRD.md": _read(dfd, "PRD.md", DOC_MAX), "issues.json": _read(dfd, "issues.json", DOC_MAX)}
            for n in range(1, min(items, ITEMS_MAX) + 1):
                files[f"issue-{n}.md"] = _read(dfd, f"issue-{n}.md", ISSUE_MAX)
            files["__superseded__"] = b"1" if _exists(dfd, "SUPERSEDED") else b""
        except OSError:
            return None, "berkas folder tidak terbaca atau terlalu besar"
        finally:
            os.close(dfd)
        return files, None

    def prd(self, job_id):
        d = self._job_dir(job_id)
        if d is None:
            return None
        sfd, jfd = d
        try:
            data = self._job_json(jfd)
            if data is None or data.get("kind") != "prd" or not isinstance(data.get("inputs"), dict):
                return None
            i = data["inputs"]
            turns = [t for t in data.get("prd_turns") or [] if isinstance(t, dict)]
            card = {"id": job_id, "state": self.s(data.get("state")), "repo": self.s(i.get("repo_name")),
                    "inputs_commit12": self.s(str(i.get("commit"))[:12]), "turn": None, "commit12": None, "stale": None,
                    "superseded": None, "folder_sha12": None, "prd_md": None, "items": [], "warnings": [], "questions": [],
                    "money": {"job_cap": data.get("max_usd") if isinstance(data.get("max_usd"), (int, float)) else None,
                              "spent": self._spent(data), "queue_usd": None}, "queues": [], "why": None}
            writer = [m for m in data.get("conversation") or [] if isinstance(m, dict) and m.get("from") == "writer"]
            if writer and isinstance(writer[-1].get("questions"), list):
                card["questions"] = [self.s(q) for q in writer[-1]["questions"][:10]]
            if not turns:
                card["why"] = "belum ada folder"
                return card
            t = turns[-1]
            n_items = t["items"] if isinstance(t.get("items"), int) and 0 < t["items"] <= ITEMS_MAX else 0
            card.update(turn=self.s(t.get("turn")), commit12=self.s(str(t.get("commit"))[:12]),
                        stale=t.get("commit") != i.get("commit"), folder_sha12=self.s(str(t.get("folder_sha"))[:12]),
                        warnings=[self.s(w) for w in (t.get("warnings") or [])[:20]])
            card["money"]["queue_usd"] = t.get("max_usd") if isinstance(t.get("max_usd"), (int, float)) else None
            files, why = self._folder(jfd, t.get("turn"), n_items)
            if files is None:
                card["why"] = why
                return card
            card["superseded"] = bool(files.pop("__superseded__"))
            bound = rp.folder_sha(files) == t.get("folder_sha") if n_items else False
            card["prd_md"] = self.s(files["PRD.md"].decode("utf-8", "replace"))
            per_item = t.get("examples") if isinstance(t.get("examples"), list) else [None] * n_items
            for n in range(1, n_items + 1):
                raw = files.get(f"issue-{n}.md")
                text = raw.decode("utf-8", "replace") if raw is not None else None
                stored = per_item[n - 1] if n - 1 < len(per_item) and per_item[n - 1] else None
                ex_card = self.examples(text, stored if stored is not None else ({"absent": True} if "examples" not in t else None), bound)
                touches = (t.get("touches") or [])[n - 1] if n - 1 < len(t.get("touches") or []) else []
                creates = (t.get("creates") or [])[n - 1] if n - 1 < len(t.get("creates") or []) else []
                clashes = (t.get("clashes") or [])[n - 1] if n - 1 < len(t.get("clashes") or []) else []
                card["items"].append({
                    "n": n, "title": self.s((text or "").split("\n", 1)[0]) if text is not None else "",
                    "text": self.s(eg.without_block(text)) if text is not None else "",
                    "touches": [self.s(x) for x in touches if isinstance(x, str)][:8],
                    "creates": [self.s(x) for x in creates if isinstance(x, str)][:8],
                    "clashes": [{"file": self.s(c.get("file")), "line": c.get("line") if isinstance(c.get("line"), int) else 0,
                                 "why": self.s(c.get("why"))} for c in clashes if isinstance(c, dict)][:10],
                    "examples": ex_card})
            card["queues"] = [r["id"] for r in self._queue_rows(derive=False)[0] if r.get("prd_job") == job_id]
            return self.withhold_keys(card)
        finally:
            os.close(jfd)
            os.close(sfd)

    @staticmethod
    def _spent(data):
        total = 0.0
        for st in (data.get("stages") or {}).values():
            if isinstance(st, dict) and isinstance(st.get("usd"), (int, float)) and not isinstance(st["usd"], bool):
                total += st["usd"]
        return round(total, 6)

    # ---- queues -----------------------------------------------------------------------------------------------------------------

    def _queues_fd(self):
        try:
            return _open_dir(str(self.queues_dir))
        except OSError:
            return None

    def _queue_json(self, qfd, qid):
        """(q, qdir_fd) of queue qid, or None; the caller closes the directory."""
        if not isinstance(qid, str) or not rq.QUEUE_ID.fullmatch(qid):
            return None
        try:
            dfd = _open_dir(qid, qfd)
        except OSError:
            return None
        try:
            q = json.loads(_read(dfd, "queue.json", QUEUE_MAX))
        except (OSError, ValueError, RecursionError):
            os.close(dfd)
            return None
        if not rq.shape_ok(q, qid):
            os.close(dfd)
            return None
        return q, dfd

    def _same_jobs_dir(self, q):
        try:
            return os.path.realpath(q["jobs_dir"]) == os.path.realpath(self.jobs_dir)
        except (OSError, ValueError, KeyError):
            return False

    def _prd_job_of(self, q):
        """The PRD job a queue was made from: the parent directory name of q.prd.dir when its grandparent is the chat's jobs dir; the
        directory itself is never opened."""
        p = (q.get("prd") or {}).get("dir")
        if not isinstance(p, str):
            return None
        path = Path(p)
        if UI_ID.fullmatch(path.parent.name) and os.path.realpath(path.parent.parent) == os.path.realpath(self.jobs_dir):
            return path.parent.name
        return None

    def _queue_rows(self, derive=True):
        """([row], truncated) of the queues of the queues directory, newest first."""
        qfd = self._queues_fd()
        if qfd is None:
            return [], False
        rows, truncated = [], False
        try:
            names = sorted((n for n in os.listdir(qfd) if rq.QUEUE_ID.fullmatch(n)), reverse=True)
            if len(names) > SCAN_QUEUES:
                names, truncated = names[:SCAN_QUEUES], True
            for qid in names:
                got = self._queue_json(qfd, qid)
                if got is None:
                    continue
                q, dfd = got
                os.close(dfd)
                ok = self._same_jobs_dir(q)
                state = self._derive(q)[0] if ok and derive else None
                rows.append({"id": qid, "kind": "queue", "title": self.s(q["name"]), "state": state, "repo": self.s(q["repo"]),
                             "at": _queue_time(qid), "items": len(q["items"]) if ok else None,
                             **({} if ok else {"why": "jobs dir lain"}), "prd_job": self._prd_job_of(q) if ok else None})
        finally:
            os.close(qfd)
        return rows, truncated

    def _derive(self, q):
        """(state, next, per-item facts) of a queue as `rq.derive` would say it, computed here: the item jobs are read through file
        descriptors from the chat's jobs directory, and nothing runs git, so the HEAD of the repository and the money left are not
        checked (the card says so). The CLI lines `derive` returns as `actions` are not produced."""
        if q.get("closed"):
            return "CLOSED", "antrean ditutup", [None] * len(q["items"])
        if not q.get("approved"):
            return "PENDING", "menunggu persetujuan antrean (di terminal)", [None] * len(q["items"])
        facts, commit, state, nxt = [], q["base_commit"], None, None
        for item in q["items"]:
            job = self.read_job(item["job"], "code") if isinstance(item.get("job"), str) and item["job"] else None
            info = {"job": item.get("job") if job is not None else None, "job_state": None, "applied": None, "spent": None}
            if job is not None:
                i = job.get("inputs") or {}
                info.update(job_state=self.s(job.get("state")), spent=self._spent(job))
                bound = (isinstance(i.get("issue"), str) and _sha(i["issue"].encode("utf-8")) == item["issue_sha256"]
                         and i.get("commit") == commit and i.get("repo") == q["repo"])
                if not bound:
                    if state is None:
                        state, nxt = "STOPPED", f"item {item['n']}: job {self.s(job.get('job'))} bukan issue antrean ini di commit ini"
                    facts.append(info)
                    continue
            facts.append(info)
            if state is not None:
                continue
            if job is None or (not job.get("stages") and job.get("state") in ("NEW", "ABANDONED", "BLOCKED")):
                if job is not None and job.get("state") == "BLOCKED":
                    state, nxt = "STOPPED", f"item {item['n']}: job {self.s(job.get('job'))} BLOCKED sebelum tahap pertama"
                else:
                    state, nxt = "WAITING", f"item {item['n']} bisa mulai (HEAD dan uang tidak diperiksa dari chat)"
                continue
            st = job.get("state")
            if st == "APPLIED":
                commit_new, as_is = None, None
                for e in reversed(job.get("log") or []):
                    if isinstance(e, dict) and e.get("what") == "state" and e.get("new") == "APPLIED":
                        commit_new, as_is = e.get("commit"), e.get("as_is")
                        break
                if not isinstance(commit_new, str) or as_is is not True:
                    state, nxt = "STOPPED", f"item {item['n']}: APPLIED tetapi commitnya tidak tercatat sebagai patch"
                else:
                    info["applied"] = self.s(commit_new[:12])
                    commit = commit_new
                continue
            if st in rq.FAILED:
                state, nxt = "STOPPED", f"item {item['n']}: job {self.s(job.get('job'))} {self.s(st)}"
            elif st == "AWAITING_APPROVAL":
                state, nxt = "WAITING", f"item {item['n']}: draf menunggu approve"
            elif st == "REVIEW_READY":
                state, nxt = "WAITING", f"item {item['n']}: paket review menunggu dibaca dan di-apply"
            else:
                state, nxt = "WAITING", f"item {item['n']}: job {self.s(job.get('job'))} {self.s(st)}"
        return (state or "DONE"), (nxt or ""), facts

    def queue(self, qid):
        qfd = self._queues_fd()
        if qfd is None:
            return None
        try:
            got = self._queue_json(qfd, qid)
            if got is None:
                return None
            q, dfd = got
            try:
                ok = self._same_jobs_dir(q)
                card = {"id": qid, "state": None, "repo": self.s(q["repo"]), "jobs_dir_ok": ok, "items": None, "next": None,
                        "closed": self.s((q.get("closed") or {}).get("note")) if q.get("closed") else None,
                        "why": None if ok else "jobs dir lain"}
                if not ok:
                    return card
                state, nxt, facts = self._derive(q)
                card.update(state=state, next=self.s(nxt), items=[])
                for item, info in zip(q["items"], facts):
                    n = item["n"]
                    text, matches = None, False
                    if isinstance(n, int) and 1 <= n <= ITEMS_MAX:
                        try:
                            raw = _read(dfd, f"issue-{n}.md", ISSUE_MAX)
                            text, matches = raw.decode("utf-8", "replace"), _sha(raw) == item["issue_sha256"]
                        except OSError:
                            pass
                    shown = text if matches else None
                    calls, parsed = self._calls(shown) if shown is not None else ([], [])
                    ex_card = {"calls": calls, "results": None,
                               "why": NOT_RUN_WHY if not info or not info.get("job") else None, "status": None}
                    if shown is None:
                        ex_card["why"] = "berkas berubah"
                    code = self.code_results(info.get("job") if info else None, parsed)
                    ex_card.update(code)
                    if not info or not info.get("job"):
                        ex_card["results"] = [{"id": c["id"], "tier": c["tier"], "status": NOT_RUN, "where": "belum"} for c in calls]
                    card["items"].append({
                        "n": n if isinstance(n, int) else 0, "title": self.s(shown.split("\n", 1)[0]) if shown is not None else "",
                        "text_matches": matches, "job": info.get("job") if info else None,
                        "job_state": info.get("job_state") if info else None, "applied": info.get("applied") if info else None,
                        "spent": info.get("spent") if info else None, "examples": ex_card})
                return self.withhold_keys(card)
            finally:
                os.close(dfd)
        finally:
            os.close(qfd)

    # ---- the list -----------------------------------------------------------------------------------------------------------------

    def listing(self):
        rows, truncated, spent = [], False, 0
        try:
            sfd = _open_dir(str(self.jobs_dir))
        except OSError:
            sfd = None
        if sfd is not None:
            try:
                names = sorted((n for n in os.listdir(sfd) if UI_ID.fullmatch(n)), reverse=True)
                if len(names) > SCAN_JOBS:
                    names, truncated = names[:SCAN_JOBS], True
                for jid in names:
                    try:
                        jfd = _open_dir(jid, sfd)
                    except OSError:
                        continue
                    try:
                        raw = _read(jfd, "job.json", JOB_JSON_MAX)
                        spent += len(raw)
                        if spent > SCAN_BYTES:
                            truncated = True
                            break
                        data = json.loads(raw)
                    except (OSError, ValueError, RecursionError):
                        continue
                    finally:
                        os.close(jfd)
                    if not isinstance(data, dict) or data.get("kind") != "prd" or not isinstance(data.get("inputs"), dict):
                        continue
                    conv = [m for m in data.get("conversation") or [] if isinstance(m, dict) and m.get("from") == "human"]
                    first = (conv[0].get("text") if conv and isinstance(conv[0].get("text"), str) else "").split("\n", 1)[0]
                    turns = [t for t in data.get("prd_turns") or [] if isinstance(t, dict)]
                    rows.append({"id": jid, "kind": "prd", "title": self.s(first), "state": self.s(data.get("state")),
                                 "repo": self.s(data["inputs"].get("repo_name")), "at": self.s(data.get("created_at")),
                                 "items": turns[-1].get("items") if turns and isinstance(turns[-1].get("items"), int) else None})
            finally:
                os.close(sfd)
        qrows, qtrunc = self._queue_rows()
        rows += [{k: v for k, v in r.items() if k != "prd_job"} for r in qrows]
        rows.sort(key=lambda r: (r["at"] or "", r["id"]), reverse=True)
        return {"rows": rows[:ROWS_MAX], "truncated": truncated or qtrunc or len(rows) > ROWS_MAX}


def _queue_time(qid):
    """The creation time written in a queue id (q20261117T044144Z-ab12) as an ISO timestamp, for the list's order."""
    m = re.fullmatch(r"q([0-9]{4})([0-9]{2})([0-9]{2})T([0-9]{2})([0-9]{2})([0-9]{2})Z-[0-9a-f]{4}", qid)
    return "{}-{}-{}T{}:{}:{}Z".format(*m.groups()) if m else ""
