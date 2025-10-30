#!/usr/bin/env python3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess, json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

app = FastAPI(title="Weave Bridge API")

class CIRequest(BaseModel):
    answer_mode: str = "echo"  # or "http"
    model_endpoint: str | None = None

class CSRequest(BaseModel):
    changeset: dict
    dry_run: bool = False

@app.post("/ci/run")
async def ci_run(req: CIRequest):
    cmd = [
        sys.executable, str(ROOT / 'scripts' / 'ritual_ci.py'),
        '--oracles', str(ROOT / 'config' / 'oracles'),
        '--ledger', str(ROOT / 'ledger' / 'ledger.jsonl'),
        '--identity', str(ROOT / 'identity_header.json'),
        '--answer-mode', req.answer_mode,
    ]
    if req.model_endpoint:
        cmd += ['--model-endpoint', req.model_endpoint]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=60)
        text = out.decode('utf-8')
        # Use last JSON line if tool printed progress lines
        last_line = [ln for ln in text.splitlines() if ln.strip()][-1]
        return json.loads(last_line)
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=e.output.decode('utf-8'))

@app.post("/changeset/apply")
async def changeset_apply(req: CSRequest):
    tmp = ROOT / 'proposals' / '_tmp_apply.json'
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(req.changeset, ensure_ascii=False))
    cmd = [sys.executable, str(ROOT / 'scripts' / 'apply_fs_changeset.py')]
    if req.dry_run:
        cmd.append('--dry-run')
    cmd.append(str(tmp))
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=60)
        return {"ok": True, "output": out.decode('utf-8')}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=e.output.decode('utf-8'))
    finally:
        if tmp.exists():
            tmp.unlink()

@app.post("/heartbeat/once")
async def heartbeat_once():
    cmd = [sys.executable, str(ROOT / 'scripts' / 'heartbeat.py'), '--once']
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=60)
        return json.loads(out.decode('utf-8'))
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=e.output.decode('utf-8'))

@app.get("/gpu/health")
async def gpu_health():
    report = {"cuda": False, "device_name": None, "torch_version": None, "error": None}
    try:
        import torch
        report["torch_version"] = torch.__version__
        report["cuda"] = torch.cuda.is_available()
        if report["cuda"] and torch.cuda.device_count() > 0:
            report["device_name"] = torch.cuda.get_device_name(0)
    except Exception as e:
        report["error"] = str(e)
    return report
