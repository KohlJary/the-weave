#!/usr/bin/env bash
# usage: ./export_for_openwebui.sh /path/to/Promethea_pack_v1.zip

ZIP="$1"
BASENAME=$(basename "$ZIP" _pack_v1.zip)   # e.g. "Promethea"
WORKDIR="/tmp/${BASENAME}_unpack"

rm -rf "$WORKDIR"
mkdir -p "$WORKDIR"

unzip -q "$ZIP" -d "$WORKDIR"

OUT_MD="${BASENAME}_knowledge.md"

{
  echo "# ${BASENAME} — Compass Internal Memory"
  echo ""
  echo "_sensitivity: internal_only_"
  echo ""

  # iterate each JSON line (each chunk) and pretty print it
  while IFS= read -r line; do
    id=$(echo "$line" | jq -r '.id')
    ts=$(echo "$line" | jq -r '.time_start_utc')
    title=$(echo "$line" | jq -r '.thread_title')
    people=$(echo "$line" | jq -r '.participants | join(", ")')
    summary=$(echo "$line" | jq -r '.local_summary')
    body=$(echo "$line" | jq -r '.body')

    echo "## $title / $id"
    echo "**time_start_utc:** $ts"
    echo "**participants:** $people"
    echo ""
    echo "**summary:** $summary"
    echo ""
    echo "### body"
    echo "$body"
    echo ""
    echo "---"
    echo ""
  done < "${WORKDIR}/rag_chunks_internal.jsonl"
} > "$OUT_MD"

echo "Wrote $OUT_MD"
