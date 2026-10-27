#!/usr/bin/env bash
# Build the sandbox image of an environment defined in environments/NAME/ from an official Python image
# (docs/reviews/SPEC_ENV_FROM_PYTHON_IMAGE.md 2.2). The builder container is the only step with network: it installs the
# exact, hashed requirements (pip --require-hashes) and copies the interpreter, the stdlib, the installed packages and
# the shared libraries they need (scripts/env_builder_copy.py). The image is then assembled on this host exactly as
# scripts/build_env_sandbox_image.sh does it: fixed times and owners, sorted tar, docker import. No shell, no pip, no git.
#
# Usage: bash scripts/build_env_from_base.sh NAME [PIP_CACHE_DIR]      (default cache: ~/.cache/argus-pip)
#   -> .sandbox_image_NAME (the image id) and .sandbox_image_NAME.json (build metadata), both git-ignored.
#   The environment may be used only after scripts/check_env_image.py NAME has passed for that image id.
set -euo pipefail
cd "$(dirname "$0")/.."
NAME="${1:?usage: build_env_from_base.sh NAME [PIP_CACHE_DIR]}"
CACHE="${2:-$HOME/.cache/argus-pip}"
[[ "$NAME" =~ ^[a-z][a-z0-9_]{0,31}$ ]] || { echo "environment name must be lower-case: $NAME" >&2; exit 1; }
DEFS="${ARGUS_ENV_DEFS:-environments}"         # tests point these at their own directories
OUT="${ARGUS_ENV_OUT:-.}"
DEF="$DEFS/$NAME"
[ -f "$DEF/base" ] && [ -f "$DEF/requirements.txt" ] || { echo "no definition in $DEF (base, requirements.txt)" >&2; exit 1; }
BASE="$(tr -d '[:space:]' < "$DEF/base")"
[[ "$BASE" =~ ^[a-z0-9._/-]+@sha256:[0-9a-f]{64}$ ]] || { echo "$DEF/base must be an image pinned by digest: $BASE" >&2; exit 1; }
BAD="$(grep -vE '^\s*(#|$)' "$DEF/requirements.txt" | grep -vE '^[A-Za-z0-9._-]+==[A-Za-z0-9.+!-]+ +--hash=sha256:[0-9a-f]{64}$' || true)"
[ -z "$BAD" ] || { echo "every requirement must be name==version --hash=sha256:...: $BAD" >&2; exit 1; }
mkdir -p "$CACHE"
W="$(mktemp -d)"
trap 'rm -rf "$W"' EXIT
mkdir -p "$W/root" "$W/site"
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e PIP_DISABLE_PIP_VERSION_CHECK=1 \
  -v "$(cd "$DEF" && pwd):/def:ro" -v "$PWD/scripts/env_builder_copy.py:/copy.py:ro" -v "$CACHE:/cache" -v "$W:/out" "$BASE" \
  sh -c 'python3 -m pip install -q --no-deps --no-compile --require-hashes --cache-dir /cache --target /out/site \
           -r /def/requirements.txt && python3 /copy.py /out/root /out/site'
R="$W/root"
mkdir -p "$R/etc" "$R/tmp" "$R/workspace" "$R/data" "$R/proc" "$R/sys" "$R/dev"
find "$R" -name '__pycache__' -prune -exec rm -rf {} +
for f in bin/sh bin/bash usr/bin/git; do [ ! -e "$R/$f" ] || { echo "the image would contain /$f" >&2; exit 1; }; done
printf 'root:x:0:0:root:/root:/bin/sh\nnobody:x:65534:65534:nobody:/nonexistent:/usr/sbin/nologin\n' > "$R/etc/passwd"
printf 'root:x:0:\nnogroup:x:65534:\n' > "$R/etc/group"
find "$R" -exec touch -h -d '2026-01-01T00:00:00Z' {} +
VER="$(ls "$R/usr/bin" | sed -n 's/^python\([0-9]\.[0-9]*\)$/\1/p' | head -1)"
ID="$(tar -C "$R" --sort=name --owner=0 --group=0 --numeric-owner --mtime='2026-01-01 00:00:00Z' -c . \
      | docker import -c 'ENV PATH=/usr/bin' -c 'WORKDIR /workspace' - "argus-sandbox-$NAME:py$VER")"
ROOTFS="$(docker image inspect --format '{{index .RootFS.Layers 0}}' "$ID")"
echo "$ID" > "$OUT/.sandbox_image_$NAME"
printf '{"environment": "%s", "image": "%s", "rootfs": "%s", "base": "%s", "python": "%s", "requirements_sha256": "%s", "commit": "%s", "built_at": "%s"}\n' \
  "$NAME" "$ID" "$ROOTFS" "$BASE" "$VER" "$(sha256sum "$DEF/requirements.txt" | cut -d' ' -f1)" \
  "$(git rev-parse HEAD 2>/dev/null || echo unknown)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$OUT/.sandbox_image_$NAME.json"
rm -f "$OUT/.sandbox_image_$NAME.check.json"        # a new image is unchecked until scripts/check_env_image.py passes
echo "$NAME environment image: $ID"
echo "$NAME environment rootfs: $ROOTFS"
