#!/usr/bin/env python3
"""End-to-end smoke test for the distiller skill toolchain."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, capture_output=True)


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    scripts = root / "scripts"
    failures: list[str] = []

    skill_text = (root / "SKILL.md").read_text(encoding="utf-8")
    if not skill_text.startswith("---\n") or "name: writer-novel-style-distiller" not in skill_text:
        failures.append("invalid SKILL.md frontmatter/name")

    for py in scripts.glob("*.py"):
        result = run([sys.executable, "-m", "py_compile", str(py)])
        if result.returncode:
            failures.append(f"syntax error in {py.name}: {result.stderr.strip()}")

    benchmark_validator = scripts / "validate_audit_benchmark.py"
    result = run([sys.executable, str(benchmark_validator)])
    if result.returncode:
        failures.append("authoritative audit benchmark validation failed: " + result.stdout + result.stderr)

    builtin_validator = scripts / "validate_builtin_profiles.py"
    result = run([sys.executable, str(builtin_validator)])
    if result.returncode:
        failures.append("built-in profile validation failed: " + result.stdout + result.stderr)

    with tempfile.TemporaryDirectory(prefix="style-distiller-test-") as td:
        base = Path(td)
        novel = base / "sample.txt"
        parts = ["书名：测试样本", "作者：测试"]
        for i in range(1, 6):
            parts.extend([
                f"第{i}章 测试{i}",
                "天刚亮，阿宁把窗推开。院里有人扫地，竹帚擦过石板。",
                "“你又没睡？”小禾问。",
                "阿宁把杯子往旁边挪了挪。她当然睡了，只不过梦太长，醒得也太早。",
                "“睡了。”她说，“别管我，先吃饭。”",
                "小禾没拆穿她，把热饼掰开，较软的那半放到了她手边。",
            ])
        parts.extend([
            "终章 归来",
            "雨停以后，阿宁把旧钥匙放回门边。她没有回头，先把窗推开。",
            "番外一 新年",
            "小禾把新饼端上桌，阿宁挑走烤得最焦的那块，谁也没提旧账。",
            "作者后记",
            "这是用于测试结构识别的作者说明，不属于小说正史。",
        ])
        novel.write_text("\n\n".join(parts), encoding="utf-8")
        work = base / "work"
        result = run([
            sys.executable, str(scripts / "ingest_novel.py"), str(novel), "--output", str(work),
            "--completion-status", "complete", "--completion-basis", "user_explicit",
        ])
        if result.returncode:
            failures.append("ingest failed: " + result.stderr.strip())
        else:
            try:
                payload = json.loads(result.stdout)
                if payload.get("units", 0) < 8:
                    failures.append("ingest did not detect expected chapters and terminal materials")
                if payload.get("completion_status") != "complete":
                    failures.append("ingest did not preserve explicit completion status")
                if not payload.get("extra_units"):
                    failures.append("ingest did not detect supplied extra")
                if not payload.get("author_afterword_units"):
                    failures.append("ingest did not separate author afterword")
                sample_units = set(payload.get("sample_units", []))
                if not set(payload.get("extra_units", [])).issubset(sample_units):
                    failures.append("complete-work sample plan omitted supplied extra")
            except Exception as exc:
                failures.append(f"ingest returned invalid JSON: {exc}")

        result = run([sys.executable, str(scripts / "measure_style.py"), "--workdir", str(work)])
        if result.returncode:
            failures.append("measure failed: " + result.stderr.strip())
        elif not (work / "metrics.json").is_file():
            failures.append("metrics.json missing")

        generated_root = base / "generated"
        skill_name = "writer-sample-style-smoke"
        result = run([
            sys.executable, str(scripts / "init_profile.py"), "--output", str(generated_root),
            "--skill-name", skill_name, "--profile-name", "烟雾测试", "--protagonist", "阿宁",
        ])
        child = generated_root / skill_name
        if result.returncode:
            failures.append("init_profile failed: " + result.stderr.strip())
        else:
            for md in child.rglob("*.md"):
                text = md.read_text(encoding="utf-8")
                text = text.replace("{{OPTIONAL_HUMOR_AUDIT_SECTION}}", "")
                text = re.sub(r"\{\{[A-Z0-9_]*_SCORE\}\}", "8.0", text)
                text = re.sub(r"\{\{[^{}]+\}\}", "测试内容", text)
                md.write_text(text, encoding="utf-8")
            manifest_path = child / "references/source-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["source_files"] = [{"source_id": "S01", "file_name": "private-sample.txt", "sha256": "0" * 64}]
            manifest["corpus"]["effective_characters"] = 10000
            manifest["corpus"]["full_text_covered"] = True
            manifest["completion"].update({
                "status": "complete",
                "basis": "user_explicit",
                "user_explicitly_declared": True,
                "main_ending_present": True,
                "epilogue_present": False,
                "extras_present": True,
                "author_afterword_present": True,
                "terminal_arc_units": [6, 7],
                "main_ending_units": [6],
                "extra_units": [7],
                "author_afterword_units": [8],
            })
            manifest["completion"]["coverage"].update({
                "main_ending_analyzed": True,
                "epilogue_analyzed": False,
                "extras_checked": True,
                "extras_analyzed": True,
            })
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

            result = run([sys.executable, str(scripts / "validate_profile.py"), str(child)])
            if result.returncode:
                failures.append("generated profile validation failed: " + result.stdout + result.stderr)
            dist = base / "dist"
            result = run([sys.executable, str(scripts / "package_skill.py"), str(child), "--output", str(dist)])
            if result.returncode or not (dist / f"{skill_name}.zip").is_file():
                failures.append("package failed: " + result.stdout + result.stderr)

    payload = {"status": "pass" if not failures else "fail", "failures": failures}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())