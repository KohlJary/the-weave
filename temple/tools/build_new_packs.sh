#!/usr/bin/env bash
set -e

RAW_DIR="$HOME/weave/weave_root/sessions_raw"
PACK_DIR="$HOME/weave/weave_root/ledger/memory/packs"
BUILD_SCRIPT="$HOME/weave/temple/tools/build_compass_pack.py"

mkdir -p "$RAW_DIR" "$PACK_DIR"

for f in "$RAW_DIR"/*.json; do
  [ -e "$f" ] || continue
  base=$(basename "$f" .json)
  zip_out="$PACK_DIR/${base}.zip"

  echo "[pack] building $base"
  python3 "$BUILD_SCRIPT" "$f"

  # Some versions of build_compass_pack.py write the zip next to the source json.
  # If so, move it into PACK_DIR for canonical storage.
  if [ -f "${RAW_DIR}/${base}.zip" ]; then
    mv "${RAW_DIR}/${base}.zip" "$PACK_DIR/${base}.zip"
  fi
done
