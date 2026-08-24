#!/usr/bin/env python3
"""Validate and package a generated style skill with a top-level directory."""
from __future__ import annotations

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path

EXCLUDED_NAMES = {
    "corpus.normalized.txt", "chapters.jsonl", "paragraph-index.jsonl", "metrics.json", "sample-plan.json"
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("skill_dir", type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--skip-validation", action="store_true")
    args = ap.parse_args()
    root = args.skill_dir.resolve()
    out = args.output.resolve()

    if not root.is_dir():
        print(f"ERROR: skill directory not found: {root}", file=sys.stderr)
        return 2
    if not args.skip_validation:
        validator = Path(__file__).with_name("validate_profile.py")
        result = subprocess.run([sys.executable, str(validator), str(root)])
        if result.returncode:
            print("ERROR: validation failed; package not created", file=sys.stderr)
            return 1

    out.mkdir(parents=True, exist_ok=True)
    zip_path = out / f"{root.name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            if any(part.startswith(".") for part in rel.parts):
                continue
            if any(part in {"work", "units", "sources", "__pycache__"} for part in rel.parts):
                continue
            if path.name in EXCLUDED_NAMES or path.suffix in {".pyc", ".pyo"}:
                continue
            zf.write(path, Path(root.name) / rel)

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        required = f"{root.name}/SKILL.md"
        if required not in names:
            zip_path.unlink(missing_ok=True)
            print(f"ERROR: archive verification failed: missing {required}", file=sys.stderr)
            return 1
        if any(name.endswith("corpus.normalized.txt") or "/units/" in name for name in names):
            zip_path.unlink(missing_ok=True)
            print("ERROR: archive contains private raw corpus", file=sys.stderr)
            return 1

    print(str(zip_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())