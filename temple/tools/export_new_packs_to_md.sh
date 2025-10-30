#!/usr/bin/env bash
set -e

PACK_DIR="$HOME/weave/weave_root/ledger/memory/packs"
OUT_DIR="$HOME/weave/weave_root/ledger/memory/knowledge"

mkdir -p "$OUT_DIR"

for z in "$PACK_DIR"/*.zip; do
  [ -e "$z" ] || continue
  base=$(basename "$z")
  out="$OUT_DIR/${base}_knowledge.md"

  # We always rewrite, same logic as packs:
  # if conversation evolved, we want the newest rollup in retrieval.
  echo "[md] exporting $base -> $out"

  workdir="/tmp/${base}_unpack"
  rm -rf "$workdir"
  mkdir -p "$workdir"
  unzip -q "$z" -d "$workdir"

  {
    echo "# ${base} — Compass Memory"
    echo ""
    echo "_sensitivity: internal_only_"
    echo ""

    # rag_chunks_internal.jsonl is line-delimited JSON objects
    while IFS= read -r line; do
      # guard against blank lines
      [ -n "$line" ] || continue

      id=$(echo "$line" | jq -r '.id // empty')
      ts=$(echo "$line" | jq -r '.time_start_utc // empty')
      title=$(echo "$line" | jq -r '.thread_title // empty')
      people=$(echo "$line" | jq -r '.participants | join(", ") // empty')
      summary=$(echo "$line" | jq -r '.local_summary // empty')
      body=$(echo "$line" | jq -r '.body // empty')

      # skip junk lines that don't parse
      [ -n "$body" ] || continue

      echo "## ${title:-Conversation} / ${id}"
      [ -n "$ts" ] && echo "**time_start_utc:** ${ts}  "
      [ -n "$people" ] && echo "**participants:** ${people}  "
      echo ""
      [ -n "$summary" ] && {
        echo "**summary:** ${summary}"
        echo ""
      }
      echo "### body"
      echo "$body"
      echo ""
      echo "---"
      echo ""
    done < "${workdir}/rag_chunks_internal.jsonl"
  } > "$out"

  echo "[md] wrote $out"
done
