#!/usr/bin/env python3
"""Validate the canonical skills/<name> layout and single-source boundary."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    skill = root / "skills" / "writer-novel-style-distiller"
    errors: list[str] = []

    required_files = ["SKILL.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "VERSION"]
    required_dirs = ["profiles", "references", "reports", "scripts", "templates"]
    runtime_scripts = [
        "ingest_novel.py", "init_profile.py", "install_skill.py", "measure_style.py",
        "package_skill.py", "self_check.py", "validate_builtin_profiles.py", "validate_profile.py",
    ]

    for rel in required_files:
        if not (skill / rel).is_file():
            errors.append(f"missing canonical skill file: {rel}")
    for rel in required_dirs:
        if not (skill / rel).is_dir():
            errors.append(f"missing canonical skill directory: {rel}")
    for rel in runtime_scripts:
        if not (skill / "scripts" / rel).is_file():
            errors.append(f"missing runtime script: scripts/{rel}")

    skill_md = skill / "SKILL.md"
    if skill_md.is_file():
        text = skill_md.read_text(encoding="utf-8")
        if not text.startswith("---\n") or not re.search(
            r"(?m)^name:\s*writer-novel-style-distiller\s*$", text
        ):
            errors.append("canonical SKILL.md has invalid frontmatter/name")

    forbidden_names = {
        "LUXUN_AUDIT_BENCHMARK.md",
        "validate_audit_benchmark.py",
        "validate_standard_skill_layout.py",
        "鲁迅精选集（全四册） 作者：鲁迅精选集.txt",
    }
    skill_files = [p for p in skill.rglob("*") if p.is_file()] if skill.is_dir() else []
    for path in skill.rglob("*") if skill.is_dir() else []:
        if path.name in forbidden_names:
            errors.append(f"repository-only asset leaked into skill: {path.relative_to(skill)}")
        if path.is_file() and (path.suffix.lower() == ".txt" or path.suffix.lower() in {".pyc", ".pyo"}):
            errors.append(f"private/runtime-noise file in canonical skill: {path.relative_to(skill)}")
        if path.is_dir() and path.name in {"benmark", "dist", "work", "sources", "__pycache__"}:
            errors.append(f"repository/private directory in canonical skill: {path.relative_to(skill)}")

    for path in skill_files:
        rel = path.relative_to(skill)
        duplicate = root / rel
        if duplicate.is_file():
            errors.append(f"duplicate compatibility copy outside canonical skill: {rel}")

    owned: dict[tuple[int, str], list[Path]] = {}
    for path in skill_files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        owned.setdefault((path.stat().st_size, digest), []).append(path)
    excluded_roots = {root / ".git", root / "dist", root / "benmark", skill}
    for path in root.rglob("*"):
        if not path.is_file() or path.is_relative_to(skill):
            continue
        if any(path.is_relative_to(base) for base in excluded_roots if base.exists()):
            continue
        key = (path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest())
        if key in owned:
            errors.append(
                f"byte-for-byte duplicate outside canonical skill: {path.relative_to(root)} "
                f"matches {owned[key][0].relative_to(root)}"
            )

    payload = {
        "status": "pass" if not errors else "fail",
        "canonical_skill": str(skill.relative_to(root)),
        "single_source": not errors,
        "errors": errors,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
