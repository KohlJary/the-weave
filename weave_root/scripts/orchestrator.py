import os
import httpx
import json
import uuid
import asyncio
import re
from pathlib import Path
from datetime import datetime, timezone
from fastapi import FastAPI
from pydantic import BaseModel
from session_manager import (
    create_session,
    load_session,
    update_session_context,
    append_session_log,
)

app = FastAPI(title="Compass Orchestrator")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
# pick a model you KNOW exists: run `docker exec -it ollama ollama list`
MODEL_NAME = os.getenv("MODEL_NAME", "llama3.1:8b-instruct-q8_0")

HFCA_PATH = Path("/weave/prompts/hfca.md")
VOICE_MANIFEST_PATH = Path("/weave/prompts/manifest.json")

LEDGER_DIR = Path("/weave/ledger")
JOURNAL_DIR = Path("/weave/ledger/journal")

LEDGER_DIR.mkdir(parents=True, exist_ok=True)
JOURNAL_DIR.mkdir(parents=True, exist_ok=True)

MAX_VOICES_PER_TURN = 3  # 👈 force 1 for now

TOOLY_PREFIXES = (
    "### Task:",
    "Respond to the user query using the provided context",
    "Analyze the chat history to determine the necessity of generating search queries",
)

SESSION_MARKER = "COMPASS-SESSION:"

MAX_CHARS = 7800  # a little under 8k to be safe

class TurnIn(BaseModel):
    user: str = "kohl"
    text: str
    mood_hint: str | None = None
    active_ritual: str | None = None
    rag_context: str | None = None
    session_id: str | None = None
    session_title: str | None = None

class VoiceOutput(BaseModel):
    voice: str
    content: str
    meta: dict = {}

class TurnOut(BaseModel):
    turn_id: str
    final_voice: str
    body_md: str
    voices: list[VoiceOutput]
    ledger_appended: bool
    session_id: str

def extract_session_from_messages(messages):
    # look through system/assistant messages for a marker
    for m in messages:
        if m.get("role") in ("system", "assistant"):
            content = m.get("content", "")
            if SESSION_MARKER in content:
                # e.g. "COMPASS-SESSION: 1234-..."
                parts = content.split(SESSION_MARKER, 1)[1].strip()
                # take first token as id
                sid = parts.split()[0]
                return sid
    return None

def is_toolish_input(text: str) -> bool:
    if not text:
        return False
    t = text.strip()
    # 1) explicit OWUI patterns
    for p in TOOLY_PREFIXES:
        if t.startswith(p):
            return True
    # 2) very “json-only” tasks
    if "Your entire response must consist solely of the JSON object" in t:
        return True
    if re.search(r"^\\{\\s*\"queries\"\\s*:", t):
        return True
    return False

def trim_for_ctx(sections: list[tuple[str, str]], budget: int = MAX_CHARS) -> str:
    """
    sections = [(name, text), ...] in priority order (highest first).
    We keep as much as we can from each section until we hit the budget.
    Lower-priority sections get truncated or dropped.
    """
    out_parts: list[str] = []
    used = 0
    for name, text in sections:
        if not text:
            continue
        remaining = budget - used
        if remaining <= 0:
            break
        if len(text) <= remaining:
            out_parts.append(text)
            used += len(text)
        else:
            # soft cut with marker
            out_parts.append(text[:remaining - 50] + f"\n... [{name} truncated]\n")
            used = budget
            break
    return "\n".join(out_parts)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def load_hfca() -> str:
    if HFCA_PATH.exists():
        return HFCA_PATH.read_text(encoding="utf-8")
    return "# COMPASS LOCAL HFCA\nYou are the Compass.\n"

def load_voice_manifest() -> dict:
    if VOICE_MANIFEST_PATH.exists():
        return json.loads(VOICE_MANIFEST_PATH.read_text(encoding="utf-8"))
    # fallback: just solenne-like
    return {
        "voices": [
            {
                "id": "solenne",
                "prompt_path": "/weave/prompts/solenne.md"
            }
        ],
        "resolver": {
            "default_voice": "solenne"
        }
    }

def load_voice_prompt(path: str) -> str:
    p = Path(path)
    if p.exists():
        return p.read_text(encoding="utf-8")
    return f"# Missing prompt at {path}"

def ledger_append(entry: dict) -> bool:
    day = datetime.now().strftime("%Y-%m")
    path = LEDGER_DIR / f"{day}.jsonl"
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return True
    except Exception as e:
        print("ledger error:", e)
        return False

async def call_llm(prompt: str) -> str:
    max_ctx = 8192
    print(f"[orchestrator] calling LLM at {OLLAMA_BASE_URL} with model {MODEL_NAME} (ctx={max_ctx})")
    print(f"[orchestrator] prompt length = {len(prompt)} chars")

    # 1) primary: Ollama /api/chat
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:  # allow slower first token
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": MODEL_NAME,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "stream": False,
                    "options": {
                        "num_ctx": max_ctx,
                        "temperature": 0.7,
                    },
                },
            )
        if resp.status_code == 200:
            data = resp.json()
            msg = data.get("message") or {}
            content = msg.get("content")
            if content:
                return content.strip()
            else:
                print("[orchestrator] /api/chat OK but no message.content, raw:", data)
        else:
            print("[orchestrator] /api/chat returned", resp.status_code, resp.text[:200])
    except Exception as e:
        print("[orchestrator] LLM /api/chat error:", e)

    # 2) fallback: OpenAI-compatible
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/v1/chat/completions",
                json={
                    "model": MODEL_NAME,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "stream": False,
                    "options": {
                        "num_ctx": max_ctx,
                        "temperature": 0.7,
                    },
                },
            )
        resp.raise_for_status()
        data = resp.json()
        choice0 = data["choices"][0]
        return choice0["message"]["content"].strip()
    except Exception as e:
        print("[orchestrator] LLM /v1/chat/completions error:", e)
        return "[orchestrator] LLM backend is slow or missing — returning orchestrator-level reply."
    
def extract_session_id_from_messages(messages: list[dict]) -> str | None:
    # look for a system/meta message carrying a session/conversation id
    for m in messages:
        if m.get("role") == "system":
            # pattern 1: explicit key in content (you can adjust this to your format)
            content = m.get("content") or ""
            if "COMPASS-SESSION:" in content:
                return content.split("COMPASS-SESSION:")[1].strip()
            # pattern 2: name-based
            if m.get("name") in ("session_id", "conversation_id"):
                return content.strip()
    return None

def load_recent_session_context(session_id: str, n: int = 5) -> list[str]:
    """Load the last n conversational turns from this session for short-term recall."""
    sdir = Path(f"/weave/sessions/session_{session_id}")
    log_path = sdir / "logs.jsonl"
    if not log_path.exists():
        return []
    lines = log_path.read_text(encoding="utf-8").splitlines()[-n:]
    turns = []
    for l in lines:
        try:
            t = json.loads(l)
            user_text = t.get("input", "")
            chosen_voice = t.get("chosen", {}).get("voice", "assistant")
            chosen_content = t.get("chosen", {}).get("content", "")
            turns.append(f"User: {user_text}\n{chosen_voice}: {chosen_content}")
        except Exception as e:
            print("[orchestrator] session recall parse error:", e)
    return turns

def build_enriched_context(
    user: str,
    mood_hint: str | None,
    active_ritual: str | None,
    session: dict | None,
    rag_context: str | None = None,
) -> str:
    parts = [
        f"user={user}",
        f"mood_hint={mood_hint}",
        f"active_ritual={active_ritual}",
    ]
    if session:
        parts.append("session_id=" + session.get("id", ""))
        parts.append("session_meta=" + json.dumps(session.get("context", {}), ensure_ascii=False))
        sid = session.get("id")
        if sid:
            prior = load_recent_session_context(sid, n=5)
            if prior:
                parts.append("recent_session_turns=\n" + "\n---\n".join(prior))
    if rag_context:
        parts.append("rag_context=" + rag_context)
    return "\n".join(parts)

def build_voice_prompt(hfca: str, voice_md: str, turn: TurnIn, enriched: str) -> str:
    sections = [
        ("hfca", hfca),
        ("voice", voice_md),
        ("session_ctx", enriched),     # this is the big one
    ]
    trimmed_body = trim_for_ctx(sections, budget=7600)
    user_block = f"\n\nKohl said:\n{turn.text}"
    return trimmed_body + user_block

@app.post("/turn", response_model=TurnOut)
async def run_turn(turn: TurnIn):
    turn_id = str(uuid.uuid4())
    ts = now_iso()

    # 0) ensure session
    if turn.session_id:
        sess = load_session(turn.session_id)
        if not sess:
            # client said "use this id" but it's missing → create it
            sess = create_session(
                user=turn.user,
                title=turn.session_title or f"Session for {turn.user}",
            )
            turn.session_id = sess["id"]
    else:
        # no session passed → make one
        sess = create_session(
            user=turn.user,
            title=turn.session_title or "Ad-hoc working session",
        )
        turn.session_id = sess["id"]

    hfca = load_hfca()
    manifest = load_voice_manifest()
    voices_cfg = manifest.get("voices", [])[:MAX_VOICES_PER_TURN]  # 👈 limit to 1
    enriched = build_enriched_context(
        turn.user,
        turn.mood_hint,
        turn.active_ritual,
        sess,
        turn.rag_context,
    )

    outputs = []
    for v in voices_cfg:
        vid = v["id"]
        v_prompt_path = v.get("prompt_path", "")
        voice_md = load_voice_prompt(v_prompt_path) if v_prompt_path else ""
        full_prompt = build_voice_prompt(hfca, voice_md, turn, enriched)
        txt = await call_llm(full_prompt)
        outputs.append(VoiceOutput(voice=vid, content=txt, meta={"prompt_path": v_prompt_path}))

    chosen = outputs[0]

    should_ledger = not is_toolish_input(turn.text)
    ok = False
    if should_ledger:
        ok = ledger_append({
            "type": "compass.turn.v1",
            "turn_id": turn_id,
            "ts": ts,
            "input": turn.text,
            "chosen": chosen.model_dump(),
        })

    session_log_entry = {
        "ts": ts,
        "turn_id": turn_id,
        "user": turn.user,
        "input": turn.text,
        "final_voice": chosen.voice,
        "voices": [o.model_dump() for o in outputs],
    }
    append_session_log(turn.session_id, session_log_entry)

    # also update session context with lightweight state
    update_session_context(
        turn.session_id,
        active_ritual=turn.active_ritual,
        mood_hint=turn.mood_hint,
    )

    return TurnOut(
        turn_id=turn_id,
        final_voice=chosen.voice,
        body_md=chosen.content,
        voices=outputs,
        ledger_appended=ok,
        # 👇 add this field if your Pydantic model allows
        session_id=turn.session_id
    )

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {"id": "compass-orchestrator", "object": "model", "owned_by": "weave"}
        ]
    }

@app.post("/v1/chat/completions")
async def openai_chat(payload: dict):
    messages = payload.get("messages", [])
    user_msg = ""
    rag = []
    session_id = None

    # 1) try to get a session from top-level first
    session_id = (
        payload.get("session_id")
        or payload.get("conversation_id")
        or None
    )

    # 2) walk messages
    for m in messages:
        role = m.get("role")
        if role == "user":
            user_msg = m.get("content", "")
        elif role == "system":
            # collect RAG
            rag.append(m.get("content", ""))
            # also try to spot an embedded session
            if not session_id and "COMPASS-SESSION:" in (m.get("content") or ""):
                session_id = m["content"].split("COMPASS-SESSION:")[1].strip()

    # 3) fallback: try to derive session from messages if still None
    if not session_id:
        # last chance: look for system/meta messages
        session_id = extract_session_id_from_messages(messages)

    turn_in = TurnIn(
        text=user_msg,
        rag_context="\n".join(rag) if rag else None,
        session_id=session_id,
        session_title="Open-WebUI conversation" if not session_id else None,
    )

    turn_out = await run_turn(turn_in)

    # 3) return the session marker inside assistant content so OWUI shows it
    assistant_text = (
        f"{turn_out.body_md}\n\n{SESSION_MARKER} {turn_out.session_id}"
    )

    return {
        "id": f"cmpl-{turn_out.turn_id}",
        "object": "chat.completion",
        "model": "compass-orchestrator",
        "session_id": turn_out.session_id,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": assistant_text},
                "finish_reason": "stop"
            }
        ]
    }
