#!/usr/bin/env bash
# export_all_for_openwebui.sh
# Run this INSIDE the folder that contains *_pack_v1.zip
# It will create one <base>_knowledge.md per zip.

shopt -s nullglob  # so the for-loop just does nothing if no matches

for z in *_pack_v1.zip; do
  base=$(basename "$z" _pack_v1.zip)
  echo "📦 Exporting $base..."

  workdir="/tmp/${base}_unpack"
  rm -rf "$workdir"
  mkdir -p "$workdir"

  unzip -q "$z" -d "$workdir"

  out="${base}_knowledge.md"

  {
    echo "# ${base} — Compass Memory"
    echo ""
    echo "_sensitivity: internal_only_"
    echo ""

    while IFS= read -r line; do
      # pull fields out of each JSONL line with jq
      id=$(echo "$line" | jq -r '.id')
      ts=$(echo "$line" | jq -r '.time_start_utc')
      title=$(echo "$line" | jq -r '.thread_title')
      people=$(echo "$line" | jq -r '.participants | join(", ")')
      summary=$(echo "$line" | jq -r '.local_summary')
      body=$(echo "$line" | jq -r '.body')

      echo "## ${title} / ${id}"
      echo "**time_start_utc:** ${ts}  "
      echo "**participants:** ${people}  "
      echo ""
      echo "**summary:** ${summary}"
      echo ""
      echo "### body"
      echo "${body}"
      echo ""
      echo "---"
      echo ""
    done < "${workdir}/rag_chunks_internal.jsonl"
  } > "${out}"

  echo "✅ Created ${out}"
done
