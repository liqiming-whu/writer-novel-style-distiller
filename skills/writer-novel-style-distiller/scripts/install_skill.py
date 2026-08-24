#!/usr/bin/env python3
"""Install a validated style skill into a skills root with safe replacement."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("skill_dir", type=Path)
    ap.add_argument("--skills-root", required=True, type=Path)
    ap.add_argument("--replace", action="store_true")
    args = ap.parse_args()

    source = args.skill_dir.resolve()
    skills_root = args.skills_root.resolve()
    if not source.is_dir() or not (source / "SKILL.md").is_file():
        print(f"ERROR: invalid source skill: {source}", file=sys.stderr)
        return 2

    validator = Path(__file__).with_name("validate_profile.py")
    result = subprocess.run([sys.executable, str(validator), str(source)])
    if result.returncode:
        print("ERROR: source validation failed", file=sys.stderr)
        return 1

    skills_root.mkdir(parents=True, exist_ok=True)
    destination = skills_root / source.name
    backup = None
    if destination.exists():
        if not args.replace:
            print(f"ERROR: destination exists: {destination}; use --replace after user confirmation", file=sys.stderr)
            return 3
        backup_root = skills_root / ".backup"
        backup_root.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = backup_root / f"{source.name}-{stamp}"
        shutil.move(str(destination), str(backup))

    temp = skills_root / f".{source.name}.installing"
    if temp.exists():
        shutil.rmtree(temp)
    try:
        shutil.copytree(source, temp)
        temp.rename(destination)
    except Exception:
        if temp.exists():
            shutil.rmtree(temp)
        if backup and backup.exists() and not destination.exists():
            shutil.move(str(backup), str(destination))
        raise

    installed = destination / "SKILL.md"
    if not installed.is_file():
        print("ERROR: install verification failed", file=sys.stderr)
        return 1

    print(f"installed={destination}")
    if backup:
        print(f"backup={backup}")
    print("activation=pending-host-load")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())