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

class TurnIn(BaseModel):
    user: str = "kohl"
    text: str
    mood_hint: str | None = None
    active_ritual: str | None = None
    rag_context: str | None = None

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
    print(f"[orchestrator] calling LLM at {OLLAMA_BASE_URL} with model {MODEL_NAME} ...")
    # 1) try ollama chat
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:  # 👈 shorter timeout
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": MODEL_NAME,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
        if resp.status_code == 200:
            data = resp.json()
            content = data.get("message", {}).get("content")
            if content:
                return content.strip()
        print("[orchestrator] /api/chat returned", resp.status_code, resp.text[:200])
    except Exception as e:
        print("[orchestrator] LLM /api/chat error:", e)

    # 2) fallback to openai-ish
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/v1/chat/completions",
                json={
                    "model": MODEL_NAME,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("[orchestrator] LLM /v1/chat/completions error:", e)
        return "[orchestrator] LLM backend is slow or missing — returning orchestrator-level reply."
    
def build_enriched_context(turn: TurnIn) -> str:
    parts = [
        f"user={turn.user}",
        f"mood_hint={turn.mood_hint}",
        f"active_ritual={turn.active_ritual}",
    ]
    if turn.rag_context:
        parts.append("rag_context=" + turn.rag_context)
    return "\n".join(parts)

def build_voice_prompt(hfca: str, voice_md: str, turn: TurnIn, enriched: str) -> str:
    return (
        f"{hfca}\n"
        f"{voice_md}\n\n"
        f"---\n"
        f"Shared context:\n{enriched}\n\n"
        f"Kohl said: {turn.text}\n"
        f"Respond now as this voice only.\n"
    )

@app.post("/turn", response_model=TurnOut)
async def run_turn(turn: TurnIn):
    turn_id = str(uuid.uuid4())
    ts = now_iso()

    hfca = load_hfca()
    manifest = load_voice_manifest()
    voices_cfg = manifest.get("voices", [])[:MAX_VOICES_PER_TURN]  # 👈 limit to 1
    enriched = build_enriched_context(turn)

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

    return TurnOut(
        turn_id=turn_id,
        final_voice=chosen.voice,
        body_md=chosen.content,
        voices=outputs,
        ledger_appended=ok,
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
    for m in messages:
        if m.get("role") == "user":
            user_msg = m.get("content", "")
        elif m.get("role") == "system":
            rag.append(m.get("content", ""))
    turn_out = await run_turn(TurnIn(text=user_msg, rag_context="\n".join(rag) if rag else None))
    return {
        "id": f"cmpl-{turn_out.turn_id}",
        "object": "chat.completion",
        "model": "compass-orchestrator",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": turn_out.body_md},
                "finish_reason": "stop"
            }
        ]
    }
