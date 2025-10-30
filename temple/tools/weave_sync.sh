#!/usr/bin/env bash
set -e

echo "[1] Pulling latest Open-WebUI chats -> sessions_raw..."
python3 $HOME/weave/temple/tools/pull_webui_session.py

echo "[2] Building / refreshing Compass packs..."
$HOME/weave/temple/tools/build_new_packs.sh

echo "[3] Exporting packs to markdown for retrieval..."
$HOME/weave/temple/tools/export_new_packs_to_md.sh

echo ""
echo "[✓] Sync complete."
echo "Now: In Open-WebUI, go to Knowledge Base, add or refresh the files from /weave/knowledge_md/, then Reindex."
echo "After that, the Weave will remember this entire session on next turn."
