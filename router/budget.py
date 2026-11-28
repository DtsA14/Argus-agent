"""The daily and monthly meters of ACTUAL spend (docs/reviews/SPEC_BUDGET_V2.md, part 1, rev 1): read only, nothing here gates an action.

Spend is what the stage ledgers hold, whoever started the job (the chat or the CLI): one wallet. Exactly three kinds of file are read, none through a symlink:
`jobs/*/runs/*/events.jsonl`, `jobs/*/patch_read_ledger.jsonl` and `jobs/env_propose_ledger.jsonl`. A call is one `call_id`, counted as `harness.llm.reconcile_ledger` counts it:
with its `llm_call` it is that event's `usd_nano` at that event's `ts`; with only its `llm_call_started` it is `worst_usd_nano` at the started `ts` (a call in flight, or one the
process died in). A refused `llm_call` carries no money; every other event kind is ignored. A window is UNKNOWN (never zero) when a call in it has no usable amount, or when a ledger
that cannot be read was written in it.

Days and months are calendar, in a fixed UTC+7 (WIB). Memory only: a file is read again from where it was read last, keyed by (inode, size, mtime_ns); only complete lines are
read (a write in progress is not unknown), a line that does not parse is skipped (a crash leaves such lines for ever), a shrunk file is read again from the start."""
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
LEDGERS = ("events.jsonl", "patch_read_ledger.jsonl", "env_propose_ledger.jsonl")
NOTE = "jobs directory only; days in WIB (a provider's dashboard counts days in UTC, so it differs by up to 7 hours)"


class BudgetConfigError(Exception):
    pass


def _nano_limit(v, name):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
        raise BudgetConfigError(f"chat.budget.{name} must be a finite positive number")
    return int(round(v * NANO))


def settings(cfg):
    """chat.budget as nano limits, or None when the section is absent (the meters are off). Raises BudgetConfigError for a section that cannot be used."""
    b = (cfg.get("chat") or {}).get("budget") if isinstance(cfg, dict) else None
    if b is None:
        return None
    if not isinstance(b, dict):
        raise BudgetConfigError("chat.budget must be a mapping")
    extra = sorted(set(b) - set(KEYS))
    miss = [k for k in KEYS if k not in b]
    if extra or miss:
        raise BudgetConfigError("chat.budget needs exactly " + ", ".join(KEYS) + (f" (unknown: {', '.join(map(str, extra))})" if extra else ""))
    out = {"daily_nano": _nano_limit(b["daily_usd"], "daily_usd"), "monthly_nano": _nano_limit(b["monthly_usd"], "monthly_usd")}
    w = b["warn_at"]
    if isinstance(w, bool) or not isinstance(w, (int, float)) or not math.isfinite(w) or not 0 < w <= 1:
        raise BudgetConfigError("chat.budget.warn_at must be a number above 0 and at most 1")
    if out["daily_nano"] > out["monthly_nano"]:
        raise BudgetConfigError("chat.budget.daily_usd is above monthly_usd")
    out["warn_at"] = float(w)
    return out


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
    __slots__ = ("job", "ino", "size", "mtime_ns", "offset", "started", "final", "unreadable_mtime")

    def __init__(self, job):
        self.job, self.ino, self.size, self.mtime_ns, self.offset = job, None, -1, -1, 0
        self.started, self.final, self.unreadable_mtime = {}, {}, None


def _is_ts(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _is_nano(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


class Ledgers:
    """The meters of one jobs directory. `snapshot` is cheap when warm (cached BUDGET_TTL_S) and only ever called from a request handler or `warm()`."""

    def __init__(self, jobs_dir, clock=time.time, mono=time.monotonic):
        self.jobs_dir, self.clock, self.mono = str(jobs_dir), clock, mono
        self._files, self._lock, self._cache = {}, threading.Lock(), None
        self.scanned = self.ignored = 0

    # ---- listing and reading ------------------------------------------------------------------------------------------

    def _paths(self):
        out = []
        try:
            names = os.listdir(self.jobs_dir)
        except OSError:
            return out
        for n in names:
            p = os.path.join(self.jobs_dir, n)
            if n == "env_propose_ledger.jsonl":
                out.append((p, "env"))
            elif n.startswith("j"):
                out.append((os.path.join(p, "patch_read_ledger.jsonl"), n))
                try:
                    runs = os.listdir(os.path.join(p, "runs"))
                except OSError:
                    continue
                for r in runs:
                    out.append((os.path.join(p, "runs", r, "events.jsonl"), n))
        return out

    def _read(self, path, job, now_ts):
        f = self._files.get(path) or self._files.setdefault(path, _File(job))
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            self._files.pop(path, None)
            return None
        except OSError as e:
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
            f.started[cid] = (e.get("ts"), e.get("worst_usd_nano"))
        elif kind == "llm_call" and isinstance(cid, str) and e.get("status") != "refused":
            f.final[cid] = (e.get("ts"), e.get("usd_nano"))

    def scan(self):
        """Read every ledger that changed. Returns nothing; `snapshot` sums."""
        now_ts = self.clock()
        paths = self._paths()
        seen = set()
        self.scanned, self.ignored = 0, 0
        for path, job in paths:
            seen.add(path)
            if self._read(path, job, now_ts) is not None:
                self.scanned += 1
        for gone in [p for p in self._files if p not in seen]:
            del self._files[gone]

    def warm(self):
        with self._lock:
            self.scan()

    # ---- the numbers --------------------------------------------------------------------------------------------------

    def snapshot(self, limits, now=None):
        """{day, month, unknown, ignored, scanned, note}; each window has spent_usd (None when unknown), limit_usd, spent_nano, limit_nano, warn, date/month and resets_at."""
        with self._lock:
            t = self.mono()
            if self._cache is not None and t - self._cache[0] < BUDGET_TTL_S and self._cache[2] == limits and now is None:
                return self._cache[1]
            now_ts = self.clock() if now is None else now
            self.scan()
            day0, month0, nxt_day, nxt_month = _starts(now_ts)
            dk, mk = _day_key(now_ts), _month_key(now_ts)
            day = month = 0
            unknown = {"day": None, "month": None}
            d0, m0 = day0.timestamp(), month0.timestamp()
            for f in self._files.values():
                if f.unreadable_mtime is not None:
                    if f.unreadable_mtime >= m0:
                        unknown["month"] = unknown["month"] or {"reason": "unreadable", "job": f.job}
                    if f.unreadable_mtime >= d0:
                        unknown["day"] = unknown["day"] or {"reason": "unreadable", "job": f.job}
                calls = [(ts, nano) for ts, nano in (f.final[c] for c in f.final)]
                calls += [s for c, s in f.started.items() if c not in f.final]
                for ts, nano in calls:
                    if not _is_ts(ts):
                        for w in ("day", "month"):
                            unknown[w] = unknown[w] or {"reason": "bad event time", "job": f.job}
                        continue
                    in_month, in_day = _month_key(ts) == mk, _day_key(ts) == dk
                    if not (in_month or in_day):
                        continue
                    if not _is_nano(nano):
                        if in_month:
                            unknown["month"] = unknown["month"] or {"reason": "unpriced call", "job": f.job}
                        if in_day:
                            unknown["day"] = unknown["day"] or {"reason": "unpriced call", "job": f.job}
                        continue
                    if in_month:
                        month += nano
                    if in_day:
                        day += nano
            out = {"day": self._window(day, limits["daily_nano"], limits["warn_at"], unknown["day"], date=day0.strftime("%Y-%m-%d"), resets_at=nxt_day.isoformat()),
                   "month": self._window(month, limits["monthly_nano"], limits["warn_at"], unknown["month"], date=month0.strftime("%Y-%m"), resets_at=nxt_month.isoformat()),
                   "unknown": unknown["day"] or unknown["month"], "ignored": self.ignored, "scanned": self.scanned, "note": NOTE}
            if now is None:
                self._cache = (t, out, limits)
            return out

    @staticmethod
    def _window(spent_nano, limit_nano, warn_at, unknown, **extra):
        known = unknown is None
        return {**extra, "spent_nano": spent_nano if known else None, "spent_usd": round(spent_nano / NANO, 6) if known else None,
                "limit_nano": limit_nano, "limit_usd": limit_nano / NANO, "warn": bool(known and spent_nano * 1_000_000 >= int(round(warn_at * 1_000_000)) * limit_nano),
                "unknown": unknown}
