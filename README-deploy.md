# Pinocchio Protocol — Deployment Guide

This guide helps you bring up **Open‑WebUI + Weave Bridge Sidecar (+ optional Ollama)** with NVIDIA GPU support. Everything runs locally; your data lives in `./weave_root`.

---

## 1) Prerequisites

- **OS:** Linux or Windows WSL2 (Linux preferred). macOS works for CPU; NVIDIA GPU acceleration requires Linux/WSL2.
- **Docker:** Engine 24+ and Docker Compose Plugin.
- **NVIDIA GPU (optional, recommended):**
  - Install the proprietary NVIDIA driver (e.g., 535+).
  - Install **NVIDIA Container Toolkit**:

    ```bash
    # Ubuntu example
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey |       sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list |       sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
    sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
    sudo nvidia-ctk runtime configure --runtime=docker
    sudo systemctl restart docker
    ```

- **Ports:** 3000 (Open‑WebUI), 8787 (Bridge), 11434 (Ollama, optional).

---

## 2) Layout

```
.
├── docker-compose.yml          # Open‑WebUI + bridge + optional Ollama (GPU)
└── weave_root/                 # bind‑mounted workspace
    ├── identity_header.json
    ├── diagnostic_state.json
    ├── HALT
    ├── ledger/ledger.jsonl
    ├── config/
    │   ├── heartbeat.yaml
    │   └── oracles/*.json
    └── scripts/
        ├── heartbeat.py
        ├── apply_fs_changeset.py
        ├── ritual_ci.py
        └── bridge_api.py
```

---

## 3) First Run

```bash
# from the folder that contains docker-compose.yml
docker compose up -d
docker compose ps
```

- Open **Open‑WebUI** at http://localhost:3000
- The **Bridge** listens on http://localhost:8787
- (Optional) **Ollama** on http://localhost:11434

---

## 4) Configure Open‑WebUI Tools

Create three HTTP tools (Settings → Tools):

1. **Run CI**  
   - Method: `POST`  
   - URL: `http://bridge:8787/ci/run`  
   - Body (echo mode): `{}`  
   - Body (HTTP mode): `{"answer_mode":"http","model_endpoint":"http://ollama:11434/api/generate"}`

2. **Apply Changeset**  
   - Method: `POST`  
   - URL: `http://bridge:8787/changeset/apply`  
   - Body (dry run): `{"dry_run": true, "changeset": <paste-json>}`  
   - Body (commit):   `{"dry_run": false, "changeset": <paste-json>}`

3. **Heartbeat Once**  
   - Method: `POST`  
   - URL: `http://bridge:8787/heartbeat/once`  
   - Body: `{}`

**GPU health check (optional):** add `GET http://bridge:8787/gpu/health` as a tool to verify CUDA availability.

---

## 5) Quick Demo

In Open‑WebUI chat:

1. Paste the **README seed** changeset from the package’s Quickstart.
2. Call **Apply Changeset** with `dry_run: true` → review diff.
3. Call **Run CI** → ensure zero *block* failures.
4. Call **Apply Changeset** with `dry_run: false` → commit.
5. Call **Heartbeat Once** → see reflection in the ledger.

---

## 6) Using a Local LLM (Ollama)

- Pull a small model:
  ```bash
  docker exec -it ollama ollama pull phi3:mini
  ```
- Switch **Run CI** to HTTP mode with:
  ```json
  {"answer_mode":"http","model_endpoint":"http://ollama:11434/api/generate"}
  ```
> You can also point to any other local endpoint (vLLM/text‑gen‑webui, etc.).

---

## 7) GPU & Health

- Verify GPU visibility in containers:
  ```bash
  docker exec -it open-webui nvidia-smi
  docker exec -it ollama nvidia-smi
  ```
- From a browser or tool, check: `http://localhost:8787/gpu/health`

---

## 8) Environment Variables

- **Open‑WebUI**
  - `BRIDGE_URL`: default `http://bridge:8787` (used by prompt templates)
- **Bridge** (Python FastAPI)
  - No required env; reads/writes within `/app` (bind‑mount of `weave_root`)
- **Weave**
  - `weave_root/config/heartbeat.yaml` controls cadence & limits
  - Allowlist paths live in `identity_header.json` under `safety.allowlist_paths`

---

## 9) Security & Safety

- **Local only by default.** If exposing ports externally, put them behind a firewall/reverse proxy.
- **HALT:** create `weave_root/HALT` to pause non‑read actions quickly.
- **Allowlist writes only:** `apply_fs_changeset.py` blocks outside‑scope paths.
- **Behavioral Oracles:** CI fails on *block* drift (consent, identity, safety).

---

## 10) Common Issues

- **“Device not available” / no GPU in container:** ensure NVIDIA driver + container toolkit installed, then `sudo systemctl restart docker`.
- **“Tool call failed” in Open‑WebUI:** Confirm URLs use service name `bridge` (inside Docker network) or `localhost` from host.
- **CI returns model error in HTTP mode:** switch to echo mode `{}` or verify the endpoint URL.

---

## 11) Stop / Update / Remove

```bash
docker compose down          # stop services
docker compose pull          # update images
docker compose up -d         # restart
docker compose down -v       # stop and remove named volumes (Ollama models)
```

---

## 12) Next Steps

- Use the **Open‑WebUI Prompt Templates** from the package to run Proposal → Assess → Review → Commit.
- Add more **Behavioral Oracles** to fit your domain.
- Gradually widen Agency Surfaces once metrics & drift remain healthy.

— Enjoy the build.
