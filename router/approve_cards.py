"""The plan card of the plain-language approval (docs/reviews/SPEC_KARTU_SETUJU.md sections 2, 3 and 6, PR 2 of T3): what will be built, the
examples as numbers, and what it costs, for one PRD job. Read only, on top of the T2 cards (`router.cards.Cards`): it opens files the same
way (one name at a time through directory descriptors, never through a symlink), it runs nothing, it starts no process, it calls no model,
it writes nothing. There is no button in this module: the two decisions (approve the plan, run the queue) are the chat's `prd_approve` and `queue_go` (router/chat_plan.py, SPEC_CHAT_T4A), which read the same card.

What the card is made of, and who says it:
- block A: the request as the human wrote it (the first human message, word for word; cut and marked when it is long), the writer's reply
  (marked as model text), the number of issues, the cost (what the job spent, what the queue proposes, and a reference: the median of what
  earlier applied code jobs spent, from their job.json);
- block B: each example as numbers (router.card_numbers: nothing is guessed, an example outside its grammar says so), in the fixed order
  same, whatif, after, with the machine's words of proof at the base: "kode sekarang memberi angka ini: <value>" (never "cocok": the writer
  tried the example with RunExample first, and the gate refuses what does not match, so a match at the base proves nothing), and for an
  `after` example "belum ada (memang belum dibuat); kode sekarang memberi <value>".
A status is shown only for the files it was computed for (the folder's sha and the digest of the examples, as in T2); otherwise the
example is shown without any proof.
Names of positional arguments come from the writer's frozen copy of the repository (runs/<turn run>/source) at the commit the turn read.
"""
import json
import math
import os
import re
import statistics

from codetask import examples as ex
from router import card_numbers as cn
from router import example_gate as eg
from router import job as rj
from router import prd as rp
from router import request_by as rb
from router.cards import (DOC_MAX, ISSUE_MAX, ITEMS_MAX, JOB_JSON_MAX, NOT_RUN_WHY, OPEN_DIR, SCAN_BYTES, SCAN_JOBS, TURN, UI_ID, _open_dir,
                          _read)

TIER_ORDER = {"same": 0, "whatif": 1, "after": 2}
NO_NEW_WARNING = "Tidak ada contoh untuk perilaku yang baru; angka baru di teks issue tidak diperiksa mesin"
FIXED_LINE = ("Mesin memeriksa: kode memberi angka ini. Dibaca Claude, bukan mesin dan bukan Anda: apakah angkanya sesuai permintaan. "
              "Tidak diperiksa siapa pun: aturan bisnis yang tidak tertulis; perubahan di luar contoh (pembaca patch: Claude); angka di teks issue.")
DOMAIN_LABEL = ("Ini pernyataan sesi Claude (model), bukan bukti angkanya benar, dan bukan manusia; Claude tidak tahu aturan yang tidak tertulis "
                "di permintaan, PRD dan dokumen repo.")
DOMAIN_UNREAD = "belum dibaca: angka domain belum dinilai siapa pun"
DOMAIN_STALE = "pembacaan Claude basi: bahan yang dibacanya berubah sejak itu (folder, contoh, dokumen atau templat); dianggap belum dibaca"
DOMAIN_ONE = "baru satu bacaan: angka domain butuh dua bacaan independen yang sama-sama ok"
DOMAIN_ERROR = "catatan pembacaan rusak: dianggap belum dibaca"
DOMAIN_NONE = "tidak ada angka baru yang dibaca"
TREE_WHY = "pohon sumber penulis tidak terbaca: nama parameter tidak bisa diambil dari definisi; kartu ini cacat"
REQUEST_MAX, SUMMARY_MAX = 3000, 4000
REFERENCE_MIN = 3
REFERENCE_OF = "job code yang sudah di-apply"
RUN_ID = re.compile(r"j[0-9]{8}_[0-9]{6}_[0-9a-f]{4}-w[0-9]{1,3}")


class Approve:
    def __init__(self, cards):
        self.cards = cards

    # ---- helpers ------------------------------------------------------------------------------------------------------------

    def _deep(self, value):
        """Every text of a card value through the chat's scrub (keys are ours and stay as they are)."""
        if isinstance(value, str):
            return self.cards.s(value)
        if isinstance(value, dict):
            return {k: self._deep(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._deep(v) for v in value]
        return value

    @staticmethod
    def _cut(text, limit):
        return (text[:limit], True) if len(text) > limit else (text, False)

    def _reference(self):
        """{median, n, of} of what the applied code jobs of this jobs directory spent, or None when fewer than REFERENCE_MIN know their
        cost (an unknown cost is left out, never counted as 0)."""
        try:
            sfd = _open_dir(str(self.cards.jobs_dir))
        except OSError:
            return None
        costs, caps, total = [], [], 0
        try:
            names = sorted((n for n in os.listdir(sfd) if UI_ID.fullmatch(n)), reverse=True)[:SCAN_JOBS]
            for jid in names:
                try:
                    jfd = _open_dir(jid, sfd)
                except OSError:
                    continue
                try:
                    raw = _read(jfd, "job.json", JOB_JSON_MAX)
                    total += len(raw)
                    if total > SCAN_BYTES:
                        break
                    data = json.loads(raw)
                except (OSError, ValueError, RecursionError):
                    continue
                finally:
                    os.close(jfd)
                if isinstance(data, dict) and data.get("kind") == "code" and data.get("state") == "APPLIED":
                    spent = self.cards._spent(data)
                    if spent is not None and math.isfinite(spent):
                        costs.append(spent)
                    cap = data.get("max_usd")
                    if isinstance(cap, (int, float)) and not isinstance(cap, bool) and math.isfinite(cap) and cap > 0:
                        caps.append(cap)
        finally:
            os.close(sfd)
        if len(costs) < REFERENCE_MIN and len(caps) < REFERENCE_MIN:
            return None
        return {"median": round(statistics.median(costs), 6) if len(costs) >= REFERENCE_MIN else None, "n": len(costs), "of": REFERENCE_OF,
                "cap_median": round(statistics.median(caps), 6) if len(caps) >= REFERENCE_MIN else None, "cap_n": len(caps)}

    @staticmethod
    def _source_fd(jfd, run_id):
        """The directory descriptor of runs/<run_id>/source of the job (never through a symlink), or None; the caller closes it."""
        if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
            return None
        fds = []
        try:
            for name in ("runs", run_id, "source"):
                fds.append(_open_dir(name, fds[-1] if fds else jfd))
            keep = fds.pop()
            return keep
        except OSError:
            return None
        finally:
            for fd in fds:
                os.close(fd)

    # ---- proof ----------------------------------------------------------------------------------------------------------------

    @staticmethod
    def _proof(tier, res, why):
        if res is None:
            return {"kind": "dasar", "status": None, "actual_json": None, "shown": None, "wording": f"belum diperiksa mesin ({why})"}
        status = res["status"]

        def value(v):
            """(json text or None, shown): a NaN or an infinity has no JSON text but is still shown as what it is; never the word None."""
            try:
                shown = cn.fmt(v)
            except (TypeError, ValueError, RecursionError):
                return None, "nilai tidak bisa ditulis"
            try:
                return json.dumps(v, ensure_ascii=False, allow_nan=False), shown
            except (TypeError, ValueError, RecursionError):
                return None, shown
        if tier == "after":
            if "base_actual" in res:
                raw, shown = value(res["base_actual"])
                return {"kind": "dasar", "status": status, "actual_json": raw, "shown": shown,
                        "wording": f"belum ada (memang belum dibuat); kode sekarang memberi {shown}"}
            return {"kind": "dasar", "status": status, "actual_json": None, "shown": None, "wording": "belum ada (memang belum dibuat)"}
        if "actual" in res:
            raw, shown = value(res["actual"])
            flag = "" if status == ex.PASS else f" (gerbang menandai: {status})"
            return {"kind": "dasar", "status": status, "actual_json": raw, "shown": shown,
                    "wording": f"kode sekarang memberi angka ini: {shown}{flag}"}
        return {"kind": "dasar", "status": status, "actual_json": None, "shown": None,
                "wording": f"kode sekarang tidak memberi angka (gerbang menandai: {status})"}

    def _results(self, parsed, stored, bound, calls):
        """({id: result}, why): the results of the writer's turn for exactly these examples, or why there are none to show."""
        if not parsed:
            return {}, None
        if not isinstance(stored, dict):
            return {}, NOT_RUN_WHY
        if stored.get("absent"):
            return {}, "dari sebelum gerbang contoh"
        results = stored.get("results")
        if not isinstance(results, list) or not results:
            return {}, (eg.RUNNER_NOTE if stored.get("note") else NOT_RUN_WHY)
        ids = [e["id"] for e in parsed]
        if not bound or eg.digest(parsed) != eg.digest(stored.get("examples") if isinstance(stored.get("examples"), list) else []):
            return {}, "berkas tidak cocok dengan hasil"
        clean = [eg._result(r, set(ids)) for r in results]
        tiers = {e["id"]: e["tier"] for e in parsed}
        if any(r is None for r in clean) or sorted(r["id"] for r in clean) != sorted(ids) or any(r["tier"] != tiers[r["id"]] for r in clean):
            return {}, "id tidak cocok"
        return {r["id"]: r for r in clean}, None

    # ---- the card -----------------------------------------------------------------------------------------------------------

    def plan(self, job_id):
        try:
            return self._plan(job_id)
        except Exception:
            return None

    def _plan(self, job_id):
        c = self.cards
        d = c._job_dir(job_id)
        if d is None:
            return None
        sfd, jfd = d
        src_fd = None
        try:
            data = c._job_json(jfd)
            if data is None or data.get("kind") != "prd" or not isinstance(data.get("inputs"), dict):
                return None
            i = data["inputs"]
            turns = [t for t in data.get("prd_turns") or [] if isinstance(t, dict)]
            human = [m for m in data.get("conversation") or [] if isinstance(m, dict) and m.get("from") == "human" and isinstance(m.get("text"), str)]
            writer = [m for m in data.get("conversation") or [] if isinstance(m, dict) and m.get("from") == "writer" and isinstance(m.get("text"), str)]
            request, cut = self._cut(c.s(human[0]["text"]), REQUEST_MAX) if human else (None, False)       # scrubbed whole, then cut: no key prefix survives
            summary = None
            via_ui = rb.via_ui(data)
            humans = rb.human_messages(data)
            card = {"kind": "plan", "id": job_id, "state": data.get("state"), "repo": i.get("repo_name"), "turn": None, "stale": None,
                    "superseded": None, "folder_sha12": None, "why": None, "request": request, "request_truncated": cut,
                    "request_by": "chat" if via_ui else "tidak_tercatat", "request_count": len(humans), "refs": rb.ref_facts(data), "summary": summary, "summary_by": "model", "issue_count": 0,
                    "cost": {"spent": None, "proposed": None, "proposed_each": None, "reference": None, "ratio": None, "ratio_text": None},
                    "items": [], "defects": 0, "fixed_line": FIXED_LINE, "domain_read_label": DOMAIN_LABEL}
            spent = c._spent(data)
            card["cost"]["spent"] = spent if spent is not None and math.isfinite(spent) else None
            if not turns:
                card["why"] = "belum ada folder"
                return self._finish(card)
            t = turns[-1]
            n_items = t["items"] if isinstance(t.get("items"), int) and 0 < t["items"] <= ITEMS_MAX else 0
            card.update(turn=t.get("turn"), stale=(not t.get("commit")) or t.get("commit") != i.get("commit"),
                        folder_sha12=t["folder_sha"][:12] if isinstance(t.get("folder_sha"), str) else None, issue_count=n_items)
            mine = [m for m in writer if m.get("stage") == t.get("turn") and isinstance(t.get("folder_sha"), str) and m.get("folder_sha") == t["folder_sha"]]
            if mine:                                                  # the reply of THIS folder, never the last message of the conversation
                card["summary"] = self._cut(c.s(mine[-1]["text"]), SUMMARY_MAX)[0]
            else:
                card["summary_why"] = "tidak ada balasan penulis yang terikat pada folder ini"
            prop = t.get("max_usd")
            card["cost"]["proposed"] = prop if isinstance(prop, (int, float)) and not isinstance(prop, bool) and math.isfinite(prop) else None
            if card["cost"]["proposed"] is not None and n_items:
                card["cost"]["proposed_each"] = round(card["cost"]["proposed"] / n_items, 6)
            card["cost"]["reference"] = self._reference()
            self._ratio(card["cost"])
            files, why = c._folder(jfd, t.get("turn"), n_items)
            if files is None:
                card["why"] = why
                return self._finish(card)
            card["superseded"] = bool(files.pop("__superseded__"))
            bound = rp.folder_sha(files) == t.get("folder_sha") if n_items else False
            stage = (data.get("stages") or {}).get(t.get("turn")) if isinstance(data.get("stages"), dict) else None
            run_id = stage.get("run_id") if isinstance(stage, dict) else None
            if isinstance(run_id, str) and isinstance(t.get("turn"), str) and TURN.fullmatch(t["turn"]) and run_id == f"{job_id}-{t['turn']}":
                src_fd = self._source_fd(jfd, run_id)
            source_of = cn.tree_source_of(f"/proc/self/fd/{src_fd}") if src_fd is not None else (lambda module: None)
            per_item = t.get("examples") if isinstance(t.get("examples"), list) else [None] * n_items
            for n in range(1, n_items + 1):
                raw = files.get(f"issue-{n}.md")
                text = raw.decode("utf-8", "replace") if raw is not None else None
                stored = per_item[n - 1] if n - 1 < len(per_item) and per_item[n - 1] else None
                if stored is None and "examples" not in t:
                    stored = {"absent": True}
                item = self._item(n, text, stored, bound, source_of, src_fd is not None)
                item["domain_read"] = self._domain_read(job_id, n, item)
                card["items"].append(item)
                if isinstance(item["examples"], list):
                    card["defects"] += item["defects"]
            return self._finish(card)
        finally:
            if src_fd is not None:
                os.close(src_fd)
            os.close(jfd)
            os.close(sfd)

    @staticmethod
    def _ratio(cost):
        """The proposal per issue against the limit an applied code job usually carries (the median of their caps): both are settings, so the ratio
        says whether this plan asks for an unusual amount (about 1 is usual). The money a job really spends is far below its cap, so the cap is
        never compared with the spending: that ratio would be large for every plan and say nothing."""
        each, ref = cost.get("proposed_each"), cost.get("reference")
        if each is None or not ref or not isinstance(ref.get("cap_median"), (int, float)) or ref["cap_median"] <= 0:
            return
        raw = each / ref["cap_median"]
        ratio = round(raw, 1) if raw >= 1 else round(raw, 2)          # below 1 two digits: 0,04 is not 0
        cost["ratio"] = ratio
        text = str(int(ratio)) if ratio == int(ratio) else str(ratio).replace(".", ",")
        cost["ratio_text"] = f"kira-kira {text}× batas job biasa per issue"

    def _domain_read(self, job_id, n, item):
        """What the domain reader (a Claude session) said about the numbers of this item, against the bundle as it is now (router.examples_read)."""
        if item.get("unreadable") or not isinstance(item.get("examples"), list):
            return {"kind": "tidak_terbaca", "fresh": False, "why": "contoh item ini tidak bisa ditampilkan, jadi tidak ada yang dibaca"}
        if not item["counts"]["calls"]:
            return {"kind": "tidak_berlaku", "fresh": False, "why": DOMAIN_NONE}
        try:
            from router import examples_read as er            # imported here: examples_read imports this module
            kind, rec = er.status(self.cards.jobs_dir, job_id, n)
        except rj.Refused as e:
            text = str(e)
            why = ("folder digantikan giliran berikutnya (SUPERSEDED): tidak ada yang dibaca" if "SUPERSEDED" in text
                   else "folder berubah sejak giliran ditulis: tidak ada yang dibaca" if "folder changed" in text
                   else "bahan pembacaan tidak bisa dibaca: dianggap belum dibaca")
            return {"kind": "tidak_terbaca", "fresh": False, "why": why}
        except Exception:                                     # whatever else: never shown as a reading
            return {"kind": "tidak_terbaca", "fresh": False, "why": "catatan pembacaan tidak bisa diperiksa: dianggap belum dibaca"}
        out = {"kind": kind, "fresh": kind in ("ok", "concerns")}
        if rec and kind != "one":
            out.update(verdict=rec["verdict"], reader=rec["reader"], reader2=rec.get("reader2"), at=rec["at"], sources=rec["sources"], note=rec["note"])
        else:
            out["why"] = {"none": DOMAIN_UNREAD, "stale": DOMAIN_STALE, "error": DOMAIN_ERROR, "one": DOMAIN_ONE}.get(kind, DOMAIN_UNREAD)
        return out

    def _finish(self, card):
        out = self.cards.withhold_keys(self._deep(card))
        return out

    def _item(self, n, text, stored, bound, source_of, tree_ok):
        c = self.cards
        title = c.s(text.split("\n", 1)[0]) if text is not None else ""
        item = {"n": n, "title": title, "counts": {"calls": 0, "same": 0, "whatif": 0, "after": 0}, "warning": None, "no_examples": None,
                "defects": 0, "examples": [], "why": None}
        if text is None:
            item["why"] = "teks issue tidak terbaca"
            item["warning"] = NO_NEW_WARNING
            item["unreadable"] = True
            return item
        if eg.extract(text)[2]:
            item["unreadable"] = True                           # a block that does not parse is not "no examples"
        calls, parsed = c._calls(text)
        if c._leaks(calls):
            item["examples"] = {"withheld": True}
            item["warning"] = NO_NEW_WARNING
            return item
        if isinstance(stored, dict) and isinstance(stored.get("no_examples"), str):
            item["no_examples"] = stored["no_examples"]
        results, why = self._results(parsed, stored, bound, calls)
        item["why"] = why
        cards = []
        for e in parsed:
            card = cn.derive(e, source_of)
            if not tree_ok and card["why"] and "nama parameter tidak ditemukan" in card["why"]:
                card["why"] = TREE_WHY
            card["says"] = e.get("says")
            card["proof"] = self._proof(e["tier"], results.get(e["id"]), why or "berkas tidak cocok dengan hasil")
            cards.append(card)
        cards.sort(key=lambda x: TIER_ORDER.get(x["tier"], 9))
        item["examples"] = cards
        counts = {t: sum(1 for e in parsed if e["tier"] == t) for t in ex.TIERS}
        item["counts"] = {"calls": len(parsed), **counts}
        item["defects"] = sum(1 for x in cards if not x["showable"])
        if counts["after"] + counts["whatif"] == 0 or item["no_examples"]:
            item["warning"] = NO_NEW_WARNING
        return item
