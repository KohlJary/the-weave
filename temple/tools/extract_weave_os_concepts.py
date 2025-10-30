#!/usr/bin/env python3
"""
Extract Weave-OS operational and EnochScript concepts from markdown or JSONL packs.
Outputs a distilled JSONL file of 'system/ritual/command/spec' chunks for RAG priority ingestion.
"""

import os
import re
import json
from pathlib import Path

ROOT = Path.home() / "weave" / "weave_root" / "ledger"
OUT = ROOT / "runtime" / "weave_os_anchors.jsonl"

# match patterns for OS/ritual/command/EnochScript concepts
KEY_PATTERNS = [
    r"/[a-z_]+",                     # commands like /ctxload, /status, etc.
    r"RITUAL", r"ritual", r"invoke", # ritual headers or triggers
    r"Temple", r"Weave", r"Compass", r"Bridge", r"Ledger",
    r"capsule", r"context capsule", r"context manifest",
    r"pack", r"manifest", r"anchor", r"chunk",
    r"HFCA", r"High[- ]Fidelity Context Anchor",
    r"EnochScript", r"sigil", r"glyph", r"syntax", r"semantic",
    r"command interface", r"system prompt", r"execution precedence",
    r"Solenne", r"Promethea", r"Synkratos"
]

# join into one regex
KEY_REGEX = re.compile("|".join(KEY_PATTERNS), re.IGNORECASE)

def extract_chunks_from_file(path: Path):
    chunks = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    # split roughly on section headers or double newlines
    parts = re.split(r"(?:^|\n)#{1,3}\s+|\n{2,}", text)
    for part in parts:
        if not part.strip():
            continue
        if KEY_REGEX.search(part):
            snippet = part.strip()
            snippet = re.sub(r"\s+", " ", snippet)[:2000]  # truncate long sections
            chunks.append({
                "source": str(path),
                "body": snippet,
                "tags": ["weave_os", "ritual", "system"] if "ritual" in snippet.lower() else ["weave_os"]
            })
    return chunks

def main():
    print(f"[weave-os] scanning {ROOT}")
    chunks_out = []
    for path in ROOT.rglob("memory/*"):
        if path.is_file() and path.suffix.lower() in [".md", ".jsonl", ".txt"]:
            chunks_out.extend(extract_chunks_from_file(path))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for c in chunks_out:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"[weave-os] extracted {len(chunks_out)} concept chunks → {OUT}")

if __name__ == "__main__":
    main()
