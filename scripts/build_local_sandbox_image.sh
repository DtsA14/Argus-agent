#!/usr/bin/env bash
# Build a minimal Python sandbox image from this machine's own python3, with `docker import`.
# For environments that cannot reach a registry (the image is then identified by its content id,
# which is pinned by definition). On a normal machine prefer scripts/pin_sandbox_image.sh.
# Usage: bash scripts/build_local_sandbox_image.sh       -> writes .sandbox_image
set -euo pipefail
cd "$(dirname "$0")/.."
PY="$(readlink -f "$(command -v python3)")"
VER="$("$PY" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
STDLIB="$("$PY" -c 'import sysconfig; print(sysconfig.get_paths()["stdlib"])')"
R="$(mktemp -d)"
trap 'rm -rf "$R"' EXIT
mkdir -p "$R/usr/bin" "$R/etc" "$R/tmp" "$R/workspace" "$R/data" "$R/proc" "$R/sys" "$R/dev"
cp "$PY" "$R/usr/bin/python$VER"; ln -s "python$VER" "$R/usr/bin/python3"
copy_libs() { for lib in $(ldd "$1" 2>/dev/null | grep -o '/[^ ]*' | sort -u); do
  [ -e "$R$lib" ] || { mkdir -p "$R$(dirname "$lib")"; cp -L "$lib" "$R$lib"; }; done; }
copy_libs "$PY"
mkdir -p "$R$(dirname "$STDLIB")"; cp -a "$STDLIB" "$R$STDLIB"; rm -rf "$R$STDLIB/test"
for so in $(find "$STDLIB/lib-dynload" -name '*.so' 2>/dev/null); do copy_libs "$so"; done
printf 'root:x:0:0:root:/root:/bin/sh\nnobody:x:65534:65534:nobody:/nonexistent:/usr/sbin/nologin\n' > "$R/etc/passwd"
printf 'root:x:0:\nnogroup:x:65534:\n' > "$R/etc/group"
ID="$(tar -C "$R" -c . | docker import -c 'ENV PATH=/usr/bin' -c 'WORKDIR /workspace' - "argus-sandbox-local:py$VER")"
echo "$ID" > .sandbox_image
echo "built: argus-sandbox-local:py$VER  id: $ID"
