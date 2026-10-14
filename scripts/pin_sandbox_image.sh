#!/usr/bin/env bash
# Pull the sandbox image and pin it to its digest, for this machine (e.g. the OCI VM).
# Writes .sandbox_image (git-ignored), which verify.sh and the harness pick up via ARGUS_SANDBOX_IMAGE.
# Usage: bash scripts/pin_sandbox_image.sh [image]      (default python:3.13-slim)
set -euo pipefail
cd "$(dirname "$0")/.."
IMAGE="${1:-python:3.13-slim}"
docker pull "$IMAGE"
PINNED="$(docker image inspect --format '{{index .RepoDigests 0}}' "$IMAGE")"
case "$PINNED" in *@sha256:*) ;; *) echo "could not determine a digest for $IMAGE" >&2; exit 1;; esac
echo "$PINNED" > .sandbox_image
echo "pinned: $PINNED"
echo "arch:   $(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$PINNED")"
echo "Run 'export ARGUS_SANDBOX_IMAGE=$PINNED' to use it outside verify.sh, or set sandbox.image in config.yaml."
