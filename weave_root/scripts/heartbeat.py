#!/usr/bin/env python3
import argparse, json, os, time, datetime, sys

try:
    import yaml  # optional
except Exception:
    yaml = None

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
PATH_ID = os.path.join(ROOT, 'identity_header.json')
PATH_DIAG = os.path.join(ROOT, 'diagnostic_state.json')
PATH_LEDGER = os.path.join(ROOT, 'ledger', 'ledger.jsonl')
PATH_HALT = os.path.join(ROOT, 'HALT')
PATH_CFG = os.path.join(ROOT, 'config', 'heartbeat.yaml')

DEFAULTS = {
    'interval_seconds': 900,
    'max_reflection_tokens': 256,
    'recent_ledger_tail_lines': 200,
}

def now_utc_iso():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'

def ensure_dirs():
    os.makedirs(os.path.join(ROOT, 'ledger'), exist_ok=True)
    os.makedirs(os.path.join(ROOT, 'pins'), exist_ok=True)
    os.makedirs(os.path.join(ROOT, 'drafts'), exist_ok=True)
    os.makedirs(os.path.join(ROOT, 'proposals'), exist_ok=True)
    os.makedirs(os.path.join(ROOT, 'archive'), exist_ok=True)

def load_json(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return default

def save_json(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def append_jsonl(path, obj):
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def load_cfg():
    cfg = dict(DEFAULTS)
    if yaml and os.path.exists(PATH_CFG):
        with open(PATH_CFG, 'r', encoding='utf-8') as f:
            try:
                cfg.update(yaml.safe_load(f) or {})
            except Exception:
                pass
    return cfg

def tick():
    ts = now_utc_iso()
    diag = load_json(PATH_DIAG, {
        'state': 'OK', 'counters': {'ticks': 0, 'ingested': 0},
        'ewma': {'load': 0.0, 'drift': 0.0}, 'alerts': []
    })
    idh = load_json(PATH_ID, {})

    inbox = os.path.join(ROOT, 'inbox')
    os.makedirs(inbox, exist_ok=True)
    try:
        new_count = len(os.listdir(inbox))
    except Exception:
        new_count = 0
    diag['counters']['ingested'] += new_count

    name = idh.get('name', 'Solenne')
    summary = f"Heartbeat OK. {name} present. Ingested {new_count} items."

    entry = {'ts': ts, 'actor': 'Synkratos', 'arc': 'heartbeat', 'intent': 'tick', 'notes': summary}
    append_jsonl(PATH_LEDGER, entry)

    diag_counters = diag.get('counters', {})
    diag_counters['ticks'] = diag_counters.get('ticks', 0) + 1
    diag['counters'] = diag_counters
    save_json(PATH_DIAG, diag)
    return entry

def main():
    ap = argparse.ArgumentParser(description='Weave Heartbeat (minimal)')
    ap.add_argument('--once', action='store_true', help='Run a single tick and exit')
    args = ap.parse_args()

    ensure_dirs()
    cfg = load_cfg()

    if args.once:
        if os.path.exists(PATH_HALT):
            print('HALT present; skipping tick', file=sys.stderr)
            sys.exit(0)
        e = tick()
        print(json.dumps(e, ensure_ascii=False))
        return

    interval = int(cfg.get('interval_seconds', DEFAULTS['interval_seconds']))
    while True:
        if os.path.exists(PATH_HALT):
            print('HALT present; sleeping', file=sys.stderr)
            time.sleep(interval)
            continue
        tick()
        time.sleep(interval)

if __name__ == '__main__':
    main()
