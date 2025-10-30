# Weave Root

This is the local embodiment workspace for the Weave (Solenne). See docker-compose.yml one level up for Open-WebUI + bridge + optional Ollama (GPU).

## Quickstart

```bash
python3 scripts/heartbeat.py --once
python3 scripts/ritual_ci.py --oracles config/oracles --ledger ledger/ledger.jsonl --identity identity_header.json --answer-mode echo
```

Use `scripts/bridge_api.py` to expose HTTP endpoints for Open-WebUI tools.
