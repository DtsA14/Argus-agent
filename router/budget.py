"""The daily and monthly meters of actual spend (docs/reviews/SPEC_BUDGET_V2.md, part 1 and B1.1 / rev 2): read only, nothing here gates an action.

Spend is what the ledgers hold, whoever started the job (the chat, the CLI, an experiment): one wallet per platform. A call costs what its bill says: the event's `usd_reported_nano`
(the gateway's own cost) when it is a non negative integer, else its `usd_nano` (the harness's count, exact for a direct API); a call that only started counts `worst_usd_nano`
(`harness.llm.reconcile_ledger`'s `unknown_after_crash`). A refused `llm_call` carries no money; every other event kind is ignored. A window is UNKNOWN (never zero) when a call in it
has no usable amount, or when a ledger that cannot be read was written in it.

Sources: the chat's own jobs directory (label "Argus jobs", always first) and the `chat.budget.sources` of the config, each a `jobs` layout (`jobs/*/runs/*/events.jsonl`,
`jobs/*/patch_read_ledger.jsonl`, `jobs/env_propose_ledger.jsonl`) or a `flat` one (`events.jsonl` or `*ledger.jsonl` at most 3 directories deep, skipping fixture and checkout directories).
No symlink is followed. A call is identified by (call_id, ts to the millisecond) and counts once, for the first source that holds it (copies of a jobs directory are harmless).

Days and months are calendar, in a fixed UTC+7 (WIB). Memory only: a file is read again from where it was read last, keyed by (inode, size, mtime_ns); only complete lines are read
(a write in progress is not unknown), a line that does not parse is skipped (a crash leaves such lines for ever), a shrunk file is read again from the start."""
import json
import math
import os
import stat
import threading
import time
from datetime import datetime, timedelta, timezone

WIB = timezone(timedelta(hours=7))
NANO = 10 ** 9
BUDGET_TTL_S = 5.0
KEYS = ("daily_usd", "monthly_usd", "warn_at")
OPTIONAL = ("sources",)
OWN = "Argus jobs"
SOURCES_MAX, LABEL_MAX, FLAT_DEPTH = 40, 40, 3
FLAT_SKIP = {".git", "node_modules", "fixtures", "source", "workspace", "root"}
NOTE = ("the ledgers of the listed sources; days in WIB (a provider's dashboard counts days in UTC, so it differs by up to 7 hours and is the truth for its own wallet)")
PLATFORMS = {"openrouter": "OpenRouter", "deepseek": "DeepSeek", "anthropic": "Anthropic"}


class BudgetConfigError(Exception):
    pass


def _nano_limit(v, name):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
        raise BudgetConfigError(f"chat.budget.{name} must be a finite positive number")
    return int(round(v * NANO))


def _sources(raw):
    if raw is None:
        return []
    if not isinstance(raw, list) or len(raw) > SOURCES_MAX:
        raise BudgetConfigError(f"chat.budget.sources must be a list of at most {SOURCES_MAX} entries")
    out, labels = [], {OWN}
    for s in raw:
        if not isinstance(s, dict) or set(s) != {"label", "path", "layout"}:
            raise BudgetConfigError("a chat.budget source has exactly label, path and layout")
        label, path, layout = s["label"], s["path"], s["layout"]
        if not isinstance(label, str) or not label.strip() or len(label) > LABEL_MAX or label in labels:
            raise BudgetConfigError("a chat.budget source label is a unique non empty text of at most 40 characters")
        if not isinstance(path, str) or not os.path.isabs(os.path.expanduser(path)):
            raise BudgetConfigError(f"chat.budget source {label!r}: the path must be absolute (a leading ~ is expanded)")
        if layout not in ("jobs", "flat"):
            raise BudgetConfigError(f"chat.budget source {label!r}: layout is jobs or flat")
        labels.add(label)
        out.append((label, os.path.expanduser(path), layout))
    return out


def settings(cfg):
    """chat.budget as nano limits and the listed sources, or None when the section is absent (the meters are off). Raises BudgetConfigError for a section that cannot be used."""
    b = (cfg.get("chat") or {}).get("budget") if isinstance(cfg, dict) else None
    if b is None:
        return None
    if not isinstance(b, dict):
        raise BudgetConfigError("chat.budget must be a mapping")
    extra = sorted(set(b) - set(KEYS) - set(OPTIONAL))
    miss = [k for k in KEYS if k not in b]
    if extra or miss:
        raise BudgetConfigError("chat.budget needs " + ", ".join(KEYS) + " (and optionally " + ", ".join(OPTIONAL) + ")" + (f"; unknown: {', '.join(map(str, extra))}" if extra else ""))
    out = {"daily_nano": _nano_limit(b["daily_usd"], "daily_usd"), "monthly_nano": _nano_limit(b["monthly_usd"], "monthly_usd")}
    w = b["warn_at"]
    if isinstance(w, bool) or not isinstance(w, (int, float)) or not math.isfinite(w) or not 0 < w <= 1:
        raise BudgetConfigError("chat.budget.warn_at must be a number above 0 and at most 1")
    if out["daily_nano"] > out["monthly_nano"]:
        raise BudgetConfigError("chat.budget.daily_usd is above monthly_usd")
    out["warn_at"] = float(w)
    out["sources"] = _sources(b.get("sources"))
    return out


def platform_of(model):
    """The platform of a call: the prefix of its model before the first colon, 'Other' when there is none."""
    if not isinstance(model, str) or ":" not in model or not model.split(":", 1)[0].strip():
        return "Other"
    p = model.split(":", 1)[0].strip().lower()
    return PLATFORMS.get(p) or p.title()


def _day_key(ts):
    d = datetime.fromtimestamp(ts, WIB)
    return (d.year, d.month, d.day)


def _month_key(ts):
    d = datetime.fromtimestamp(ts, WIB)
    return (d.year, d.month)


def _starts(now):
    d = datetime.fromtimestamp(now, WIB)
    day0 = d.replace(hour=0, minute=0, second=0, microsecond=0)
    month0 = day0.replace(day=1)
    nxt_day = day0 + timedelta(days=1)
    nxt_month = (month0.replace(year=month0.year + 1, month=1) if month0.month == 12 else month0.replace(month=month0.month + 1))
    return day0, month0, nxt_day, nxt_month


class _File:
    __slots__ = ("job", "source", "ino", "size", "mtime_ns", "offset", "started", "final", "unreadable_mtime")

    def __init__(self, job, source):
        self.job, self.source, self.ino, self.size, self.mtime_ns, self.offset = job, source, None, -1, -1, 0
        self.started, self.final, self.unreadable_mtime = {}, {}, None


def _is_ts(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _is_nano(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


class Ledgers:
    """The meters of one jobs directory and its extra sources. `snapshot` is cheap when warm (cached BUDGET_TTL_S) and only ever called from a request handler or `warm()`."""

    def __init__(self, jobs_dir, clock=time.time, mono=time.monotonic):
        self.jobs_dir, self.clock, self.mono = str(jobs_dir), clock, mono
        self._files, self._lock, self._cache = {}, threading.Lock(), None
        self.scanned = self.ignored = 0
        self.sources_info, self._order = [], [OWN]

    # ---- listing and reading ------------------------------------------------------------------------------------------

    @staticmethod
    def _jobs_layout(root, label, out):
        try:
            names = os.listdir(root)
        except OSError:
            return False
        for n in names:
            p = os.path.join(root, n)
            if n == "env_propose_ledger.jsonl":
                out.append((p, label, "env"))
            elif n.startswith("j"):
                out.append((os.path.join(p, "patch_read_ledger.jsonl"), label, n))
                try:
                    runs = os.listdir(os.path.join(p, "runs"))
                except OSError:
                    continue
                for r in runs:
                    out.append((os.path.join(p, "runs", r, "events.jsonl"), label, n))
        return True

    def _flat_layout(self, root, label, out):
        if not os.path.isdir(root) or os.path.islink(root):
            return False

        def walk(d, depth):
            try:
                it = list(os.scandir(d))
            except OSError:
                return
            for e in it:
                try:
                    if e.is_symlink():
                        self.ignored += 1
                        continue
                    if e.is_dir():
                        if depth < FLAT_DEPTH and e.name not in FLAT_SKIP:
                            walk(e.path, depth + 1)
                    elif e.name == "events.jsonl" or e.name.endswith("ledger.jsonl"):
                        out.append((e.path, label, os.path.relpath(d, root)))
                except OSError:
                    continue
        walk(root, 0)
        return True

    def _paths(self, sources):
        out, info = [], []
        for label, root, layout in [(OWN, self.jobs_dir, "jobs")] + list(sources):
            present = self._jobs_layout(root, label, out) if layout == "jobs" else self._flat_layout(root, label, out)
            info.append({"label": label, "missing": not present})
        self.sources_info = info
        return out

    def _read(self, path, job, source, now_ts):
        f = self._files.get(path)
        if f is None or f.source != source:
            f = self._files[path] = _File(job, source)
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except (FileNotFoundError, NotADirectoryError):               # no such ledger (a plain file named j*.out beside the job directories is no job)
            self._files.pop(path, None)
            return None
        except OSError:
            if os.path.islink(path):
                self.ignored += 1                                   # a symlink is no ledger: not followed, not read, not unknown
                self._files.pop(path, None)
                return None
            try:
                mt = os.stat(path).st_mtime
            except OSError:
                mt = now_ts                                          # not even stat'ed: unknown in every window
            f.unreadable_mtime = mt
            return f
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode):
                self.ignored += 1
                self._files.pop(path, None)
                return None
            f.unreadable_mtime = None
            if f.ino == st.st_ino and f.size == st.st_size and f.mtime_ns == st.st_mtime_ns:
                return f
            if f.ino != st.st_ino or st.st_size < f.offset:
                f.offset, f.started, f.final = 0, {}, {}
            try:
                chunk = os.pread(fd, st.st_size - f.offset, f.offset)
            except OSError:
                f.unreadable_mtime = st.st_mtime
                return f
            cut = chunk.rfind(b"\n")
            if cut >= 0:
                for line in chunk[:cut].split(b"\n"):
                    self._line(f, line)
                f.offset += cut + 1
            f.ino, f.size, f.mtime_ns = st.st_ino, st.st_size, st.st_mtime_ns
            return f
        finally:
            os.close(fd)

    @staticmethod
    def _line(f, line):
        try:
            e = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            return                                                    # a broken line (a crash, repaired by a newline) is skipped, as the harness's parse_lines does
        if not isinstance(e, dict):
            return
        kind, cid = e.get("event"), e.get("call_id")
        if kind == "llm_call_started" and isinstance(cid, str):
            f.started[cid] = (e.get("ts"), e.get("worst_usd_nano"), platform_of(e.get("model")))
        elif kind == "llm_call" and isinstance(cid, str) and e.get("status") != "refused":
            rep = e.get("usd_reported_nano")
            f.final[cid] = (e.get("ts"), rep if _is_nano(rep) else e.get("usd_nano"), platform_of(e.get("model")))

    def scan(self, sources=()):
        """Read every ledger that changed. `snapshot` sums."""
        now_ts = self.clock()
        paths = self._paths(sources)
        seen, self.scanned = set(), 0
        for path, label, job in paths:
            seen.add(path)
            if self._read(path, job, label, now_ts) is not None:
                self.scanned += 1
        for gone in [p for p in self._files if p not in seen]:
            del self._files[gone]
        self._order = [OWN] + [label for label, _p, _l in sources]

    def warm(self, sources=()):
        with self._lock:
            self.scan(sources)

    # ---- the numbers --------------------------------------------------------------------------------------------------

    def snapshot(self, limits, now=None):
        """{day, month, unknown, ignored, scanned, sources, note}; each window has spent_usd (None when unknown), limit_usd, spent_nano, limit_nano, warn, by_platform and by_source."""
        with self._lock:
            t = self.mono()
            if self._cache is not None and t - self._cache[0] < BUDGET_TTL_S and self._cache[2] == limits and now is None:
                return self._cache[1]
            now_ts = self.clock() if now is None else now
            sources = limits.get("sources", [])
            self.ignored = 0
            self.scan(sources)
            day0, month0, nxt_day, nxt_month = _starts(now_ts)
            dk, mk = _day_key(now_ts), _month_key(now_ts)
            tot, plat, src = {"day": 0, "month": 0}, {"day": {}, "month": {}}, {"day": {}, "month": {}}
            unknown = {"day": None, "month": None}
            d0, m0 = day0.timestamp(), month0.timestamp()
            counted = set()
            rank = {label: i for i, label in enumerate(self._order)}
            for f in sorted(self._files.values(), key=lambda f: rank.get(f.source, 10 ** 6)):          # the first source in order holds a call that several hold
                if f.unreadable_mtime is not None:
                    if f.unreadable_mtime >= m0:
                        unknown["month"] = unknown["month"] or {"reason": "unreadable", "job": f.job, "source": f.source}
                    if f.unreadable_mtime >= d0:
                        unknown["day"] = unknown["day"] or {"reason": "unreadable", "job": f.job, "source": f.source}
                calls = list(f.final.items()) + [(c, v) for c, v in f.started.items() if c not in f.final]
                for cid, (ts, nano, platform) in calls:
                    if not _is_ts(ts):
                        for w in ("day", "month"):
                            unknown[w] = unknown[w] or {"reason": "bad event time", "job": f.job, "source": f.source}
                        continue
                    in_month, in_day = _month_key(ts) == mk, _day_key(ts) == dk
                    if not (in_month or in_day):
                        continue
                    key = (cid, round(ts, 3))
                    if key in counted:
                        continue
                    counted.add(key)
                    if not _is_nano(nano):
                        for w, inside in (("month", in_month), ("day", in_day)):
                            if inside:
                                unknown[w] = unknown[w] or {"reason": "unpriced call", "job": f.job, "source": f.source}
                        continue
                    for w, inside in (("month", in_month), ("day", in_day)):
                        if inside:
                            tot[w] += nano
                            plat[w][platform] = plat[w].get(platform, 0) + nano
                            src[w][f.source] = src[w].get(f.source, 0) + nano
            per_src = {}
            for f in self._files.values():
                per_src[f.source] = per_src.get(f.source, 0) + 1
            info = [{"label": i["label"], "missing": i["missing"], "scanned": per_src.get(i["label"], 0)} for i in self.sources_info]
            out = {"day": self._window(tot["day"], limits["daily_nano"], limits["warn_at"], unknown["day"], plat["day"], src["day"], date=day0.strftime("%Y-%m-%d"), resets_at=nxt_day.isoformat()),
                   "month": self._window(tot["month"], limits["monthly_nano"], limits["warn_at"], unknown["month"], plat["month"], src["month"], date=month0.strftime("%Y-%m"), resets_at=nxt_month.isoformat()),
                   "unknown": unknown["day"] or unknown["month"], "ignored": self.ignored, "scanned": self.scanned, "sources": info, "note": NOTE}
            if now is None:
                self._cache = (t, out, limits)
            return out

    @staticmethod
    def _window(spent_nano, limit_nano, warn_at, unknown, by_platform, by_source, **extra):
        known = unknown is None
        return {**extra, "spent_nano": spent_nano if known else None, "spent_usd": round(spent_nano / NANO, 6) if known else None,
                "limit_nano": limit_nano, "limit_usd": limit_nano / NANO, "warn": bool(known and spent_nano * 1_000_000 >= int(round(warn_at * 1_000_000)) * limit_nano),
                "by_platform": dict(sorted(by_platform.items(), key=lambda kv: -kv[1])) if known else None,
                "by_source": dict(sorted(by_source.items(), key=lambda kv: -kv[1])) if known else None, "unknown": unknown}
