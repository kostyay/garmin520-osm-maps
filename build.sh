#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
./scripts/bootstrap.sh
uv run replica/clip_maps.py
./replica/build-optimized.sh
