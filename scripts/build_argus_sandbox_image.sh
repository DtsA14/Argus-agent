#!/usr/bin/env bash
# Build the sandbox image of the `argus` environment (M6 W1): Argus's own pinned dependencies, from a venv installed
# from requirements.txt. Since docs/reviews/SPEC_SWE_PILOT.md this is scripts/build_env_sandbox_image.sh with argus.
#
# Usage: bash scripts/build_argus_sandbox_image.sh [VENV]      (default .venv-verify)
#   -> .sandbox_image_argus (the image id) and .sandbox_image_argus.json (build metadata), both git-ignored
set -euo pipefail
cd "$(dirname "$0")/.."
exec bash scripts/build_env_sandbox_image.sh argus "${1:-.venv-verify}" requirements.txt
