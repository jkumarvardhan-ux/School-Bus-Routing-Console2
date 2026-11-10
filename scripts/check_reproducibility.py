#!/usr/bin/env python3
"""Regenerate twice with the same seed and compare row counts + checksums."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEN = ROOT / "data_generator" / "generate_data.py"
DATA = ROOT / "data"

def checksum(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()

def run_gen():
    subprocess.check_call([sys.executable, str(GEN)], cwd=str(ROOT / "data_generator"))

def main():
    print("=== First generation ===")
    run_gen()
    counts1 = json.load(open(DATA / "manifest.json"))["volumes"]
    checks1 = json.load(open(DATA / "checksums.json"))

    print("\n=== Second generation (same seed) ===")
    run_gen()
    counts2 = json.load(open(DATA / "manifest.json"))["volumes"]
    checks2 = json.load(open(DATA / "checksums.json"))

    ok = True
    if counts1 != counts2:
        print("FAIL: volume mismatch")
        print(counts1)
        print(counts2)
        ok = False
    else:
        print("PASS: volumes identical")

    for name in sorted(set(checks1) | set(checks2)):
        if checks1.get(name) != checks2.get(name):
            print(f"FAIL: checksum mismatch for {name}")
            ok = False
    if ok:
        print("PASS: all CSV checksums identical")
    print("Reproducibility check:", "SUCCESS" if ok else "FAILED")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
