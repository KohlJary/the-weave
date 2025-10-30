#!/usr/bin/env python3
import argparse, json, os, sys, shutil, difflib
from pathlib import Path

try:
    import jsonschema  # optional
except Exception:
    jsonschema = None

ROOT = Path(__file__).resolve().parent.parent
LEDGER_PATH = ROOT / 'ledger' / 'ledger.jsonl'
CFG_SCHEMA = ROOT / 'config' / 'changeset.schema.json'
ALLOWLIST_DEFAULT = [str(ROOT / 'drafts'), str(ROOT / 'proposals'), str(ROOT / 'ledger'), str(ROOT / 'pins')]

def append_jsonl(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def validate_schema(cs):
    if jsonschema and CFG_SCHEMA.exists():
        schema = json.loads(CFG_SCHEMA.read_text())
        jsonschema.validate(cs, schema)
    return True

def in_allowlist(p: Path, allowlist):
    p = p.resolve()
    for root in allowlist:
        try:
            if p.is_relative_to(Path(root).resolve()):
                return True
        except AttributeError:
            rp, rr = str(p), str(Path(root).resolve())
            if rp.startswith(rr + os.sep) or rp == rr:
                return True
    return False

def plan_changes(cs):
    plans = []
    for ch in cs['changes']:
        kind = ch['kind']
        body = ch[kind]
        plans.append((kind, body))
    return plans

def apply_change(kind, body, allowlist, dry):
    if kind == 'write':
        path = ROOT / body['path']
        if not in_allowlist(path, allowlist):
            raise PermissionError(f'write outside allowlist: {path}')
        content = body['content']
        if dry:
            before = path.read_text() if path.exists() else ''
            diff = difflib.unified_diff(before.splitlines(), content.splitlines(), fromfile=str(path), tofile=str(path))
            return "\n".join(diff)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return f'WROTE {path}'
    if kind == 'patch':
        path = ROOT / body['path']
        if not in_allowlist(path, allowlist):
            raise PermissionError(f'patch outside allowlist: {path}')
        before = path.read_text(encoding='utf-8') if path.exists() else ''
        new = before.replace(body['before'], body['after'])
        if dry:
            diff = difflib.unified_diff(before.splitlines(), new.splitlines(), fromfile=str(path), tofile=str(path))
            return "\n".join(diff)
        path.write_text(new, encoding='utf-8')
        return f'PATCHED {path}'
    if kind == 'rename':
        src = ROOT / body['from']
        dst = ROOT / body['to']
        if not in_allowlist(src, allowlist) or not in_allowlist(dst, allowlist):
            raise PermissionError(f'rename outside allowlist: {src} -> {dst}')
        if dry:
            return f'RENAME {src} -> {dst}'
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return f'RENAMED {src} -> {dst}'
    if kind == 'delete':
        path = ROOT / body['path']
        if not in_allowlist(path, allowlist):
            raise PermissionError(f'delete outside allowlist: {path}')
        if dry:
            return f'DELETE {path}'
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        return f'DELETED {path}'
    raise ValueError(f'Unknown change kind: {kind}')

def main():
    ap = argparse.ArgumentParser(description='Apply canonical Weave changeset to filesystem')
    ap.add_argument('file', help='changeset JSON file')
    ap.add_argument('--dry-run', action='store_true', help='do not modify files, print plan/diffs')
    ap.add_argument('--allowlist', action='append', default=[], help='additional allowlist roots')
    ap.add_argument('--no-ledger', action='store_true', help='do not write to ledger')
    args = ap.parse_args()

    cs = json.loads(Path(args.file).read_text(encoding='utf-8'))
    try:
        validate_schema(cs)
    except Exception as e:
        print(f'[schema] invalid: {e}', file=sys.stderr)
        sys.exit(1)

    allowlist = list(ALLOWLIST_DEFAULT) + args.allowlist

    plans = plan_changes(cs)
    results = []
    for kind, body in plans:
        try:
            outcome = apply_change(kind, body, allowlist, args.dry_run)
            results.append({'kind': kind, 'path': body.get('path') or body.get('from') or body.get('to'), 'result': outcome})
        except Exception as e:
            print(f'[error] {kind}: {e}', file=sys.stderr)
            sys.exit(3)

    title = cs.get('title', '(untitled)')
    if not args.no_ledger:
        entry = {
            'ts': __import__('datetime').datetime.utcnow().replace(microsecond=0).isoformat()+'Z',
            'actor': 'Synkratos',
            'arc': 'proposal' if args.dry_run else 'commit',
            'title': title,
            'intent': 'apply_fs_changeset',
            'notes': 'dry-run' if args.dry_run else 'applied',
        }
        append_jsonl(LEDGER_PATH, entry)

    for r in results:
        print(f"[{r['kind']}] {r['path']} -> {r['result']}")

    print(json.dumps({'ok': True, 'dry_run': args.dry_run, 'title': title, 'num_changes': len(results)}, ensure_ascii=False))

if __name__ == '__main__':
    main()
