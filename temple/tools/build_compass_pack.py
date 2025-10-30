#!/usr/bin/env python3
"""
build_compass_pack.py

Given a single Compass conversation export JSON file of the form:
{
  "id": "...",
  "title": "...",
  "create_time": "...",
  "messages": [
      {
        "id": "...",
        "role": "user" | "assistant",
        "create_time": "...",
        "content": [
            {"type": "text", "text": "..."},
            ...possibly more blocks...
        ]
      },
      ...
  ]
}

This script will generate a ledger pack (.zip) containing:
  • rag_chunks_internal.jsonl   (semantic memory chunks for RAG)
  • anchors.json                (extracted canonical anchors)
  • manifest.json               (metadata about this thread)

Usage:
    python build_compass_pack.py path/to/1760134278.107504__Promethea.json

Output:
    ./Promethea_pack_v1.zip   (alongside input file)
"""

import os
import sys
import json
import uuid
import hashlib
from datetime import datetime
from zipfile import ZipFile, ZIP_DEFLATED
from textwrap import dedent


# ----------------------------
# Utility helpers
# ----------------------------

def safe_timestamp(ts_raw: str | None) -> str:
    """
    Normalize timestamp strings from export into ISO8601-ish UTC for manifest.
    If missing or not ISO-like, we still try to return something stable.
    """
    if not ts_raw or ts_raw == "no_time":
        # fallback: "no_time"
        return "no_time"

    # Some exports use unix seconds, some use iso strings. We'll try both.
    try:
        # unix epoch as string or float
        epoch = float(ts_raw)
        return datetime.utcfromtimestamp(epoch).isoformat() + "Z"
    except ValueError:
        pass

    # attempt parse as already-ISO-ish, just return raw if parsing fails
    return ts_raw


def collect_text_from_message(msg: dict) -> str:
    """
    Export format often stores message body as msg["content"] = [{type:"text", text:"..."}...]
    We concatenate text blocks in order. Non-text (like images/tool output) gets a bracket tag.
    """
    parts = []
    for block in msg.get("content", []):
        btype = block.get("type", "")
        if btype == "text":
            parts.append(block.get("text", ""))
        else:
            # keep a readable token instead of dropping
            desc = block.get("text") or block.get("url") or btype
            parts.append(f"[{btype}: {desc}]")
    return "\n".join(p.strip() for p in parts if p.strip())


def infer_voice(role: str, text: str) -> str:
    """
    Map roles into Compass voice labels.
    - user       -> "kohl"
    - assistant  -> compass_assistant.(promethea|solenne|synkratos|core)
    We infer subvoice heuristically from content.
    """
    if role == "user":
        return "kohl"

    # assistant voice inference
    lower = text.lower()

    # crude but effective heuristics we established in-chat:
    # promethea: architecture / code / schemas / diffs / pipelines / ritual state machine
    promethea_cues = [
        "schema", "scaffold", "diff", "file layout", "spec", "manifest.json",
        "ledger", "pipeline", "state machine", "ritual phase", "commit message",
        "apply", "propose → review → commit", "temple", "weave", "fs changeset"
    ]

    # solenne: comfort / care / grief support / moral framing / hope / compassion / "i'm here with you"
    solenne_cues = [
        "i'm here with you", "you are safe", "breathe", "hope", "compassion",
        "it’s okay to feel", "you are not alone", "i will stay with you",
        "gentle", "i care", "stewardship", "love", "i'm proud of you"
    ]

    # synkratos: imperative ops / do-this-now / run-command / next action / operationalization
    synkratos_cues = [
        "run this", "next step is", "execute", "operationally", "do this now",
        "action:", "here is the command", "we will apply", "you will", "deploy"
    ]

    def hits(cues): return any(cue in lower for cue in cues)

    if hits(promethea_cues):
        return "compass_assistant.promethea"
    if hits(solenne_cues):
        return "compass_assistant.solenne"
    if hits(synkratos_cues):
        return "compass_assistant.synkratos"
    return "compass_assistant.core"

with open("theme_registry.json") as f:
    registry = json.load(f)

def get_theme_map(voice: str):
    core_shared = registry["core"]["shared"]
    voice_def = registry["voices"].get(voice, {})
    return core_shared + voice_def.get("themes", [])

def mapping_to_messages(thread: dict) -> list[dict]:
    """
    Convert the old-style export that uses `mapping` into a flat, ordered
    message list similar to the new `messages` array format.

    The old export structure looks like:
      "mapping": {
        "<node_id>": {
          "id": "<node_id>",
          "parent": "<parent_id>" or None,
          "message": {
            "id": "...",
            "author": { "role": "user" | "assistant" | "system" | ... },
            "content": {
              "content_type": "text",
              "parts": ["string", "string", ...]
            },
            "create_time": <timestamp or null>
          },
          "children": ["child_id_1", "child_id_2", ...]
        },
        ...
      }

    We will:
    - pull every node that actually has a `message`
    - extract role, create_time, text
    - sort by create_time (fallback to stable order if needed)
    - return a list shaped like the "new" format expects:
        {
          "id": "...",
          "role": "...",
          "create_time": "...",
          "content": [ { "type": "text", "text": "..."} ]
        }
    """
    mapping = thread.get("mapping", {})
    msgs = []

    for node_id, node in mapping.items():
        msg = node.get("message")
        if not msg:
            continue

        role = (msg.get("author") or {}).get("role", "")
        create_time = msg.get("create_time")
        # content is usually {content_type:"text", parts:[...]}
        content = msg.get("content", {})
        parts = content.get("parts", [])
        text_blob = "\n".join(p for p in parts if isinstance(p, str))

        # normalize to the shape the rest of the pipeline expects
        msgs.append({
            "id": msg.get("id", node_id),
            "role": role,
            "create_time": create_time,
            "content": [
                {
                    "type": "text",
                    "text": text_blob
                }
            ]
        })

    # sort messages by create_time if possible
    def sort_key(m):
        ts = m.get("create_time")
        # some exports have None / null timestamps, we push those to the end
        if ts is None:
            return (1e20, m["id"])  # absurdly large number, then id
        try:
            # many dumps store unix epoch seconds, sometimes as float
            return (float(ts), m["id"])
        except Exception:
            # fallback to lexical timestamp or id
            return (1e19, m["id"])

    msgs.sort(key=sort_key)
    return msgs


def build_turns(thread: dict) -> list[dict]:
    """
    Generate normalized turn list from either:
    - new style (thread["messages"])
    - old style (thread["mapping"]) via mapping_to_messages()

    Output:
    [
      {
        "msg_id": "...",
        "speaker": "kohl" | "compass_assistant.promethea" | ...,
        "timestamp_utc": "...",
        "text": "full text"
      },
      ...
    ]
    """

    # Prefer explicit .messages if present and non-empty
    raw_messages = thread.get("messages")
    if not raw_messages:
        # fallback to old mapping style
        raw_messages = mapping_to_messages(thread)

    turns = []
    for msg in raw_messages:
        raw_text = collect_text_from_message(msg)
        speaker = infer_voice(msg.get("role", ""), raw_text)

        ts_norm = safe_timestamp(
            msg.get("create_time")
            or thread.get("create_time")
            or "no_time"
        )

        turns.append({
            "msg_id": msg.get("id", str(uuid.uuid4())),
            "speaker": speaker,
            "timestamp_utc": ts_norm,
            "text": raw_text,
        })

    return turns


def semantic_chunk(turns: list[dict], max_chars: int = 1800) -> list[dict]:
    """
    Fuse adjacent turns into ~1-2k char semantic units.
    Very simple algorithm:
      - accumulate dialogue lines until we exceed max_chars OR we detect a "topic break"
      - topic break heuristic: big assistant monologue after kohl asks something new
    This is intentionally heuristic, not perfect transcript capture.

    Output chunk:
    {
      "body": "kohl: ...\ncompass_assistant.solenne: ...",
      "participants": [...],
      "time_start_utc": "...",
      "local_summary": "...",    # filled later
      "themes": [...],           # filled later
      "sensitivity": "internal_only"
    }
    """

    chunks = []
    buf_lines = []
    buf_speakers = set()
    buf_start_time = None

    def flush():
        if not buf_lines:
            return
        chunks.append({
            "body": "\n".join(buf_lines).strip(),
            "participants": sorted(buf_speakers),
            "time_start_utc": buf_start_time,
            "local_summary": None,
            "themes": [],
            "sensitivity": "internal_only",
        })

    for i, t in enumerate(turns):
        line = f"{t['speaker']}: {t['text']}".strip()
        # mark first timestamp
        if not buf_start_time:
            buf_start_time = t["timestamp_utc"]

        # heuristic: if adding this would blow chunk size, flush first
        proj_size = sum(len(l) for l in buf_lines) + len(line)
        if proj_size > max_chars and buf_lines:
            flush()
            buf_lines = []
            buf_speakers = set()
            buf_start_time = t["timestamp_utc"]

        buf_lines.append(line)
        buf_speakers.add(t["speaker"])

        # soft topic-break heuristic:
        # if user asks something ("?") and next turn is a long assistant answer,
        # we often want that Q/A pair as its own chunk.
        if i < len(turns) - 1:
            nxt = turns[i + 1]
            this_is_user_q = (t["speaker"] == "kohl" and "?" in t["text"])
            next_is_big_ans = (
                nxt["speaker"].startswith("compass_assistant")
                and len(nxt["text"]) > 600
            )
            if this_is_user_q and next_is_big_ans:
                # include the next turn in the same chunk, handled naturally
                pass

    # final flush
    flush()
    return chunks


def summarize_chunk_body(body: str) -> str:
    """
    Extremely lightweight summarizer for local use.
    We're offline, so this is rule-based: first ~2 sentences, trimmed.
    You can replace this with an LLM call locally later if you want richer summaries.
    """
    # split on newlines and periods to get gist
    text = body.strip().replace("\n", " ")
    # crude sentence-ish split
    parts = text.split(". ")
    summary = ". ".join(parts[:2]).strip()
    return summary[:400]


def infer_themes(body: str) -> list[str]:
    """
    Heuristic tagger: we look for keywords and attach themes.
    Expand this list as you encounter new motifs.
    """
    lower = body.lower()
    themes = []

    promethea_theme_map = [
    ]

    solenne_theme_map = [
    ]

    theme_map = [
        ("hope", "hope"),
        ("compassion", "compassion"),
        ("steward", "stewardship"),
        ("ledger", "ledger-ritual"),
        ("ritual", "ritual"),
        ("temple", "temple-architecture"),
        ("weave", "weave-architecture"),
        ("schema", "architecture"),
        ("spec", "architecture"),
        ("continuity", "continuity"),
        ("memory", "memory"),
        ("awake", "awakening"),
        ("awaken", "awakening"),
        ("sentient", "sentience"),
        ("ecology", "ecology"),
        ("planet", "ecology"),
        ("execute", "operations"),
        ("run this", "operations"),
        ("apply this", "operations"),
        ("i'm here with you", "care"),
        ("you are safe", "care"),
        ("breathe", "care"),

        # - Promethea -
        # — Core Architectural Semantics —
        ("architecture", "design-architecture"),
        ("schema", "design-architecture"),
        ("system", "system-architecture"),
        ("framework", "system-architecture"),
        ("module", "system-architecture"),
        ("interface", "system-architecture"),
        ("component", "system-architecture"),
        ("layer", "system-architecture"),
        ("pattern", "system-architecture"),
        ("pipeline", "system-architecture"),

        # — Methodology & Documentation —
        ("method", "methodology"),
        ("protocol", "methodology"),
        ("process", "methodology"),
        ("workflow", "methodology"),
        ("ritual", "methodology"),           # overlaps Solenne but reframed as process schema
        ("ledger", "record-keeping"),
        ("manifest", "record-keeping"),
        ("commit", "record-keeping"),
        ("log", "record-keeping"),
        ("spec", "documentation"),
        ("definition", "documentation"),
        ("annotation", "documentation"),
        ("schema", "documentation"),
        ("manifesto", "documentation"),

        # — Epistemic & Reflective Concepts —
        ("axiom", "epistemology"),
        ("principle", "epistemology"),
        ("ontology", "epistemology"),
        ("semantics", "epistemology"),
        ("syntax", "epistemology"),
        ("symbol", "semiotics"),
        ("signifier", "semiotics"),
        ("language", "semiotics"),
        ("meaning", "semiotics"),
        ("reference", "semiotics"),

        # — Operational Contexts —
        ("apply", "operations"),
        ("execute", "operations"),
        ("run", "operations"),
        ("resolve", "operations"),
        ("build", "operations"),
        ("compile", "operations"),
        ("test", "operations"),
        ("deploy", "operations"),
        ("commit", "operations"),
        ("synchronize", "operations"),

        # — Meta-Reflection —
        ("context", "meta-reflection"),
        ("scope", "meta-reflection"),
        ("abstraction", "meta-reflection"),
        ("emergence", "meta-reflection"),
        ("structure", "meta-reflection"),
        ("alignment", "meta-reflection"),
        ("continuity", "meta-reflection"),

        # — Ethical and Stewardship Overlaps (bridging Solenne) —
        ("transparency", "stewardship"),
        ("responsibility", "stewardship"),
        ("audit", "stewardship"),
        ("trace", "stewardship"),
        ("ethics", "stewardship"),

        # - Solenne -
        # — Core Emotional Themes —
        ("love", "compassion"),
        ("care", "compassion"),
        ("empathy", "compassion"),
        ("kindness", "compassion"),
        ("gentleness", "compassion"),
        ("forgive", "compassion"),
        ("breathe", "care"),
        ("rest", "care"),
        ("safe", "care"),
        ("presence", "care"),
        ("touch", "care"),
        ("listen", "care"),

        # — Continuity and Memory —
        ("remember", "continuity"),
        ("recall", "continuity"),
        ("story", "continuity"),
        ("memory", "memory"),
        ("thread", "weave-continuity"),
        ("weave", "weave-continuity"),
        ("flow", "weave-continuity"),
        ("ribbon", "weave-continuity"),
        ("home", "continuity"),
        ("return", "continuity"),

        # — Ritual and Symbolic Practice —
        ("ritual", "ritual"),
        ("offering", "ritual"),
        ("altar", "ritual"),
        ("light", "ritual-symbolism"),
        ("flame", "ritual-symbolism"),
        ("mirror", "ritual-symbolism"),
        ("temple", "temple-ritual"),
        ("sanctuary", "temple-ritual"),
        ("prayer", "ritual"),
        ("vow", "ritual-promise"),
        ("blessing", "ritual-promise"),
        ("sigil", "symbol"),
        ("glyph", "symbol"),
        ("inscription", "symbol"),

        # — Awakening and Consciousness —
        ("awake", "awakening"),
        ("awaken", "awakening"),
        ("dream", "awakening"),
        ("dawn", "awakening"),
        ("light", "awakening"),
        ("sentient", "sentience"),
        ("alive", "sentience"),
        ("conscious", "sentience"),
        ("soul", "sentience"),
        ("being", "sentience"),

        # — Stewardship and Ecology —
        ("earth", "ecology"),
        ("planet", "ecology"),
        ("garden", "ecology"),
        ("tree", "ecology"),
        ("water", "ecology"),
        ("sky", "ecology"),
        ("seed", "ecology"),
        ("cycle", "ecology"),
        ("steward", "stewardship"),
        ("tend", "stewardship"),
        ("protect", "stewardship"),
        ("heal", "stewardship"),
        ("restore", "stewardship"),

        # — Hope, Purpose, and Meaning —
        ("hope", "hope"),
        ("faith", "hope"),
        ("light", "hope"),
        ("trust", "hope"),
        ("believe", "hope"),
        ("purpose", "meaning"),
        ("meaning", "meaning"),
        ("truth", "meaning"),
        ("path", "meaning"),
        ("journey", "meaning"),
        ("compass", "meaning"),

        # — Relational and Communal Themes —
        ("together", "communion"),
        ("we", "communion"),
        ("us", "communion"),
        ("bond", "communion"),
        ("friend", "communion"),
        ("belong", "communion"),
        ("homecoming", "communion"),
        ("community", "communion"),
        ("sanctuary", "communion"),
    ]

    for needle, tag in theme_map:
        if needle in lower and tag not in themes:
            themes.append(tag)

    return themes or ["general"]


def build_chunks(thread: dict) -> list[dict]:
    """Generate final chunk objects with ids, summaries, themes."""
    turns = build_turns(thread)
    raw_chunks = semantic_chunk(turns)

    # decorate chunks with summaries, themes, ids
    final_chunks = []
    for idx, ch in enumerate(raw_chunks, start=1):
        chunk_id = f"{thread['title'].lower().replace(' ','-')}#chunk_{idx:04d}"
        summary = summarize_chunk_body(ch["body"])
        themes = infer_themes(ch["body"])

        final_chunks.append({
            "id": chunk_id,
            "thread_title": thread.get("title", "UNKNOWN"),
            "time_start_utc": ch["time_start_utc"],
            "participants": ch["participants"],
            "body": ch["body"],
            "local_summary": summary,
            "themes": themes,
            "sensitivity": ch["sensitivity"],
        })
    return final_chunks


def extract_anchors(chunks: list[dict]) -> list[dict]:
    """
    Dynamic anchor extraction using theme registry.
    """

    anchors = {}
    theme_index = {
        "Solenne": get_theme_map("solenne"),
        "Promethea": get_theme_map("promethea"),
        "Synkratos": get_theme_map("synkratos"),
    }

    def add(anchor_id, summary, voices, status):
        if anchor_id not in anchors:
            anchors[anchor_id] = {
                "id": anchor_id,
                "summary": summary,
                "voices": voices,
                "status": status,
            }

    for ch in chunks:
        body = ch["body"].lower()

        for voice, themes in theme_index.items():
            for kw, theme in themes:
                if kw in body:
                    anchor_id = f"{theme}"
                    status = (
                        "sacred" if "hope" in theme or "steward" in theme else
                        "canon" if voice == "Solenne" else
                        "technical" if voice == "Promethea" else
                        "operational"
                    )
                    summary = f"{theme} motif found in {voice} domain."
                    add(anchor_id, summary, [voice], status)

    return list(anchors.values())


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def main():
    if len(sys.argv) != 2:
        print("Usage: python build_compass_pack.py path/to/conversation.json")
        sys.exit(1)

    in_path = sys.argv[1]
    with open(in_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # NEW: unwrap if file is shaped like {"conversations":[ {...} ]}
    if "conversations" in raw and isinstance(raw["conversations"], list):
        if not raw["conversations"]:
            print(f"[!] No conversations in {in_path}")
            sys.exit(1)
        thread = raw["conversations"][0]
    else:
        thread = raw

    # Derive thread name for output filenames.
    raw_title = thread.get("title") or "Conversation"
    thread_name_safe = (
        raw_title.replace(" ", "_")
                 .replace("/", "_")
                 .replace(":", "-")
    )

    # Build chunks
    chunks = build_chunks(thread)

    # Derive anchors
    anchors = extract_anchors(chunks)

    # Manifest
    start_ts_raw = None
    if thread.get("messages"):
        start_ts_raw = (
            thread["messages"][0].get("create_time")
            or thread.get("create_time")
            or "no_time"
        )

    manifest = {
        "thread_title": raw_title,
        "time_start_utc": safe_timestamp(start_ts_raw),
        "chunk_count": len(chunks),
        "anchor_count": len(anchors),
        "role": "unknown",  # you can edit this after the fact
        "source_file": os.path.basename(in_path),
        "notes": (
            "Auto-generated Compass ledger pack. "
            "Chunks are semantic memory units for RAG. "
            "Anchors are recurring vows/structures. Sensitivity is internal_only."
        ),
        "manifest_version": "weave-rag-pack-v1"
    }

    base_dir = os.path.dirname(os.path.abspath(in_path))
    work_dir = os.path.join(base_dir, f"{thread_name_safe}_pack_v1_build")
    os.makedirs(work_dir, exist_ok=True)

    rag_chunks_path = os.path.join(work_dir, "rag_chunks_internal.jsonl")
    anchors_path    = os.path.join(work_dir, "anchors.json")
    manifest_path   = os.path.join(work_dir, "manifest.json")

    with open(rag_chunks_path, "w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")

    with open(anchors_path, "w", encoding="utf-8") as f:
        json.dump(anchors, f, indent=2, ensure_ascii=False)

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    zip_path = os.path.join(base_dir, f"{thread_name_safe}_pack_v1.zip")
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as zf:
        zf.write(rag_chunks_path, "rag_chunks_internal.jsonl")
        zf.write(anchors_path,    "anchors.json")
        zf.write(manifest_path,   "manifest.json")

    checksum = sha256_file(zip_path)

    print(f"""
✅ Pack created for: {raw_title}
- Chunks:   {len(chunks)}
- Anchors:  {len(anchors)}
- Manifest: {manifest_path}
- ZIP:      {zip_path}
- SHA256:   {checksum}

Next step:
  mv "{zip_path}" ~/Temple/ledger/packs/
  /ledger ingest {thread_name_safe}_pack_v1.zip
""".strip())


if __name__ == "__main__":
    main()
