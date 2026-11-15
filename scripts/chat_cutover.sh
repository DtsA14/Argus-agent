#!/usr/bin/env bash
# SPEC_CHAT_APP 13.7 item 11 (C4b): move the chat from 127.0.0.1:8712 to 127.0.0.1:8711 and retire argus-control.
#
#   scripts/chat_cutover.sh check             read only: is it safe to cut over now?
#   scripts/chat_cutover.sh apply [--yes]     the cutover (prints what it would do without --yes)
#   scripts/chat_cutover.sh post  [JOB_ID]    read only: did it work? (JOB_ID: a job to open through the Decide link)
#   scripts/chat_cutover.sh rollback [--yes]  back to chat on 8712 and argus-control on 8711
#
# Light: systemctl, ss, curl and one small python read of the jobs directory. It never touches ~/.ssh/authorized_keys (the
# permitopen of 8712 is removed by hand, after `post` passes), never reads a key file, never starts a model or a job.
set -euo pipefail

LIVE="${ARGUS_LIVE:-$HOME/pilot3a_live}"
UNITD="$HOME/.config/systemd/user/argus-chat.service.d"
DROPIN="$UNITD/port.conf"
PY="$LIVE/.venv-verify/bin/python"
ok()   { printf 'ok    %s\n' "$*"; }
bad()  { printf 'FAIL  %s\n' "$*"; FAILED=1; }
note() { printf '      %s\n' "$*"; }
FAILED=0

main_pid() { systemctl --user show -p MainPID --value "$1"; }
listener_pid() {   # the pid listening on 127.0.0.1:$1, or empty
  ss -ltnpH "sport = :$1" 2>/dev/null | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | head -1
}

check() {
  echo "== pre-flight (13.7 item 11 b)"
  # 1. the live checkout has the merged C4a code
  if [ -d "$LIVE/.git" ] || [ -f "$LIVE/.git" ]; then
    git -C "$LIVE" fetch -q origin 2>/dev/null || true
    here=$(git -C "$LIVE" rev-parse HEAD); there=$(git -C "$LIVE" rev-parse origin/main 2>/dev/null || echo none)
    if [ "$here" = "$there" ]; then ok "live checkout is at origin/main (${here:0:9})"; else bad "live checkout ${here:0:9} is not origin/main ${there:0:9}: git pull --ff-only there first"; fi
    if grep -q "names_for" "$LIVE/router/chat.py"; then ok "router/chat.py has the per-port binding (C4a)"; else bad "router/chat.py is older than C4a"; fi
  else
    bad "no checkout at $LIVE"
  fi
  # 2. both services run, each with only its serve process in its control group
  for u in argus-control argus-chat; do
    if systemctl --user is-active --quiet "$u.service"; then ok "$u is active"; else note "$u is not active (control may already be retired)"; fi
    n=$(systemd-cgls --full --user-unit "$u.service" --no-pager 2>/dev/null | grep -c -E '[0-9]+ ' || true)
    kids=$(systemd-cgls --full --user-unit "$u.service" --no-pager 2>/dev/null | grep -E '[0-9]+ ' | grep -v -E 'scripts/argus.py (control|chat) serve' | grep -v -E '^\S*─?\s*$' || true)
    if [ -z "$kids" ]; then ok "$u: only its serve process in the control group"; else bad "$u has other processes (a run a restart would kill):"; echo "$kids" | sed 's/^/        /'; fi
  done
  # 3. no job a restart would strand
  if [ -x "$PY" ]; then
    out=$("$PY" - "$LIVE" <<'PY'
import json, os, sys
live = sys.argv[1]
sys.path.insert(0, live)
from router import job as rj, issue as ri, research as rr
running = {ri.WRITING, rj.DRAFTING, *rr.RUNNING}
jobs = os.path.join(live, "jobs")
found = []
for n in sorted(os.listdir(jobs), reverse=True)[:300]:
    try:
        d = json.load(open(os.path.join(jobs, n, "job.json")))
    except (OSError, ValueError):
        continue
    if isinstance(d, dict) and d.get("state") in running:
        found.append(f"{n} {d.get('kind')} {d.get('state')}")
print("\n".join(found))
PY
    ) || out="?"
    if [ -z "$out" ]; then ok "no job is WRITING, DRAFTING or running research"; else bad "jobs in a running state (a restart kills their runs):"; echo "$out" | sed 's/^/        /'; fi
  else
    bad "no python at $PY"
  fi
  # 4. ports
  cp=$(listener_pid 8711); hp=$(listener_pid 8712)
  if [ -n "$cp" ] && [ "$cp" = "$(main_pid argus-control.service)" ]; then ok "8711 is argus-control (pid $cp)"; else note "8711 listener: ${cp:-none}"; fi
  if [ -n "$hp" ] && [ "$hp" = "$(main_pid argus-chat.service)" ]; then ok "8712 is argus-chat (pid $hp)"; else note "8712 listener: ${hp:-none}"; fi
  # 5. the rollback is possible
  [ -e "$HOME/.config/systemd/user/argus-control.service" ] && ok "argus-control.service is still installed (rollback possible)" || bad "argus-control.service is gone"
  ls "$HOME"/.ssh/authorized_keys.bak-* >/dev/null 2>&1 && ok "an authorized_keys backup exists" || note "no ~/.ssh/authorized_keys.bak-* yet: make one before step 7"
  echo
  [ "$FAILED" = 0 ] && echo "SAFE to cut over." || { echo "NOT safe yet."; exit 1; }
}

apply() {
  local yes="${1:-}"
  run() { if [ "$yes" = "--yes" ]; then echo "+ $*"; "$@"; else echo "would: $*"; fi; }
  echo "== cutover ($([ "$yes" = "--yes" ] && echo LIVE || echo dry run: add --yes to do it))"
  if [ "$yes" = "--yes" ]; then check || { echo "refusing: pre-flight failed"; exit 1; }; fi
  echo "-- 1. the drop-in (no effect until daemon-reload)"
  if [ "$yes" = "--yes" ]; then
    mkdir -p "$UNITD"
    cat > "$DROPIN" <<EOF
# SPEC_CHAT_APP 13.7 item 11: the chat takes port 8711 and replaces argus-control. Remove this file to roll back.
[Unit]
Conflicts=argus-control.service
[Service]
ExecStart=
ExecStart=%h/pilot3a_live/.venv-verify/bin/python scripts/argus.py chat serve --port 8711
EOF
    echo "+ wrote $DROPIN"
  else
    echo "would: write $DROPIN with Conflicts=argus-control.service and ExecStart=... chat serve --port 8711"
  fi
  echo "-- 2. retire argus-control (frees 8711; stays off after a reboot)"
  run systemctl --user disable --now argus-control.service
  echo "-- 3. systemd reads the drop-in"
  run systemctl --user daemon-reload
  echo "-- 4. the chat restarts on 8711"
  run systemctl --user restart argus-chat.service
  if [ "$yes" = "--yes" ]; then sleep 3; post || { echo "post-check failed: run '$0 rollback --yes'"; exit 1; }; fi
  echo
  echo "Left for you: open the page on the phone (post-check below), THEN remove permitopen 8712 from the iphone-viewer key"
  echo "(back up authorized_keys first) and the 8712 forward in Termius. The phone-termius-shell key does not change."
}

post() {
  local job="${1:-}"
  echo "== post-check (13.7 item 11 d, e)"
  cp=$(listener_pid 8711); cm=$(main_pid argus-chat.service)
  if [ -n "$cp" ] && [ "$cp" = "$cm" ]; then ok "8711 is argus-chat (pid $cp)"; else bad "8711 listener ${cp:-none} is not argus-chat ($cm)"; fi
  if [ -z "$(listener_pid 8712)" ]; then ok "nothing listens on 8712"; else bad "something still listens on 8712"; fi
  if ss -ltnH 2>/dev/null | grep -E '0\.0\.0\.0:871[12]|\[::\]:871[12]' >/dev/null; then bad "a listener on 0.0.0.0 or ::"; else ok "no listener on 0.0.0.0 or ::"; fi
  systemctl --user is-active --quiet argus-control.service && bad "argus-control is still active" || ok "argus-control is not running"
  systemctl --user is-enabled --quiet argus-control.service 2>/dev/null && bad "argus-control is still enabled" || ok "argus-control is not enabled (a reboot will not bring it back)"
  for host in 127.0.0.1:8711 localhost:8711; do
    code=$(curl -s -o /dev/null -w '%{http_code}' -H "Host: $host" http://127.0.0.1:8711/api/status || true)
    [ "$code" = 200 ] && ok "GET /api/status with Host $host -> 200" || bad "GET /api/status with Host $host -> $code"
    csp=$(curl -s -D - -o /dev/null -H "Host: $host" http://127.0.0.1:8711/ | tr -d '\r' | grep -i '^content-security-policy' || true)
    case "$csp" in *"http://$host/static/app.js"*) ok "the CSP names http://$host/static/app.js";; *) bad "the CSP does not name http://$host/static/app.js";; esac
  done
  for host in 127.0.0.1:8712 localhost:8712 127.0.0.1:8710 evil.test:8711; do
    code=$(curl -s -o /dev/null -w '%{http_code}' -H "Host: $host" http://127.0.0.1:8711/api/status || true)
    [ "$code" = 421 ] && ok "Host $host -> 421" || bad "Host $host -> $code (expected 421)"
  done
  if [ -n "$job" ]; then
    for host in 127.0.0.1:8711 localhost:8711; do
      code=$(curl -s -o /dev/null -w '%{http_code}' -H "Host: $host" -H 'Sec-Fetch-Site: same-site' -H 'Sec-Fetch-Mode: navigate' "http://127.0.0.1:8711/jobs/$job" || true)
      [ "$code" = 200 ] && ok "the Decide link /jobs/$job with Host $host -> 200" || bad "the Decide link with Host $host -> $code"
    done
  else
    note "pass a job id to also test the Decide link: $0 post j2026..."
  fi
  echo
  [ "$FAILED" = 0 ] && echo "POST-CHECK passed. On the phone: open http://127.0.0.1:8711 and http://localhost:8711/jobs/<id>, press Reject then Batal once on each." || { echo "POST-CHECK FAILED."; return 1; }
}

rollback() {
  local yes="${1:-}"
  run() { if [ "$yes" = "--yes" ]; then echo "+ $*"; "$@"; else echo "would: $*"; fi; }
  echo "== rollback ($([ "$yes" = "--yes" ] && echo LIVE || echo dry run: add --yes to do it))"
  run rm -f "$DROPIN"
  run systemctl --user daemon-reload
  run systemctl --user restart argus-chat.service
  run systemctl --user enable --now argus-control.service
  if [ "$yes" = "--yes" ]; then
    sleep 3
    [ "$(listener_pid 8711)" = "$(main_pid argus-control.service)" ] && ok "8711 is argus-control again" || bad "8711 is not argus-control"
    [ "$(listener_pid 8712)" = "$(main_pid argus-chat.service)" ] && ok "8712 is argus-chat again" || bad "8712 is not argus-chat"
    echo "If you already removed permitopen 8712 from the key, add it back by hand (the backup is ~/.ssh/authorized_keys.bak-*)."
  fi
}

case "${1:-}" in
  check) check ;;
  apply) shift; apply "${1:-}" ;;
  post) shift; post "${1:-}" ;;
  rollback) shift; rollback "${1:-}" ;;
  *) sed -n '2,11p' "$0"; exit 2 ;;
esac
