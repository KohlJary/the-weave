#!/usr/bin/env python3
import argparse, json, pathlib

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--from-ledger', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    # Minimal stub: create an empty list or echo simple pins
    pins = []
    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(pins, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
