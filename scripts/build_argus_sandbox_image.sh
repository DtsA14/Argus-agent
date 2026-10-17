#!/usr/bin/env bash
# Build the sandbox image of the `argus` environment (M6 W1): this machine's python3 and stdlib, as in
# scripts/build_local_sandbox_image.sh, plus the site-packages of a venv installed from requirements.txt. Offline:
# no registry, no download. The image has no shell, no git and no Docker; validation flags are unchanged.
#
# Reproducibility: file times, owners and order are fixed, so the same python and venv give the same root filesystem
# layer digest (rootfs). The image id still differs per build, because `docker import` records the creation time;
# the id is what runs pin, the rootfs digest is what proves a rebuild has the same content.
#
# Usage: bash scripts/build_argus_sandbox_image.sh [VENV]      (default .venv-verify)
#   -> .sandbox_image_argus (the image id) and .sandbox_image_argus.json (build metadata), both git-ignored
set -euo pipefail
cd "$(dirname "$0")/.."
VENV="${1:-.venv-verify}"
PY="$(readlink -f "$(command -v python3)")"
VER="$("$PY" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
VVER="$("$VENV/bin/python" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
[ "$VER" = "$VVER" ] || { echo "the venv's python is $VVER, this python3 is $VER" >&2; exit 1; }
STDLIB="$("$PY" -c 'import sysconfig; print(sysconfig.get_paths()["stdlib"])')"
# where this python looks for packages in isolated mode (-I): the first site- or dist-packages entry
DEST="$("$PY" -I -c 'import sys; print(next(p for p in sys.path if p.endswith(("site-packages", "dist-packages"))))')"
SITE="$("$VENV/bin/python" -c 'import site; print(site.getsitepackages()[0])')"
R="$(mktemp -d)"
trap 'rm -rf "$R"' EXIT
mkdir -p "$R/usr/bin" "$R/etc" "$R/tmp" "$R/workspace" "$R/data" "$R/proc" "$R/sys" "$R/dev"
cp "$PY" "$R/usr/bin/python$VER"; ln -s "python$VER" "$R/usr/bin/python3"
copy_libs() { for lib in $(ldd "$1" 2>/dev/null | grep -o '/[^ ]*' | sort -u); do
  [ -e "$R$lib" ] || { mkdir -p "$R$(dirname "$lib")"; cp -L "$lib" "$R$lib"; }; done; }
copy_libs "$PY"
mkdir -p "$R$(dirname "$STDLIB")"; cp -a "$STDLIB" "$R$STDLIB"; rm -rf "$R$STDLIB/test"
for so in $(find "$STDLIB/lib-dynload" -name '*.so' 2>/dev/null); do copy_libs "$so"; done
mkdir -p "$R$DEST"; cp -a "$SITE/." "$R$DEST/"
find "$R" -name '__pycache__' -prune -exec rm -rf {} +
for so in $(find "$R$DEST" -name '*.so'); do copy_libs "$so"; done
printf 'root:x:0:0:root:/root:/bin/sh\nnobody:x:65534:65534:nobody:/nonexistent:/usr/sbin/nologin\n' > "$R/etc/passwd"
printf 'root:x:0:\nnogroup:x:65534:\n' > "$R/etc/group"
find "$R" -exec touch -h -d '2026-01-01T00:00:00Z' {} +
ID="$(tar -C "$R" --sort=name --owner=0 --group=0 --numeric-owner --mtime='2026-01-01 00:00:00Z' -c . \
      | docker import -c 'ENV PATH=/usr/bin' -c 'WORKDIR /workspace' - "argus-sandbox-argus:py$VER")"
ROOTFS="$(docker image inspect --format '{{index .RootFS.Layers 0}}' "$ID")"
FREEZE="$("$VENV/bin/pip" freeze --all 2>/dev/null | LC_ALL=C sort | sha256sum | cut -d' ' -f1)"
REQ="$(sha256sum requirements.txt | cut -d' ' -f1)"
echo "$ID" > .sandbox_image_argus
printf '{"image": "%s", "rootfs": "%s", "python": "%s", "requirements_sha256": "%s", "pip_freeze_sha256": "%s", "commit": "%s", "built_at": "%s"}\n' \
  "$ID" "$ROOTFS" "$("$PY" --version 2>&1 | cut -d' ' -f2)" "$REQ" "$FREEZE" \
  "$(git rev-parse HEAD 2>/dev/null || echo unknown)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > .sandbox_image_argus.json
echo "argus environment image: $ID"
echo "argus environment rootfs: $ROOTFS"
