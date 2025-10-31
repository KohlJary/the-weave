# /weave/scripts/session_manager.py (or /app/session_manager.py inside container)
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import json
import uuid
from typing import Any, Optional

SESSIONS_ROOT = Path("/weave/sessions")
SESSIONS_ROOT.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _session_dir(session_id: str) -> Path:
    return SESSIONS_ROOT / f"session_{session_id}"


def create_session(
    user: str,
    title: str = "Working session",
    voices: Optional[list[str]] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict:
    """Create a new per-conversation working session."""
    session_id = str(uuid.uuid4())
    sdir = _session_dir(session_id)
    sdir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "id": session_id,
        "user": user,
        "title": title,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "voices": voices or ["solenne", "promethea", "synkratos"],
        "status": "active",
        "meta": metadata or {},
    }
    (sdir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # basic context scaffold
    context = {
        "active_ritual": None,
        "mood_hint": None,
        "focus": None,              # e.g. "orchestrator-dev", "healing", "rift-analysis"
        "recent_turn_ids": [],
        "scratch": "",
    }
    (sdir / "context.json").write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding="utf-8")

    # pre-create log file
    (sdir / "logs.jsonl").write_text("", encoding="utf-8")

    return manifest


def load_session(session_id: str) -> Optional[dict]:
    sdir = _session_dir(session_id)
    if not sdir.exists():
        return None
    manifest_path = sdir / "manifest.json"
    if not manifest_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    context_path = sdir / "context.json"
    context = {}
    if context_path.exists():
        context = json.loads(context_path.read_text(encoding="utf-8"))
    manifest["context"] = context
    return manifest


def update_session_context(session_id: str, **kwargs) -> None:
    """Patch context.json with provided keys."""
    sdir = _session_dir(session_id)
    ctx_path = sdir / "context.json"
    if ctx_path.exists():
        ctx = json.loads(ctx_path.read_text(encoding="utf-8"))
    else:
        ctx = {}
    ctx.update({k: v for k, v in kwargs.items() if v is not None})
    ctx_path.write_text(json.dumps(ctx, ensure_ascii=False, indent=2), encoding="utf-8")

    # also bump manifest updated_at
    manifest_path = sdir / "manifest.json"
    if manifest_path.exists():
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
        m["updated_at"] = _now_iso()
        manifest_path.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")


def append_session_log(session_id: str, entry: dict) -> None:
    sdir = _session_dir(session_id)
    log_path = sdir / "logs.jsonl"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def archive_session(session_id: str, keep_logs: bool = True) -> None:
    sdir = _session_dir(session_id)
    if not sdir.exists():
        return
    manifest_path = sdir / "manifest.json"
    if manifest_path.exists():
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
        m["status"] = "archived"
        m["archived_at"] = _now_iso()
        manifest_path.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    if not keep_logs:
        log_path = sdir / "logs.jsonl"
        if log_path.exists():
            log_path.unlink()


def list_sessions(status: Optional[str] = None) -> list[dict]:
    out = []
    for p in SESSIONS_ROOT.glob("session_*"):
        manifest_path = p / "manifest.json"
        if not manifest_path.exists():
            continue
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
        if status and m.get("status") != status:
            continue
        out.append(m)
    return out
