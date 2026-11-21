"""The install card of the plain-language approval (docs/reviews/SPEC_KARTU_SETUJU.md sections 2, 3, 5 and 6, PR 5b of T3): for one code job and one
patch, what the change is for and what it cost, the examples as numbers with the audit's proof words, the files the patch touches with the machine's
marks, what the two Claude readers said (marked as Claude, not human, not proof), and the conditions (a) to (i) under which block C ("install?") is
open. Read only, like the plan card: files one name at a time through directory descriptors, never through a symlink; it runs nothing, starts no
process, calls no model and writes nothing. There is no button here: the decision "install" is a later change (T4).

The checks follow what `argus apply` itself refuses, read from the same files, so the card and the command line cannot disagree about whether a
patch may go in: (a) the examples on the base, (b) the audit on the patch, (c) the review package, (d) and (e) the draft's approval, (f) the patch
reader's note for these very bytes, (g) one sha for the review, the provenance and the patch on disk, (h) at least one example of the new
behaviour, (i) the domain reader's note through the chain queue -> PRD folder -> item -> digest. A condition that does not apply (an issue that is not
an item of a PRD queue has no domain reader) is `null` and does not close C; every `false` does, and the card says what is missing. The card never
says a patch is safe.
"""
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from types import SimpleNamespace

from acceptance.contract import matches
from codetask import examples as ex
from router import card_numbers as cn
from router import example_gate as eg
from router import examples_read as er
from router import patch_read as pr
from router.approve_cards import DOMAIN_LABEL, FIXED_LINE
from router.cards import DOC_MAX, ISSUE_MAX, OPEN_FILE, _open_dir, _read

READER_TESTS = Path(__file__).resolve().parent.parent / "verification" / "reader_tests.json"
PATCH_LABEL = "Ini pernyataan pembaca patch (dua model Argus atau sesi Claude), bukan bukti bahwa patch dibaca, dan bukan dibaca manusia."
PATCH_MAX = 16 * 1024 * 1024
FILES_MAX = 60
RUN_A = re.compile(r"j[0-9]{8}_[0-9]{6}_[0-9a-f]{4}-a[0-9]{1,3}")
SID = re.compile(r"a[0-9]{1,3}")
SHA = re.compile(r"[0-9a-f]{64}")
PROTECTED_MARK = "dilindungi repo (.argus/protected)"
OUTSIDE_MARK = "di luar yang disebut issue (touches/creates)"
LABELS = {"a": "contoh di dasar tidak gagal", "b": "audit: contoh benar pada kode akhir", "c": "paket review valid",
          "d": "tes lama yang bentrok sudah dilonggarkan", "e": "draf tes disetujui", "f": "pembaca patch mencatat ok untuk patch ini",
          "g": "satu sha untuk review, provenance dan patch", "h": "ada contoh perilaku yang baru", "i": "angka domain dibaca"}
APPROVAL_NOTE = "dicatat sebagai tahap; catatan tidak membedakan manusia dan sesi Claude"


def _chk(key, ok, why):
    return {"key": key, "label": LABELS[key], "ok": ok, "why": why}


class Install:
    def __init__(self, approve):
        self.approve = approve
        self.cards = approve.cards

    def code(self, job_id):
        try:
            return self._code(job_id)
        except Exception:
            return None

    # ---- files ------------------------------------------------------------------------------------------------------------------

    @staticmethod
    def _chain_fds(jfd, names):
        """The descriptor of jfd/<names...> (never through a symlink), or None; the caller closes it."""
        fds = []
        try:
            for name in names:
                fds.append(_open_dir(name, fds[-1] if fds else jfd))
            return fds.pop()
        except OSError:
            return None
        finally:
            for fd in fds:
                os.close(fd)

    @staticmethod
    def _hash(dfd, name, limit):
        """(sha256 hex, bytes) of a regular file read through the directory descriptor, or (None, None) when it is missing, not regular, or over `limit`."""
        try:
            fd = os.open(name, OPEN_FILE, dir_fd=dfd)
        except OSError:
            return None, None
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode) or os.fstat(fd).st_size > limit:
                return None, None
            h, parts = hashlib.sha256(), []
            total = 0
            with os.fdopen(fd, "rb", closefd=False) as f:
                while True:
                    block = f.read(1 << 16)
                    if not block:
                        break
                    total += len(block)
                    if total > limit:                       # it grew after the size check
                        return None, None
                    h.update(block)
                    parts.append(block)
            return h.hexdigest(), b"".join(parts)
        except OSError:
            return None, None
        finally:
            os.close(fd)

    def _load(self, jfd, name, key, parsed):
        """eg.load's kinds for a file read through the descriptor: ('none'|'stale'|'skipped'|'pending'|'error', why) or ('results', rows)."""
        try:
            raw = _read(jfd, name, DOC_MAX)
        except FileNotFoundError:
            return "none", None
        except OSError:
            return "error", None
        try:
            return eg.parse_stored(raw.decode("utf-8"), key, parsed)
        except UnicodeDecodeError:
            return "error", None

    # ---- the card ---------------------------------------------------------------------------------------------------------------

    def _code(self, job_id):
        c = self.cards
        d = c._job_dir(job_id)
        if d is None:
            return None
        sfd, jfd = d
        extra = []
        try:
            data = c._job_json(jfd)
            if data is None or data.get("kind") != "code" or not isinstance(data.get("inputs"), dict):
                return None
            i = data["inputs"]
            issue = i.get("issue") if isinstance(i.get("issue"), str) else ""
            stages = data.get("stages") if isinstance(data.get("stages"), dict) else {}
            sids = sorted((k for k, st in stages.items() if isinstance(st, dict) and st.get("kind") == "agent" and SID.fullmatch(k)), key=lambda k: int(k[1:]))
            sid = sids[-1] if sids else None
            st = stages[sid] if sid else {}
            rv = st.get("review") if isinstance(st.get("review"), dict) else {}
            rsha = rv.get("patch_sha256") if isinstance(rv.get("patch_sha256"), str) and SHA.fullmatch(rv["patch_sha256"]) else None
            run_id = st.get("run_id") if sid else None
            run_ok = isinstance(run_id, str) and RUN_A.fullmatch(run_id) is not None and run_id == f"{job_id}-{sid}"
            present, parsed, problems = eg.extract(issue)
            checks = {}

            # the review package and the patch on disk (c, g, files)
            prov, disk_sha, patch_bytes = None, None, None
            if run_ok:
                rfd = self._chain_fds(jfd, ("runs", run_id, "review"))
                if rfd is not None:
                    try:
                        try:
                            prov = json.loads(_read(rfd, "provenance.json", DOC_MAX))
                        except (OSError, ValueError, RecursionError):
                            prov = None
                        disk_sha, patch_bytes = self._hash(rfd, "changes.patch", PATCH_MAX)
                    finally:
                        os.close(rfd)
            patch = prov.get("patch") if isinstance(prov, dict) and isinstance(prov.get("patch"), dict) else {}
            listed = [f["path"] for f in patch.get("files") or [] if isinstance(f, dict) and isinstance(f.get("path"), str)]

            # the example items as numbers
            src_fd = self._chain_fds(jfd, ("runs", run_id, "workspace")) if run_ok else None
            try:
                source_of = cn.tree_source_of(f"/proc/self/fd/{src_fd}") if src_fd is not None else (lambda module: None)
                item = self.approve._item(1, issue, {"absent": True}, False, source_of, src_fd is not None)
            finally:
                if src_fd is not None:
                    os.close(src_fd)
            counts = item["counts"]

            # (a) and (b): the examples on the base and on the patch
            base_kind = audit_kind = None
            base_val = audit_val = None
            if present and not problems and parsed:
                snap = (data.get("intake") or {}).get("snapshot_sha256")
                base_kind, base_val = self._load(jfd, eg.INTAKE_FILE, eg.intake_key(snap, parsed), parsed) if isinstance(snap, str) else ("error", None)
                audit_kind, audit_val = (self._load(jfd, f"examples_audit_{sid}.json", eg.audit_key(rsha, parsed), parsed)
                                         if sid and rsha else ("error", None))
            checks["a"] = self._check_a(present, problems, parsed, base_kind, base_val)
            checks["b"] = self._check_b(present, problems, parsed, audit_kind, audit_val)
            if isinstance(item.get("examples"), list):
                self._audit_proofs(item["examples"], audit_kind, audit_val)

            # (c) the review package, (d) and (e) the approval of the draft
            state = data.get("state")
            globs = [g for g in ((data.get("protected_repo") or {}).get("globs") or []) if isinstance(g, str)]
            protected = [p for p in listed if self._protected(p, globs)]
            if state != "REVIEW_READY":
                checks["c"] = _chk("c", False, f"job ada di keadaan {state}, bukan REVIEW_READY: belum ada paket review yang siap")
            elif rv.get("valid") is not True or rv.get("problems"):
                checks["c"] = _chk("c", False, "paket review tidak valid (tes yang dijalankan ulang atau must_pass gagal)")
            elif protected:
                checks["c"] = _chk("c", False, f"patch mengubah file yang dilindungi repo (.argus/protected): {', '.join(protected[:3])}; `argus apply` menolaknya")
            else:
                checks["c"] = _chk("c", True, "paket review valid")
            appr = data.get("approval") if isinstance(data.get("approval"), dict) else None
            drafts = [s for s in stages.values() if isinstance(s, dict) and s.get("kind") == "draft" and s.get("status") == "DRAFTED"]
            last_draft = drafts[-1].get("draft_sha256") if drafts else None
            if appr is None:
                checks["d"] = _chk("d", False, "draf belum disetujui, jadi belum ada pemeriksaan bentrok dengan tes lama yang lolos")
                checks["e"] = _chk("e", False, "draf tes belum disetujui")
            else:
                nc = any(isinstance(s, dict) and isinstance(s.get("carry"), dict) and s["carry"].get("not_a_conflict") for s in stages.values())
                checks["d"] = _chk("d", None, "tidak tercatat terpisah: draf yang bentrok tidak bisa disetujui, jadi persetujuan ada berarti tidak ada bentrokan yang masih ditandai; "
                                   "siapa yang melonggarkan tes lama, bila ada, tidak dicatat" + (
                                       "; ada tahap yang dinilai 'bukan bentrokan' oleh seseorang" if nc else ""))
                same = isinstance(last_draft, str) and appr.get("draft_sha256") == last_draft
                checks["e"] = _chk("e", same, (f"draf disetujui {appr.get('at')} oleh {appr.get('by')} ({APPROVAL_NOTE})" if same
                                               else "persetujuan itu untuk draf lain dari draf terakhir"))

            # (f) the patch reader's note, (g) one sha
            pr_kind, pr_rec = pr.load(f"/proc/self/fd/{jfd}", sid, rsha) if sid and rsha else ("error", None)
            checks["f"] = _chk("f", pr_kind in ("ok", "nit"), {
                "ok": "dua pembaca patch sama-sama mencatat ok untuk patch ini", "nit": "dua pembaca patch membaca patch ini; hanya ada catatan kecil (nit), bukan keberatan",
                "concerns": "pembaca patch mencatat ada yang meragukan",
                "one": "baru satu bacaan patch: ok butuh dua bacaan oleh dua pembaca berbeda",
                "none": "belum ada catatan pembaca patch", "stale": "catatan pembaca patch untuk patch lain",
                "error": "catatan pembaca patch rusak atau tidak bisa dibaca"}[pr_kind])
            same_sha = rsha is not None and rsha == patch.get("sha256") == disk_sha
            empty = patch_bytes is not None and (not patch_bytes.strip() or not listed)
            checks["g"] = _chk("g", same_sha and not empty, "review, provenance dan patch di disk menyebut sha yang sama" if same_sha and not empty else
                               "patch kosong atau tanpa daftar file; `argus apply` menolaknya" if same_sha else
                               "sha patch tidak sama di review (job.json), provenance dan berkas patch, atau salah satunya tidak terbaca")

            # (h) at least one example of the new behaviour (a stated "no numbers checked by the machine" is not recorded anywhere yet)
            if item.get("unreadable") or item.get("defects"):
                checks["h"] = _chk("h", False, "ada contoh yang tidak bisa ditampilkan sebagai angka: kartu cacat")
            elif counts["after"] + counts["whatif"] >= 1:
                checks["h"] = _chk("h", True, "ada contoh perilaku baru")
            else:
                checks["h"] = _chk("h", False, "tidak ada contoh untuk perilaku yang baru; pernyataan 'tanpa angka yang diperiksa mesin' belum tercatat di kartu rencana")

            # (i) the domain reader, through the queue
            res = er.chain(SimpleNamespace(id=job_id, data=data), c.jobs_dir, c.queues_dir)
            if not res["applicable"]:
                checks["i"] = _chk("i", None, f"tidak berlaku: {res['why']}")
                item["domain_read"] = {"kind": "tidak_berlaku", "fresh": False, "why": f"tidak berlaku: {res['why']}"}
            else:
                checks["i"] = _chk("i", res["ok"], er.card_text(res) if res["ok"] else (res["why"] or "angka domain belum dibaca"))
                item["domain_read"] = (self.approve._domain_read(res["prd_job"], res["item"], item) if res.get("prd_job") else
                                       {"kind": "tidak_terbaca", "fresh": False, "why": res["why"] or "tidak terbaca"})
            files, scope_note, cut = self._files(listed, patch_bytes, globs, res)
            repo = i.get("repo_name")
            cost = {"spent": c._spent(data), "cap": data.get("max_usd") if isinstance(data.get("max_usd"), (int, float)) and not isinstance(data.get("max_usd"), bool) else None,
                    "reference": self.approve._reference()}
            card = {"kind": "install", "id": job_id, "state": state, "repo": repo, "sid": sid, "patch_sha12": rsha[:12] if rsha else None,
                    "purpose": {"title": c.s(issue.split("\n", 1)[0])[:200], "text": self.approve._cut(c.s(self.approve_text(issue)), ISSUE_MAX)[0],
                                "by": "ditulis model (issue dari PRD, bukan permintaan Atha kata demi kata)" if res["applicable"] else
                                      "teks issue; pembuatnya tidak tercatat (bukan permintaan Atha kata demi kata)"},
                    "scope_note": scope_note, "files_cut": cut, "cost": cost, "item": item, "checks": [checks[k] for k in "abcdefghi"],
                    "open": all(v["ok"] is not False for v in checks.values()), "files": files,
                    "scope_marks": [f"{f['path']}: {m}" for f in files for m in f["marks"]],
                    "patch_read": None, "patch_read_label": PATCH_LABEL, "fixed_line": FIXED_LINE, "domain_read_label": DOMAIN_LABEL,
                    "approval": None if appr is None else {"at": appr.get("at"), "by": appr.get("by"), "note": APPROVAL_NOTE},
                    "patch_reader_tested": False, "domain_reader_tested": False}
            if pr_kind in ("ok", "concerns", "nit") and pr_rec:
                card["patch_read"] = {"verdict": pr_rec["verdict"], "reader": pr_rec["reader"], "at": pr_rec["at"], "note": pr_rec["note"], "by": "model",
                                      **({"severity": pr_rec["severity"]} if pr_rec.get("severity") else {})}
                if isinstance(pr_rec.get("second"), dict):
                    s2 = pr_rec["second"]
                    card["patch_read"]["second"] = {"verdict": s2["verdict"], "reader": s2["reader"], "at": s2["at"], "note": s2["note"],
                                                    **({"severity": s2["severity"]} if s2.get("severity") else {})}
            pids = [(r.get("kind"), r.get("id")) for r in ((pr_rec or {}).get("reader"), ((pr_rec or {}).get("second") or {}).get("reader")) if isinstance(r, dict)] if pr_kind in ("ok", "nit") else []
            dr = item.get("domain_read") if isinstance(item, dict) else None
            ids = [r.get("id") for r in (dr.get("reader"), dr.get("reader2")) if isinstance(r, dict)] if isinstance(dr, dict) else []
            card["patch_reader_tested"], card["domain_reader_tested"] = self._tested(repo, ids, pids)
            return c.withhold_keys(self.approve._deep(card))
        finally:
            os.close(jfd)
            os.close(sfd)

    @staticmethod
    def approve_text(issue):
        """The issue without its examples block and without its first line (the title is shown on its own)."""
        try:
            body = eg.without_block(issue)
        except Exception:
            body = issue
        return body.split("\n", 1)[1].strip() if "\n" in body else ""

    # ---- conditions ---------------------------------------------------------------------------------------------------------------

    @staticmethod
    def _check_a(present, problems, parsed, kind, val):
        if not present:
            return _chk("a", None, "issue ini tidak punya contoh")
        if problems or not parsed:
            return _chk("a", False, "blok contoh di issue tidak bisa dipakai")
        if kind == "skipped":
            return _chk("a", False, f"contoh di dasar tidak dijalankan: {val}")
        if kind != "results":
            return _chk("a", False, {"none": "contoh di dasar belum dijalankan", "stale": "hasil contoh di dasar untuk issue atau dasar lain",
                                     "pending": "contoh di dasar belum selesai dijalankan", "error": "hasil contoh di dasar rusak"}[kind])
        tiers = {e["id"]: e["tier"] for e in parsed}                                      # the tier is the issue's, never the stored file's
        bad = sorted(r["id"] for r in val if tiers.get(r["id"]) != "after" and r["status"] != ex.PASS)
        if bad:
            return _chk("a", False, f"contoh gagal di dasar: {', '.join(bad)}")
        return _chk("a", True, "contoh yang harus benar di dasar memang benar")

    @staticmethod
    def _check_b(present, problems, parsed, kind, val):
        if not present:
            return _chk("b", None, "issue ini tidak punya contoh")
        if problems or not parsed:
            return _chk("b", False, "blok contoh di issue tidak bisa dipakai")
        if kind == "skipped":
            return _chk("b", False, f"contoh pada patch tidak dijalankan: {val}")
        if kind != "results":
            return _chk("b", False, {"none": "contoh belum dijalankan pada patch ini", "stale": "hasil contoh untuk patch atau contoh lain",
                                     "pending": "audit contoh belum selesai", "error": "hasil audit rusak"}[kind])
        bad = eg.failing(val)
        if bad:
            return _chk("b", False, f"contoh tidak benar pada kode akhir: {', '.join(bad)} (pengecualian 'sengaja berubah' belum ada di kartu rencana)")
        return _chk("b", True, "semua contoh benar pada kode akhir")

    @staticmethod
    def _val(v):
        try:
            shown = cn.fmt(v)
        except (TypeError, ValueError, RecursionError):
            return None, "nilai tidak bisa ditulis"
        try:
            return json.dumps(v, ensure_ascii=False, allow_nan=False), shown
        except (TypeError, ValueError, RecursionError):
            return None, shown

    def _audit_proofs(self, cards, kind, rows):
        """The proof of each example from the audit on this patch; without a finished audit for exactly this patch and these examples, none."""
        by_id = {r["id"]: r for r in rows} if kind == "results" else {}
        for e in cards:
            r = by_id.get(e.get("id"))
            if r is None:
                why = {"none": "contoh belum dijalankan pada patch ini", "stale": "hasil untuk patch atau contoh lain", "pending": "audit belum selesai",
                       "skipped": "audit dilewati", "error": "hasil audit rusak"}.get(kind, "belum diperiksa")
                e["proof"] = {"kind": "audit", "status": None, "actual_json": None, "shown": None, "wording": f"belum diperiksa mesin ({why})"}
                continue
            if "actual" in r:
                raw, shown = self._val(r["actual"])
                tail = "cocok dengan yang diharapkan" if r["status"] == ex.PASS else "TIDAK cocok dengan yang diharapkan"
                e["proof"] = {"kind": "audit", "status": r["status"], "actual_json": raw, "shown": shown,
                              "wording": f"kode akhir memberi angka ini: {shown}; {tail}"}
            else:
                e["proof"] = {"kind": "audit", "status": r["status"], "actual_json": None, "shown": None,
                              "wording": f"kode akhir tidak memberi angka (gerbang menandai: {r['status']}); TIDAK cocok dengan yang diharapkan"}

    # ---- scope ------------------------------------------------------------------------------------------------------------------

    def _anchors(self, res):
        """The `touches` and `creates` lines the PRD item named (code anchors, not file names), or None when the job is not an item of a PRD folder."""
        if not res.get("prd_job") or not isinstance(res.get("item"), int):
            return None
        d = self.cards._job_dir(res["prd_job"])
        if d is None:
            return None
        try:
            data = self.cards._job_json(d[1])
        finally:
            for fd in d:
                os.close(fd)
        turns = [t for t in (data or {}).get("prd_turns") or [] if isinstance(t, dict)]
        if not turns:
            return None
        t, n, out = turns[-1], res["item"], []
        for key in ("touches", "creates"):
            rows = t.get(key) if isinstance(t.get(key), list) else []
            if 0 < n <= len(rows) and isinstance(rows[n - 1], list):
                out += [x.strip() for x in rows[n - 1] if isinstance(x, str) and len(x.strip()) >= 3]
        return out

    @staticmethod
    def _protected(path, globs):
        try:
            return bool(matches(path, globs))
        except Exception:
            return True                                           # a glob that cannot be read protects

    def _files(self, listed, patch_bytes, globs, res):
        """([{path, marks}], note, how many files were cut): the marks are hints of the machine, not a judgement; the note says when the issue's own
        anchors could not be compared (no anchors, no readable patch)."""
        anchors = self._anchors(res)
        sections = {}
        if patch_bytes is not None and anchors:
            for part in re.split(rb"(?m)^diff --git ", patch_bytes)[1:]:
                head = part.split(b"\n", 1)[0].decode("utf-8", "replace")
                m = re.match(r"a/(.+?) b/(.+)$", head)
                if m:
                    sections[m.group(2)] = part.decode("utf-8", "replace")
        out = []
        for p in sorted(listed)[:FILES_MAX]:
            marks = []
            if self._protected(p, globs):
                marks.append(PROTECTED_MARK)
            if anchors and p in sections and not any(a in sections[p] for a in anchors):
                marks.append(OUTSIDE_MARK)
            out.append({"path": p, "marks": marks})
        note = None
        if not anchors:
            note = "cakupan terhadap issue tidak diperiksa: issue ini tidak punya potongan touches/creates dari PRD"
        elif patch_bytes is None or any(p not in sections for p in listed[:FILES_MAX]):
            note = "cakupan terhadap issue hanya diperiksa untuk file yang bisa dibaca dari patch; sisanya tidak ditandai"
        return out, note, max(0, len(listed) - FILES_MAX)

    # ---- the readers have not been tested -----------------------------------------------------------------------------------------

    @staticmethod
    def _same_reader(dom, ids):
        """The test holds for the model and effort it names (spec 13.3): the readers of this card are that model (`argus:<model>`, or a session id that starts
        with the model name); no readers or any other reader is untested."""
        model, effort = dom.get("model"), dom.get("effort")
        if not (isinstance(model, str) and model.strip() and isinstance(effort, str) and effort.strip()) or not ids:
            return False
        m = model.strip().casefold()
        return all(isinstance(i, str) and (i.strip().casefold() in (m, f"argus:{m}") or i.strip().casefold().startswith(m + "-")) for i in ids)

    @staticmethod
    def _same_pair(patch, ids):
        """The patch reader test holds for the pair of models it names (`models`: reader ids `argus:<ref>`, in order) and this template: the two readings of the card are
        by exactly that pair (the first and the second); anything else, or no readings, is untested."""
        models = patch.get("models")
        return (isinstance(models, list) and len(models) == 2 and all(isinstance(m, str) and m for m in models) and patch.get("effort") == "default"
                and patch.get("instruction_sha256") == pr.INSTRUCTION_SHA256 and all(k == "argus" for k, _ in ids)
                and [i.strip().casefold() if isinstance(i, str) else None for _, i in ids] == [m.strip().casefold() for m in models])

    @staticmethod
    def _tested(repo, domain_ids=(), patch_ids=()):
        """(patch reader tested, domain reader tested): true only when verification/reader_tests.json holds an entry for this repo whose template hash is
        the current one; a missing or damaged file, another repo or another hash is untested. The patch reader has no template yet: never tested."""
        try:
            doc = json.loads(Path(READER_TESTS).read_bytes()[:DOC_MAX].decode("utf-8"))
            rec = doc[repo] if isinstance(doc, dict) and isinstance(repo, str) else {}
            dom = rec.get("domain") if isinstance(rec, dict) else None
            patch = rec.get("patch") if isinstance(rec, dict) else None
            cur_patch = getattr(pr, "TEMPLATE_SHA256", None)
            return (bool(cur_patch and isinstance(patch, dict) and patch.get("template_sha256") == cur_patch and Install._same_pair(patch, patch_ids)),
                    bool(isinstance(dom, dict) and dom.get("template_sha256") == er.TEMPLATE_SHA256 and Install._same_reader(dom, domain_ids)))
        except Exception:
            return False, False
