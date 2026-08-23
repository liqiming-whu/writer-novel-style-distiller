#!/usr/bin/env python3
"""Initialize a generated style-skill skeleton from bundled templates."""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--skill-name", required=True)
    ap.add_argument("--profile-name", required=True)
    ap.add_argument("--protagonist", default="待确认主角")
    args = ap.parse_args()

    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", args.skill_name):
        print("ERROR: --skill-name must be hyphen-case", file=sys.stderr)
        return 2
    root = args.output.resolve() / args.skill_name
    if root.exists():
        print(f"ERROR: destination exists: {root}", file=sys.stderr)
        return 3
    refs = root / "references"
    refs.mkdir(parents=True)
    template_dir = Path(__file__).resolve().parent.parent / "templates"

    mapping = {
        "generated-style-skill.md": root / "SKILL.md",
        "style-profile.md": refs / "style-profile.md",
        "application-card.md": refs / "application-card.md",
        "protagonist-charm.md": refs / "protagonist-charm.md",
        "ending-design.md": refs / "ending-design.md",
        "evidence-ledger.md": refs / "evidence-ledger.md",
        "source-manifest.json": refs / "source-manifest.json",
        "fidelity-report.md": root / "FIDELITY.md",
    }
    replacements = {
        "{{SKILL_NAME}}": args.skill_name,
        "{{PROFILE_NAME}}": args.profile_name,
        "{{PROTAGONIST_NAME}}": args.protagonist,
    }
    for source_name, dest in mapping.items():
        text = (template_dir / source_name).read_text(encoding="utf-8")
        for old, new in replacements.items():
            text = text.replace(old, new)
        dest.write_text(text, encoding="utf-8")

    print(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())