#!/usr/bin/env bash
# Build the sandbox image of a Node environment defined in environments/NAME/ (docs/reviews/SPEC_PWA_VIEWER.md E): an
# official Node image pinned by digest, package.json and its package-lock.json. The builder container is the only step
# with network: `npm ci --ignore-scripts` installs exactly the lock (npm checks every package's sha512 integrity; no
# install script runs) and the node binary and the shared libraries it needs are copied out. The image is then assembled
# on this host as scripts/build_env_from_base.sh does it: fixed times and owners, sorted tar, docker import. It holds
# node, its libraries and /node_modules (owned by root: read-only for the sandbox's nobody), the parent of /workspace,
# where Node and vite resolve packages from. No shell, no npm, no git.
#
# Usage: bash scripts/build_env_node.sh NAME [NPM_CACHE_DIR]      (default cache: ~/.cache/argus-npm)
#   -> .sandbox_image_NAME (the image id) and .sandbox_image_NAME.json (build metadata), both git-ignored.
#   The environment may be used only after scripts/check_env_image.py NAME has passed for that image id.
set -euo pipefail
cd "$(dirname "$0")/.."
NAME="${1:?usage: build_env_node.sh NAME [NPM_CACHE_DIR]}"
CACHE="${2:-$HOME/.cache/argus-npm}"
[[ "$NAME" =~ ^[a-z][a-z0-9_]{0,31}$ ]] || { echo "environment name must be lower-case: $NAME" >&2; exit 1; }
DEFS="${ARGUS_ENV_DEFS:-environments}"         # tests point these at their own directories
OUT="${ARGUS_ENV_OUT:-.}"
DEF="$DEFS/$NAME"
[ -f "$DEF/base" ] && [ -f "$DEF/package.json" ] && [ -f "$DEF/package-lock.json" ] \
  || { echo "no definition in $DEF (base, package.json, package-lock.json)" >&2; exit 1; }
BASE="$(tr -d '[:space:]' < "$DEF/base")"
[[ "$BASE" =~ ^[a-z0-9._/-]+@sha256:[0-9a-f]{64}$ ]] || { echo "$DEF/base must be an image pinned by digest: $BASE" >&2; exit 1; }
# Every locked package from the npm registry with a sha512 integrity; exact versions only in package.json.
python3 - "$DEF" <<'EOF' || exit 1
import json, re, sys
d = sys.argv[1]
pkg, lock = json.load(open(d + "/package.json")), json.load(open(d + "/package-lock.json"))
bad = [f"{k}: {v}" for s in ("dependencies", "devDependencies") for k, v in (pkg.get(s) or {}).items()
       if not re.fullmatch(r"\d+\.\d+\.\d+", str(v))]
bad += [k for k, v in lock.get("packages", {}).items() if k and not (
    str(v.get("integrity", "")).startswith("sha512-") and str(v.get("resolved", "")).startswith("https://registry.npmjs.org/"))]
if lock.get("lockfileVersion") != 3 or bad:
    sys.exit("package.json must pin exact versions and every locked package needs a registry sha512 (lockfile v3): "
             + ", ".join(bad[:10]))
EOF
mkdir -p "$CACHE"
W="$(mktemp -d)"
trap 'rm -rf "$W"' EXIT
mkdir -p "$W/root"
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e npm_config_update_notifier=false \
  -v "$(cd "$DEF" && pwd):/def:ro" -v "$CACHE:/cache" -v "$W:/out" "$BASE" \
  sh -c 'set -e; mkdir /tmp/b && cp /def/package.json /def/package-lock.json /tmp/b/ && cd /tmp/b \
         && npm ci --ignore-scripts --no-audit --no-fund --loglevel=error --cache /cache \
         && cp -a node_modules /out/root/node_modules \
         && mkdir -p /out/root/usr/local/bin && cp /usr/local/bin/node /out/root/usr/local/bin/node \
         && for l in $(ldd /usr/local/bin/node | grep -o "/[^ ]*"); do mkdir -p "/out/root$(dirname "$l")"; cp -L "$l" "/out/root$l"; done \
         && node --version > /out/node_version'
R="$W/root"
mkdir -p "$R/etc" "$R/tmp" "$R/workspace" "$R/data" "$R/proc" "$R/sys" "$R/dev"
for f in bin/sh bin/bash usr/bin/git usr/local/bin/npm; do [ ! -e "$R/$f" ] || { echo "the image would contain /$f" >&2; exit 1; }; done
printf 'root:x:0:0:root:/root:/bin/sh\nnobody:x:65534:65534:nobody:/nonexistent:/usr/sbin/nologin\n' > "$R/etc/passwd"
printf 'root:x:0:\nnogroup:x:65534:\n' > "$R/etc/group"
find "$R" -exec touch -h -d '2026-01-01T00:00:00Z' {} +
NODE="$(tr -d '[:space:]v' < "$W/node_version")"
ID="$(tar -C "$R" --sort=name --owner=0 --group=0 --numeric-owner --mtime='2026-01-01 00:00:00Z' -c . \
      | docker import -c 'ENV PATH=/usr/local/bin' -c 'WORKDIR /workspace' - "argus-sandbox-$NAME:node$NODE")"
ROOTFS="$(docker image inspect --format '{{index .RootFS.Layers 0}}' "$ID")"
echo "$ID" > "$OUT/.sandbox_image_$NAME"
printf '{"environment": "%s", "image": "%s", "rootfs": "%s", "base": "%s", "node": "%s", "lock_sha256": "%s", "commit": "%s", "built_at": "%s"}\n' \
  "$NAME" "$ID" "$ROOTFS" "$BASE" "$NODE" "$(sha256sum "$DEF/package-lock.json" | cut -d' ' -f1)" \
  "$(git rev-parse HEAD 2>/dev/null || echo unknown)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$OUT/.sandbox_image_$NAME.json"
rm -f "$OUT/.sandbox_image_$NAME.check.json"        # a new image is unchecked until scripts/check_env_image.py passes
echo "$NAME environment image: $ID"
echo "$NAME environment rootfs: $ROOTFS"
