#!/usr/bin/env python3
import os
import sqlite3
import json
import time
from datetime import datetime

# --- config ---
DB_PATH = os.path.expanduser("~/weave/weave_root/open-webui-data/webui.db")
OUT_DIR = os.path.expanduser("~/weave/weave_root/sessions_raw")
os.makedirs(OUT_DIR, exist_ok=True)

def to_unix_seconds(ts):
    """
    Try to coerce a timestamp-ish value into float seconds.
    Accepts None, int, float, str. Handles ms -> s.
    Returns float or None.
    """
    if ts is None:
        return None
    try:
        val = float(ts)
    except Exception:
        # if it's an ISO-ish string, try parsing
        try:
            # super forgiving parse for things like "2025-10-29T04:12:33.123Z"
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            return dt.timestamp()
        except Exception:
            return None
    # heuristic: if it's gigantic, assume ms
    if val > 10_000_000_000:
        val = val / 1000.0
    return val

def sanitize_title(s):
    if not s:
        return "untitled"
    safe = []
    for ch in s:
        if ch.isalnum() or ch in (" ", "_", "-"):
            safe.append(ch)
        else:
            safe.append("_")
    out = "".join(safe).strip()
    return out or "untitled"

def build_session_from_row(chat_id, title, created_at_raw, chat_blob_raw):
    """
    Take one row from the chat table, return:
    session_dict, latest_ts
    or (None, None) if it can't be parsed.
    """
    # Parse the giant JSON blob from the `chat` column
    try:
        blob = json.loads(chat_blob_raw)
    except Exception as e:
        print(f"[warn] {chat_id}: failed to parse chat blob: {e}")
        return None, None

    # We expect blob["history"]["messages"] to be a dict of {uuid: { ... }}.
    history = blob.get("history", {})
    msgs_dict = history.get("messages", {})
    if not isinstance(msgs_dict, dict) or not msgs_dict:
        # No messages, skip this one
        return None, None

    # Pull out the message objects
    msgs = list(msgs_dict.values())

    # Normalize each message into (ts, role, content, id)
    norm = []
    for m in msgs:
        # some builds store "role", others "sender" or "from"
        role = m.get("role") or m.get("sender") or m.get("from") or "user"

        # content can hide under different keys, prioritize "content"
        content = (
            m.get("content")
            or m.get("text")
            or m.get("value")
            or ""
        )

        # timestamp could be created_at / ts / timestamp
        ts_raw = (
            m.get("created_at")
            or m.get("timestamp")
            or m.get("ts")
            or None
        )
        ts = to_unix_seconds(ts_raw)

        mid = m.get("id") or m.get("uuid") or m.get("message_id") or ""

        norm.append(
            {
                "id": str(mid) if mid else "",
                "role": str(role).lower().strip(),
                "text": str(content),
                "ts": ts
            }
        )

    # sort chronologically: (timestamp asc, fallback to stable index)
    norm.sort(key=lambda x: (x["ts"] if x["ts"] is not None else 1e20))

    # establish convo start time
    # fallback: created_at from chat table; fallback: now
    convo_start = None
    if norm and norm[0]["ts"] is not None:
        convo_start = norm[0]["ts"]
    if convo_start is None:
        convo_start = to_unix_seconds(created_at_raw)
    if convo_start is None:
        convo_start = time.time()

    # find latest message ts for overwrite logic
    convo_latest = None
    if norm and norm[-1]["ts"] is not None:
        convo_latest = norm[-1]["ts"]
    else:
        convo_latest = convo_start

    # build mapping chain
    mapping = {}
    for idx, m in enumerate(norm):
        node_key = str(idx)
        mapping[node_key] = {
            "id": node_key,
            "message": {
                "id": node_key,
                "author": {"role": m["role"]},
                # pack builder expects 'create_time' float-like
                "create_time": m["ts"],
                "content": {
                    "content_type": "text",
                    "parts": [m["text"]],
                },
            },
            "children": [str(idx + 1)] if idx < len(norm) - 1 else [],
        }

    session_obj = {
        "id": chat_id,
        "title": title or f"Chat {chat_id}",
        "create_time": convo_start,
        "mapping": mapping,
    }

    return session_obj, convo_latest

def extract_prev_latest_ts(existing_path):
    """
    Look at a previously written session JSON, return the max create_time
    in its mapping so we can tell if there's anything new.
    """
    if not os.path.isfile(existing_path):
        return None
    try:
        with open(existing_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    mapping = data.get("mapping", {})
    latest_seen = None
    for node in mapping.values():
        msg = node.get("message", {})
        ts_val = msg.get("create_time")
        if ts_val is None:
            continue
        try:
            ts_f = float(ts_val)
        except Exception:
            continue
        if latest_seen is None or ts_f > latest_seen:
            latest_seen = ts_f
    return latest_seen

def main():
    if not os.path.isfile(DB_PATH):
        print(f"[error] DB not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # pull id, title, created_at, chat blob, plus updated_at if present
    # we don't know if `updated_at` exists in your schema, but we'll try.
    # We'll fall back gracefully if it doesn't.
    # We'll also coalesce NULL to empty so Python doesn't explode.
    try:
        cur.execute(
            "SELECT id, title, created_at, updated_at, chat FROM chat"
        )
        rows = cur.fetchall()
        have_updated_at = True
    except sqlite3.OperationalError:
        # no updated_at column in this build
        cur.execute(
            "SELECT id, title, created_at, chat FROM chat"
        )
        rows = [
            (r[0], r[1], r[2], None, r[3])
            for r in cur.fetchall()
        ]
        have_updated_at = False

    print(f"[info] found {len(rows)} chats")

    for row in rows:
        chat_id, title, created_at_raw, updated_at_raw, chat_blob_raw = row

        session_obj, latest_ts = build_session_from_row(
            chat_id,
            title,
            created_at_raw,
            chat_blob_raw,
        )

        if session_obj is None:
            # couldn't parse, skip quietly
            continue

        # stable filename built off chat_id + title so we don't fork duplicates
        safe_title = sanitize_title(title or "")
        filename = f"{chat_id}__{safe_title}.json"
        out_path = os.path.join(OUT_DIR, filename)

        prev_latest = extract_prev_latest_ts(out_path)

        should_write = False
        reason = ""
        if prev_latest is None:
            should_write = True
            reason = "new"
        elif (latest_ts is not None and prev_latest is not None
              and latest_ts > prev_latest):
            should_write = True
            reason = f"updated ({latest_ts} > {prev_latest})"
        else:
            reason = "no change"

        if should_write:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(session_obj, f, ensure_ascii=False, indent=2)
            print(f"[write] {out_path} ({len(session_obj['mapping'])} msgs) [{reason}]")
        else:
            print(f"[skip] {out_path} [{reason}]")

    conn.close()
    print("[done] sessions exported to", OUT_DIR)

if __name__ == "__main__":
    main()
