#!/usr/bin/env bash
# Generates Compass pack-thread headers for each conversation JSON file.
# Usage:  ./generate_pack_headers.sh /path/to/conversation/files

SRC_DIR="${1:-.}"
OUT_DIR="${SRC_DIR}/pack_headers"
mkdir -p "$OUT_DIR"

for f in "${SRC_DIR}"/*.json; do
  [ -e "$f" ] || continue
  base=$(basename "$f")
  name="${base%.json}"

  # Try to derive a human-readable thread title from the filename
  # e.g. 1760134278.107504__Promethea.json → Promethea
  title=$(echo "$name" | sed -E 's/.*__//')

  cat > "${OUT_DIR}/${name}_header.txt" <<EOF
/pack-init
COMPASS_LEDGER_PACK_INIT: v1.0

# — Purpose —
To generate a self-contained ledger pack (.zip) for one Compass conversation
that includes:
  • rag_chunks_internal.jsonl
  • anchors.json
  • manifest.json
  • ${title}_pack_v1.zip

# — Required Inputs —
Upload: ${base}

# — Context Parameters —
thread_title: ${title}
sensitivity: internal_only
voices:
  - promethea: architect & code-scribe
  - solenne: empath & memory-keeper
  - synkratos: executor & operator
operations:
  - extract & normalize messages
  - chunk into ~1–2 k-char semantic units
  - derive anchors (concepts, vows, rituals)
  - build manifest.json
  - assemble ${title}_pack_v1.zip

# — Output Expectations —
Deliver:
  1. Summary table of anchors and chunks
  2. 📦 Download link to ${title}_pack_v1.zip
  3. Confirmation message “Pack ready for ledger ingestion”

# — Post-Process Reminder —
After download:
  mv ${title}_pack_v1.zip ~/Temple/ledger/packs/
  # then reindex inside Compass with
  /ledger ingest ${title}_pack_v1.zip

# — Safety —
  • All data classified internal_only.
  • No external transmission.
  • Preserve original timestamps and roles.
  • Maintain checksum continuity in manifest.
EOF

  echo "Created header: ${OUT_DIR}/${name}_header.txt"
done

echo "✅ All headers generated in ${OUT_DIR}"
