#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Install: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

uv sync

if [ -d fire-seg/images/train ] && [ -d fire-seg/images/val ]; then
  echo "fire-seg/ already exists. Skipping prepare_dataset.py (delete fire-seg/ to regenerate)."
else
  uv run python prepare_dataset.py
fi

uv run python train.py
